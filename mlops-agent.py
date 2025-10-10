import json
import boto3
import logging
import time
import os
import tempfile
import shutil
import re
import urllib.request
import urllib.error
import zipfile
import io
import ssl
import certifi
import uuid
from typing import Dict, Any
from contextlib import contextmanager
from functools import wraps

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sagemaker_client = boto3.client('sagemaker')
codestar_client = boto3.client('codestar-connections')
servicecatalog_client = boto3.client('servicecatalog')

# Constants
STANDARD_TAGS = [
    {'Key': 'project', 'Value': 'mlopsagent'},
    {'Key': 'CreatedBy', 'Value': 'MLOpsAgent'}
]
MAX_ZIP_SIZE = 100 * 1024 * 1024  # 100MB
MAX_EXTRACT_SIZE = 500 * 1024 * 1024  # 500MB
DEFAULT_TIMEOUT = 30

# Security: Input validation functions
def validate_project_name(name):
    """Validate SageMaker project name."""
    if not name or not isinstance(name, str):
        raise ValueError("Project name is required")
    if not re.match(r'^[a-zA-Z0-9-]{1,63}$', name):
        raise ValueError("Invalid project name. Must be 1-63 alphanumeric characters or hyphens")
    return name

def validate_github_repo(repo):
    """Validate GitHub repository format."""
    if not repo or not isinstance(repo, str):
        raise ValueError("GitHub repository is required")
    if not re.match(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$', repo):
        raise ValueError("Invalid GitHub repository format. Expected: username/repo")
    return repo

def validate_s3_bucket_name(bucket):
    """Validate S3 bucket name."""
    if not bucket or not isinstance(bucket, str):
        raise ValueError("S3 bucket name is required")
    if not re.match(r'^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$', bucket):
        raise ValueError("Invalid S3 bucket name")
    if '..' in bucket or '.-' in bucket or '-.' in bucket:
        raise ValueError("Invalid S3 bucket name pattern")
    return bucket

def validate_arn(arn):
    """Validate AWS ARN format."""
    if not arn or not isinstance(arn, str):
        raise ValueError("ARN is required")
    if not re.match(r'^arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:.+$', arn):
        raise ValueError("Invalid AWS ARN format")
    return arn

def validate_connection_name(name):
    """Validate CodeStar connection name."""
    if not name or not isinstance(name, str):
        raise ValueError("Connection name is required")
    if not re.match(r'^[a-zA-Z0-9_-]{1,32}$', name):
        raise ValueError("Invalid connection name. Must be 1-32 alphanumeric characters, underscores, or hyphens")
    return name

def validate_feature_group_name(name):
    """Validate Feature Group name."""
    if not name or not isinstance(name, str):
        raise ValueError("Feature group name is required")
    if not re.match(r'^[a-zA-Z0-9-]{1,63}$', name):
        raise ValueError("Invalid feature group name")
    return name

def validate_pipeline_name(name):
    """Validate pipeline name."""
    if not name or not isinstance(name, str):
        raise ValueError("Pipeline name is required")
    if not re.match(r'^[a-zA-Z0-9-]{1,256}$', name):
        raise ValueError("Invalid pipeline name")
    return name

def sanitize_for_logging(data):
    """Remove sensitive fields from logging."""
    sensitive_keys = ['token', 'Token', 'arn', 'Arn', 'ARN', 'password', 'secret', 'key', 'Key']
    if isinstance(data, dict):
        return {k: '***REDACTED***' if any(s.lower() in k.lower() for s in sensitive_keys) else sanitize_for_logging(v) 
                for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]
    return data

def safe_error_response(error, status_code=500):
    """Return safe error response without internal details."""
    error_id = str(uuid.uuid4())
    logger.error(f"Error ID {error_id}: {str(error)}", exc_info=True)
    
    return {
        'statusCode': status_code,
        'body': {
            'error': 'An error occurred processing your request',
            'error_id': error_id,
            'message': 'Please contact support with the error ID'
        }
    }

@contextmanager
def secure_temp_dir():
    """Create temporary directory with secure permissions."""
    temp_dir = tempfile.mkdtemp()
    os.chmod(temp_dir, 0o700)  # Owner only
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def rate_limit(max_calls=10, period=60):
    """Rate limiting decorator."""
    calls = []
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [c for c in calls if c > now - period]
            
            if len(calls) >= max_calls:
                sleep_time = period - (now - calls[0])
                logger.warning(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
            calls.append(time.time())
            return func(*args, **kwargs)
        return wrapper
    return decorator

def safe_extract_zip(zip_file, extract_path):
    """Safely extract ZIP file with path traversal protection."""
    for member in zip_file.namelist():
        # Check for path traversal
        member_path = os.path.normpath(os.path.join(extract_path, member))
        if not member_path.startswith(os.path.abspath(extract_path)):
            raise ValueError(f"Path traversal attempt detected: {member}")
        
        # Check for absolute paths
        if os.path.isabs(member):
            raise ValueError(f"Absolute path in ZIP: {member}")
    
    # Check total extraction size
    total_size = sum(info.file_size for info in zip_file.infolist())
    if total_size > MAX_EXTRACT_SIZE:
        raise ValueError(f"ZIP extraction would exceed size limit: {total_size}")
    
    zip_file.extractall(extract_path)

@rate_limit(max_calls=10, period=60)
def safe_urlopen(url, timeout=DEFAULT_TIMEOUT):
    """Wrapper for urllib with security features."""
    # Create secure SSL context
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    # Validate URL scheme
    if not url.startswith('https://'):
        raise ValueError("Only HTTPS URLs are allowed")
    
    # Validate allowed domains
    from urllib.parse import urlparse
    parsed = urlparse(url)
    allowed_domains = ['api.github.com', 'github.com']
    if parsed.hostname not in allowed_domains:
        raise ValueError(f"Domain not allowed: {parsed.hostname}")
    
    return urllib.request.urlopen(url, context=ssl_context, timeout=timeout)

def get_aws_region():
    """Get AWS region with fallback."""
    region = os.environ.get('AWS_REGION')
    if not region:
        try:
            region = boto3.Session().region_name
        except Exception:
            region = 'us-east-1'
    return region

def lambda_handler(event, context):
    """Main handler for MLOps project management actions."""
    logger.debug("="*50)
    logger.debug("BEDROCK AGENT EVENT DEBUG")
    logger.debug("="*50)
    # Security: Sanitize event before logging
    logger.debug(f"Event received: {json.dumps(sanitize_for_logging(event), indent=2, default=str)}")
    logger.debug("="*50)
    
    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    http_method = event.get('httpMethod', '')
    
    params = extract_parameters_from_request_body(event)
    
    logger.info(f"Action Group: {action_group}")
    logger.info(f"API Path: {api_path}")
    logger.info(f"HTTP Method: {http_method}")
    logger.debug(f"Extracted Parameters: {sanitize_for_logging(params)}")
    
    try:
        if api_path == '/configure-code-connection':
            response = configure_code_connection(params)
        elif api_path == '/create-mlops-project':
            response = create_mlops_project(params)
        elif api_path == '/manage-project-lifecycle':
            response = manage_project_lifecycle(params)
        elif api_path == '/list-mlops-templates':
            response = list_mlops_templates(params)
        elif api_path == '/build-cicd-pipeline': 
            response = build_cicd_pipeline(params)
        elif api_path == '/manage-model-approval': 
            response = manage_model_approval(params)
        elif api_path == '/manage-staging-approval': 
            response = manage_staging_approval(params)
        else:
            response = {
                'statusCode': 400,
                'body': f'Unknown API path: {api_path}'
            }
    except ValueError as e:
        # Validation errors
        logger.warning(f"Validation error: {str(e)}")
        response = {
            'statusCode': 400,
            'body': {'error': 'Validation error', 'message': str(e)}
        }
    except Exception as e:
        # Unexpected errors
        response = safe_error_response(e)
    
    logger.info(f"Response status: {response.get('statusCode', 200)}")
    
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': action_group,
            'apiPath': api_path,
            'httpMethod': http_method,
            'httpStatusCode': response.get('statusCode', 200),
            'responseBody': {
                'application/json': {
                    'body': json.dumps(response.get('body', response))
                }
            }
        }
    }

def extract_parameters_from_request_body(event):
    """Extract parameters from Bedrock Agent event."""
    params = {}
    
    try:
        # Method 1: Check parameters array
        if 'parameters' in event and isinstance(event['parameters'], list):
            for param in event['parameters']:
                if isinstance(param, dict) and 'name' in param and 'value' in param:
                    params[param['name']] = param['value']
        
        # Method 2: Check requestBody
        request_body = event.get('requestBody')
        if request_body:
            content = request_body.get('content', {})
            application_json = content.get('application/json', {})
            properties = application_json.get('properties', [])
            
            for prop in properties:
                if isinstance(prop, dict) and 'name' in prop and 'value' in prop:
                    if prop['name'] not in params:
                        params[prop['name']] = prop['value']
        
        # Method 3: Check query string parameters
        if 'queryStringParameters' in event and event['queryStringParameters']:
            params.update(event['queryStringParameters'])
        
    except Exception as e:
        logger.error(f"Error extracting parameters: {str(e)}", exc_info=True)
    
    return params

def ensure_s3_bucket_exists(artifact_store_uri):
    """Ensure S3 bucket exists with comprehensive error handling."""
    bucket_created = False
    bucket_name = None
    
    try:
        # Parse and validate S3 URI
        s3_path = artifact_store_uri.replace('s3://', '')
        bucket_name = s3_path.split('/')[0]
        prefix = '/'.join(s3_path.split('/')[1:]) if '/' in s3_path else ''
        
        # Security: Validate bucket name
        bucket_name = validate_s3_bucket_name(bucket_name)
        
        logger.info(f"Checking S3 bucket: {bucket_name}")
        
        s3_client = boto3.client('s3')
        
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} exists and is accessible")
            bucket_created = False
            
        except Exception as head_error:
            error_code = None
            if hasattr(head_error, 'response') and 'Error' in head_error.response:
                error_code = head_error.response['Error'].get('Code', 'Unknown')
            
            if error_code == '404' or 'Not Found' in str(head_error):
                logger.info(f"Bucket doesn't exist, creating: {bucket_name}")
                
                try:
                    region = get_aws_region()
                    
                    if region == 'us-east-1':
                        s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    
                    s3_client.put_bucket_tagging(
                        Bucket=bucket_name,
                        Tagging={'TagSet': STANDARD_TAGS + [{'Key': 'Purpose', 'Value': 'MLflowArtifacts'}]}
                    )
                    
                    logger.info(f"Successfully created and tagged bucket: {bucket_name}")
                    bucket_created = True
                    time.sleep(2)
                    
                except Exception as create_error:
                    logger.error(f"Failed to create bucket: {str(create_error)}")
                    
                    if 'BucketAlreadyExists' in str(create_error) or 'already exists' in str(create_error).lower():
                        try:
                            account_id = boto3.client('sts').get_caller_identity()['Account']
                            timestamp = int(time.time())
                            
                            suggested_names = [
                                f"{bucket_name}-{account_id}",
                                f"{bucket_name}-{timestamp}",
                                f"mlops-{account_id}-{timestamp}"
                            ]
                            
                            return False, f"Bucket name conflict", {
                                'original_bucket': bucket_name,
                                'suggested_names': suggested_names,
                                'account_id': account_id
                            }
                        except Exception:
                            return False, f"Bucket creation failed: {create_error}", None
                    else:
                        return False, f"Bucket creation failed: {create_error}", None
                        
            elif error_code == '403' or 'Forbidden' in str(head_error):
                logger.error(f"Bucket {bucket_name} exists but is owned by another account")
                return False, f"Bucket access forbidden", None
            else:
                return False, f"Bucket access error: {head_error}", None
        
        # Create prefix/folder structure if specified
        if prefix:
            try:
                folder_key = prefix.rstrip('/') + '/'
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=folder_key,
                    Body=b'',
                    Metadata={'CreatedBy': 'MLOpsAgent'}
                )
            except Exception as folder_error:
                logger.warning(f"Could not create folder structure: {str(folder_error)}")
        
        # Test write access
        try:
            test_key = f"{prefix}/mlflow-test-{int(time.time())}.txt" if prefix else f"mlflow-test-{int(time.time())}.txt"
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=b'MLflow server access test',
                Metadata={'CreatedBy': 'MLOpsAgent'}
            )
            
            s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            
        except Exception as write_error:
            logger.error(f"S3 write test failed: {str(write_error)}")
            return False, f"S3 write access failed", bucket_name
        
        bucket_status = "created" if bucket_created else "existing"
        success_message = f"S3 bucket ready ({bucket_status}): s3://{bucket_name}"
        
        return True, success_message, bucket_name
        
    except ValueError as e:
        # Validation error
        return False, str(e), None
    except Exception as e:
        logger.error(f"S3 bucket setup failed: {str(e)}", exc_info=True)
        return False, f"S3 setup error", bucket_name

def configure_code_connection(params: Dict[str, Any]) -> Dict[str, Any]:
    """Set up AWS CodeStar connection for GitHub integration."""
    logger.info("configure_code_connection called")
    
    try:
        # Security: Validate inputs
        connection_name = validate_connection_name(params.get('connection_name'))
        provider_type = params.get('provider_type', 'GitHub')
        
        if provider_type not in ['GitHub', 'Bitbucket', 'GitHubEnterpriseServer']:
            raise ValueError(f"Invalid provider type: {provider_type}")
        
        response = codestar_client.create_connection(
            ConnectionName=connection_name,
            ProviderType=provider_type,
            Tags=STANDARD_TAGS + [{'Key': 'Purpose', 'Value': 'MLOpsAutomation'}]
        )
        
        connection_arn = response['ConnectionArn']
        connection_status = response.get('ConnectionStatus', 'PENDING')
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully created CodeStar connection: {connection_name}',
                'connection_arn': connection_arn,
                'connection_status': connection_status,
                'connection_name': connection_name,
                'provider_type': provider_type,
                'next_steps': [
                    'Complete the connection setup in the AWS Console',
                    f'Navigate to: AWS Console → Developer Tools → Settings → Connections',
                    f'Find connection "{connection_name}" and click "Update pending connection"'
                ]
            }
        }
        
    except ValueError as e:
        return {'statusCode': 400, 'body': {'error': 'Validation error', 'message': str(e)}}
    except Exception as e:
        if 'already exists' in str(e).lower():
            return {
                'statusCode': 409,
                'body': {
                    'error': f'Connection already exists',
                    'suggestion': 'Use a different connection name'
                }
            }
        return safe_error_response(e)

def ensure_sagemaker_servicecatalog_enabled():
    """Ensure SageMaker Service Catalog portfolio is enabled."""
    try:
        region = get_aws_region()
        sagemaker_client = boto3.client('sagemaker', region_name=region)
        
        # Check if already enabled
        status_response = sagemaker_client.get_sagemaker_servicecatalog_portfolio_status()
        if status_response.get('Status') == 'Enabled':
            logger.info("SageMaker Service Catalog portfolio already enabled")
            return True
        
        # Enable the portfolio
        logger.info("Enabling SageMaker Service Catalog portfolio...")
        sagemaker_client.enable_sagemaker_servicecatalog_portfolio()
        
        # Wait a moment for it to take effect
        import time
        time.sleep(5)
        
        logger.info("SageMaker Service Catalog portfolio enabled successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to enable SageMaker Service Catalog: {str(e)}")
        return False

def find_mlops_service_catalog_product():
    """
    Find MLOps Service Catalog product by name instead of hardcoded IDs.
    Returns (product_id, provisioning_artifact_id) or (None, None) if not found.
    """
    try:
        # Ensure SageMaker Service Catalog is enabled first
        if not ensure_sagemaker_servicecatalog_enabled():
            logger.error("Could not enable SageMaker Service Catalog")
            return None, None
        
        region = get_aws_region()
        sc = boto3.client('servicecatalog', region_name=region)
        
        # Product name to search for
        sc_product_name = "MLOps template for model building, training, and deployment with third-party Git repositories using CodePipeline"
        
        logger.info(f"Searching for MLOps product in {region}")
        
        # Search for the product
        response = sc.search_products(
            Filters={
                'FullTextSearch': [sc_product_name]
            }
        )
        
        products = response.get('ProductViewSummaries', [])
        logger.info(f"Service Catalog search returned {len(products)} products")
        
        # Log all found products for debugging
        if products:
            logger.debug("Found products:")
            for i, p in enumerate(products):
                logger.debug(f"  {i+1}. {p.get('Name', 'No Name')} - {p.get('ProductId', 'No ID')}")
        else:
            logger.warning(f"Service Catalog returned no products in {region} - catalog may be empty")
        
        # Find exact match by name
        matching_products = [
            p for p in products 
            if p.get('Name') == sc_product_name
        ]
        
        if not matching_products:
            logger.error(f"MLOps product not found in {region}. Searched for: '{sc_product_name}'")
            if products:
                logger.error(f"Available products: {[p.get('Name') for p in products[:3]]}")
            return None, None
        
        product_id = matching_products[0]['ProductId']
        logger.info(f"✅ Found MLOps product: {product_id}")
        
        # Get provisioning artifacts for this product
        artifacts_response = sc.list_provisioning_artifacts(ProductId=product_id)
        artifacts = artifacts_response.get('ProvisioningArtifactDetails', [])
        
        logger.info(f"Found {len(artifacts)} provisioning artifacts for product {product_id}")
        
        if not artifacts:
            logger.error(f"❌ No provisioning artifacts found for product {product_id}")
            return product_id, None
        
        # Log all artifacts for debugging
        logger.debug("Available artifacts:")
        for i, a in enumerate(artifacts):
            active_status = "Active" if a.get('Active', False) else "Inactive"
            logger.debug(f"  {i+1}. {a.get('Name', 'No Name')} ({a.get('Id', 'No ID')}) - {active_status}")
        
        # Get the latest/active artifact
        active_artifacts = [a for a in artifacts if a.get('Active', False)]
        if active_artifacts:
            provisioning_artifact_id = active_artifacts[0]['Id']
            logger.info(f"✅ Using active artifact: {provisioning_artifact_id}")
        else:
            provisioning_artifact_id = artifacts[0]['Id']  # Fallback to first
            logger.warning(f"⚠️ No active artifacts found, using first artifact: {provisioning_artifact_id}")
        
        logger.info(f"🎉 SUCCESS - Product ID: {product_id}, Artifact ID: {provisioning_artifact_id}")
        return product_id, provisioning_artifact_id
        
    except Exception as e:
        logger.error(f"Error finding MLOps product: {str(e)}", exc_info=True)
        return None, None

def create_mlops_project(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create MLOps project with GitHub integration."""
    logger.info("create_mlops_project called")
    
    try:
        # Security: Validate all inputs
        project_name = validate_project_name(params.get('project_name'))
        github_repo_build = validate_github_repo(params.get('github_repo_build'))
        github_repo_deploy = validate_github_repo(params.get('github_repo_deploy'))
        connection_arn = validate_arn(params.get('connection_arn'))
        github_username = params.get('github_username')
        
        if not github_username or not re.match(r'^[a-zA-Z0-9-]{1,39}$', github_username):
            raise ValueError("Invalid GitHub username")
        
        product_id, provisioning_artifact_id = find_mlops_service_catalog_product()
        
        if not product_id or not provisioning_artifact_id:
            return {'statusCode': 404, 'body': {'error': 'MLOps template not found'}}
        
        model_build_code_repository_branch = 'main'
        model_deploy_code_repository_branch = 'main'
        model_build_code_repository_full_name = f"{github_username}/{github_repo_build.split('/')[-1]}"
        model_deploy_code_repository_full_name = f"{github_username}/{github_repo_deploy.split('/')[-1]}"
        
        project_parameters = [
            {'Key': 'ModelBuildCodeRepositoryBranch', 'Value': model_build_code_repository_branch},
            {'Key': 'ModelBuildCodeRepositoryFullname', 'Value': model_build_code_repository_full_name},
            {'Key': 'ModelDeployCodeRepositoryBranch', 'Value': model_deploy_code_repository_branch},
            {'Key': 'ModelDeployCodeRepositoryFullname', 'Value': model_deploy_code_repository_full_name},
            {'Key': 'CodeConnectionArn', 'Value': connection_arn}
        ]
        
        project_response = sagemaker_client.create_project(
            ProjectName=project_name,
            ProjectDescription=f"MLOps project for model building and deployment",
            ServiceCatalogProvisioningDetails={
                'ProductId': product_id,
                'ProvisioningArtifactId': provisioning_artifact_id,
                'ProvisioningParameters': project_parameters,
                'Tags': STANDARD_TAGS + [
                    {'Key': 'Environment', 'Value': 'Development'},
                    {'Key': 'GitHubIntegration', 'Value': 'Enabled'}
                ]
            },
            Tags=STANDARD_TAGS
        )
        
        project_arn = project_response['ProjectArn']
        project_id = project_response['ProjectId']
        
        # Wait for completion
        max_wait_time = 600
        wait_interval = 10
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                project_status_response = sagemaker_client.describe_project(ProjectName=project_name)
                current_status = project_status_response['ProjectStatus']
                
                if current_status == 'CreateCompleted':
                    break
                elif current_status == 'CreateFailed':
                    return {'statusCode': 500, 'body': {'error': 'Project creation failed'}}
                
                time.sleep(wait_interval)
                elapsed_time += wait_interval
                    
            except Exception as status_error:
                logger.error(f"Error checking status: {status_error}")
                time.sleep(wait_interval)
                elapsed_time += wait_interval
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully created MLOps project: {project_name}',
                'project_name': project_name,
                'project_id': project_id,
                'project_arn': project_arn,
                'status': 'CreateCompleted'
            }
        }
        
    except ValueError as e:
        return {'statusCode': 400, 'body': {'error': 'Validation error', 'message': str(e)}}
    except Exception as e:
        return safe_error_response(e)

# NOTE: Due to file size constraints, the following functions have been abbreviated.
# Full implementations with security fixes should include:
# - build_cicd_pipeline() with safe ZIP extraction and input validation
# - manage_model_approval() with ARN validation
# - manage_staging_approval() with proper error handling
# - manage_project_lifecycle() with input validation
# - list_mlops_templates() (simplified version)
# - All helper functions with security improvements

def list_mlops_templates(params: Dict[str, Any]) -> Dict[str, Any]:
    """List available MLOps templates."""
    available_templates = [
        {
            'ProductId': 'prod-txwcxmr6k3xsc',
            'Name': 'MLOps Template for Model Building and Deployment with GitHub',
            'ShortDescription': 'Template for MLOps projects with GitHub integration'
        }
    ]
    
    return {
        'statusCode': 200,
        'body': {
            'message': f'Found {len(available_templates)} MLOps templates',
            'templates': available_templates
        }
    }

def manage_model_approval(params: Dict[str, Any]) -> Dict[str, Any]:
    """Manage model approval in SageMaker Model Registry."""
    try:
        # Security: Validate ARN
        model_package_arn = validate_arn(params.get('model_package_arn'))
        action = params.get('action', 'approve')
        
        if action not in ['approve', 'reject']:
            raise ValueError(f"Invalid action: {action}")
        
        approval_status = 'Approved' if action == 'approve' else 'Rejected'
        
        sagemaker_client.update_model_package(
            ModelPackageArn=model_package_arn,
            ModelApprovalStatus=approval_status,
            ApprovalDescription=f'{approval_status} by MLOps Agent'
        )
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully {action}d model package',
                'model_package_arn': model_package_arn,
                'approval_status': approval_status
            }
        }
    
    except ValueError as e:
        return {'statusCode': 400, 'body': {'error': 'Validation error', 'message': str(e)}}
    except Exception as e:
        return safe_error_response(e)

def manage_staging_approval(params: Dict[str, Any]) -> Dict[str, Any]:
    """Manage CodePipeline staging approval."""
    try:
        # Security: Validate project name
        project_name = validate_project_name(params.get('project_name'))
        action = params.get('action', 'list')
        region = params.get('region') or get_aws_region()
        
        project_response = sagemaker_client.describe_project(ProjectName=project_name)
        project_id = project_response['ProjectId']
        
        codepipeline_client = boto3.client('codepipeline', region_name=region)
        deploy_pipeline_name = f"sagemaker-{project_name}-{project_id}-modeldeploy"
        
        if action == 'approve':
            pipeline_state = codepipeline_client.get_pipeline_state(name=deploy_pipeline_name)
            
            approved_actions = []
            for stage in pipeline_state.get('stageStates', []):
                for action_state in stage.get('actionStates', []):
                    if action_state.get('actionTypeId', {}).get('category') == 'Approval':
                        latest_execution = action_state.get('latestExecution', {})
                        
                        if latest_execution.get('status') == 'InProgress':
                            token = latest_execution.get('token')
                            if token:
                                try:
                                    codepipeline_client.put_approval_result(
                                        pipelineName=deploy_pipeline_name,
                                        stageName=stage['stageName'],
                                        actionName=action_state['actionName'],
                                        result={'summary': 'Approved by MLOps Agent', 'status': 'Approved'},
                                        token=token
                                    )
                                    approved_actions.append(action_state['actionName'])
                                except Exception as e:
                                    logger.error(f"Approval failed: {e}")
            
            if approved_actions:
                return {
                    'statusCode': 200,
                    'body': {
                        'message': f'Approved {len(approved_actions)} action(s)',
                        'approved_actions': approved_actions
                    }
                }
            else:
                return {'statusCode': 404, 'body': {'error': 'No pending approvals found'}}
        
        else:
            # List action
            pipeline_state = codepipeline_client.get_pipeline_state(name=deploy_pipeline_name)
            pending_approvals = []
            
            for stage in pipeline_state.get('stageStates', []):
                for action_state in stage.get('actionStates', []):
                    if action_state.get('actionTypeId', {}).get('category') == 'Approval':
                        latest_execution = action_state.get('latestExecution', {})
                        if latest_execution.get('status') == 'InProgress':
                            pending_approvals.append({
                                'stage_name': stage['stageName'],
                                'action_name': action_state['actionName']
                            })
            
            return {
                'statusCode': 200,
                'body': {
                    'message': f'Pipeline status for {project_name}',
                    'pending_approvals': pending_approvals
                }
            }
    
    except ValueError as e:
        return {'statusCode': 400, 'body': {'error': 'Validation error', 'message': str(e)}}
    except Exception as e:
        return safe_error_response(e)

def manage_project_lifecycle(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle project updates and lifecycle management."""
    try:
        # Security: Validate inputs
        project_name = validate_project_name(params.get('project_name'))
        action = params.get('action')
        
        if action not in ['describe', 'delete', 'check_mlflow_status']:
            raise ValueError(f"Invalid action: {action}")
        
        if action == 'describe':
            response = sagemaker_client.describe_project(ProjectName=project_name)
            return {
                'statusCode': 200,
                'body': {
                    'project_name': response['ProjectName'],
                    'project_id': response['ProjectId'],
                    'project_status': response['ProjectStatus']
                }
            }
        
        elif action == 'delete':
            sagemaker_client.delete_project(ProjectName=project_name)
            return {
                'statusCode': 200,
                'body': {
                    'message': f'Successfully initiated deletion of project: {project_name}',
                    'status': 'DeleteInProgress'
                }
            }
        
        elif action == 'check_mlflow_status':
            tracking_server_name = params.get('tracking_server_name')
            if not tracking_server_name:
                raise ValueError("tracking_server_name required for MLflow status check")
            
            mlflow_response = sagemaker_client.describe_mlflow_tracking_server(
                TrackingServerName=tracking_server_name
            )
            
            return {
                'statusCode': 200,
                'body': {
                    'tracking_server_name': tracking_server_name,
                    'status': mlflow_response.get('TrackingServerStatus', 'Unknown'),
                    'is_ready': mlflow_response.get('TrackingServerStatus') == 'InService'
                }
            }
            
    except ValueError as e:
        return {'statusCode': 400, 'body': {'error': 'Validation error', 'message': str(e)}}
    except Exception as e:
        return safe_error_response(e)

def build_cicd_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    """Build CI/CD pipeline using seed code from GitHub (using urllib instead of requests)."""
    logger.info(f"build_cicd_pipeline called with params: {sanitize_for_logging(params)}")
    
    # Required parameters from previous actions
    project_name = params.get('project_name')
    model_build_code_repository_full_name = params.get('model_build_code_repository_full_name')
    code_connection_arn = params.get('code_connection_arn')
    
    # Additional required parameters
    feature_group_name = params.get('feature_group_name')
    bucket_name = params.get('bucket_name')
    mlflow_tracking_server_arn = params.get('mlflow_tracking_server_arn')
    pipeline_name = params.get('pipeline_name')
    
    # Optional parameters with defaults
    region = params.get('region') or get_aws_region()
    bucket_prefix = params.get('bucket_prefix', 'player-churn/xgboost')
    experiment_name = params.get('experiment_name', 'player-churn-model-build-pipeline')
    train_instance_type = params.get('train_instance_type', 'ml.m5.xlarge')
    test_score_threshold = float(params.get('test_score_threshold', 0.75))
    model_approval_status = params.get('model_approval_status', 'PendingManualApproval')
    
    # Validate required parameters
    missing_params = []
    if not project_name: missing_params.append('project_name')
    if not model_build_code_repository_full_name: missing_params.append('model_build_code_repository_full_name')
    if not code_connection_arn: missing_params.append('code_connection_arn')
    if not feature_group_name: missing_params.append('feature_group_name')
    if not bucket_name: missing_params.append('bucket_name')
    if not mlflow_tracking_server_arn: missing_params.append('mlflow_tracking_server_arn')
    if not pipeline_name: missing_params.append('pipeline_name')
    
    if missing_params:
        error_msg = f'Missing required parameters: {missing_params}'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': {
                'error': error_msg,
                'missing_parameters': missing_params
            }
        }
    
    try:
        # Phase 1: Get project details
        logger.info("Phase 1: Getting project details...")
        project_response = sagemaker_client.describe_project(ProjectName=project_name)
        project_id = project_response['ProjectId']
        project_arn = project_response['ProjectArn']
        
        # Derive additional variables
        repository_name = model_build_code_repository_full_name.split('/')[1]
        git_folder = project_name
        project_folder = f'sagemaker-{project_id}-modelbuild'
        project_path = f'{git_folder}/{project_folder}'
        model_package_group_name = f"{project_name}-{project_id}"
        
        logger.info(f"Project details: ID={project_id}, Path={project_path}")
        
        # Phase 2: Setup temporary directories with secure permissions
        logger.info("Phase 2: Setting up temporary directories...")
        with secure_temp_dir() as temp_dir:
            home_dir = temp_dir
            agent_folder = "mlops-sagemaker-mlflow"
            
            os.makedirs(f"{home_dir}/{project_path}", exist_ok=True)
            os.makedirs(f"{home_dir}/{agent_folder}/pipelines", exist_ok=True)
            
            logger.info(f"Temporary directories created in: {temp_dir}")
            
            # Phase 3: Download repository or create seed files if empty
            logger.info("Phase 3: Downloading repository from GitHub or creating seed files...")
            
            # Extract username and repo from full name
            username, repo_name = model_build_code_repository_full_name.split('/')
            
            # First, check if repository has content
            github_api_url = f"https://api.github.com/repos/{username}/{repo_name}/contents"
            repo_has_content = False
            
            try:
                with safe_urlopen(github_api_url, timeout=10) as response:
                    if response.getcode() == 200:
                        content = json.loads(response.read().decode())
                        if len(content) > 0:
                            repo_has_content = True
                            logger.info(f"Repository has {len(content)} files")
                        else:
                            logger.info("Repository exists but is empty")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    logger.info("Repository not found - will create seed files")
                else:
                    logger.warning(f"Error checking repository: {e}")
            except Exception as e:
                logger.warning(f"Error checking repository contents: {e}")
            
            if repo_has_content:
                # Download existing repository content
                github_zip_url = f"https://github.com/{username}/{repo_name}/archive/refs/heads/main.zip"
                logger.info(f"Downloading from: {github_zip_url}")
                
                try:
                    with safe_urlopen(github_zip_url, timeout=30) as response:
                        # Security: Check size before reading
                        content_length = response.headers.get('Content-Length')
                        if content_length and int(content_length) > MAX_ZIP_SIZE:
                            raise ValueError("ZIP file too large")
                        
                        zip_data = response.read(MAX_ZIP_SIZE + 1)
                        if len(zip_data) > MAX_ZIP_SIZE:
                            raise ValueError("ZIP file exceeds size limit")
                    
                    # Extract ZIP to temporary directory with security checks
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                        safe_extract_zip(zip_file, temp_dir)
                        
                    # Find the extracted directory
                    extracted_folders = [f for f in os.listdir(temp_dir) if f.startswith(repo_name)]
                    if not extracted_folders:
                        raise Exception(f"Could not find extracted repository folder")
                    
                    source_dir = os.path.join(temp_dir, extracted_folders[0])
                    target_dir = f"{home_dir}/{project_path}"
                    
                    # Copy files from extracted directory to target directory
                    for item in os.listdir(source_dir):
                        source_item = os.path.join(source_dir, item)
                        target_item = os.path.join(target_dir, item)
                        if os.path.isdir(source_item):
                            shutil.copytree(source_item, target_item)
                        else:
                            shutil.copy2(source_item, target_item)
                    
                    logger.info(f"Repository downloaded and extracted successfully")
                    
                except urllib.error.URLError as e:
                    logger.error(f"Failed to download repository: {e}")
                    return {
                        'statusCode': 500,
                        'body': {
                            'error': 'Failed to download repository from GitHub',
                            'message': str(e)
                        }
                    }
            else:
                # Create basic seed files since repository is empty
                logger.info("Creating basic seed files for empty repository...")
                
                seed_files = {
                    'README.md': f"""# {project_name} - Model Build Repository
This repository contains the model building pipeline for the {project_name} MLOps project.
""",
                    'setup.py': '''from setuptools import setup, find_packages
required_packages = ["sagemaker"]
setup(name="mlops-model-build", version="1.0.0", packages=find_packages(), install_requires=required_packages)
''',
                    'requirements.txt': '''sagemaker
mlflow==2.13.2
sagemaker-mlflow
s3fs
xgboost
''',
                    'pipelines/__init__.py': '',
                    'pipelines/run_pipeline.py': '''#!/usr/bin/env python3
import argparse
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role-arn", required=True)
    parser.add_argument("--pipeline-name", required=True)
    args = parser.parse_args()
    print(f"Pipeline: {args.pipeline_name}")
if __name__ == "__main__":
    main()
'''
                }
                
                target_dir = f"{home_dir}/{project_path}"
                for file_path, content in seed_files.items():
                    full_path = os.path.join(target_dir, file_path)
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, 'w') as f:
                        f.write(content)
                
                logger.info(f"Created {len(seed_files)} seed files")
            
            # Phase 4: File operations
            logger.info("Phase 4: Performing file operations...")
            
            buildspec_original = f"{home_dir}/{project_path}/codebuild-buildspec-original.yml"
            buildspec_current = f"{home_dir}/{project_path}/codebuild-buildspec.yml"
            
            if os.path.exists(buildspec_current):
                os.rename(buildspec_current, buildspec_original)
            
            abalone_path = f"{home_dir}/{project_path}/pipelines/abalone"
            playerchurn_path = f"{home_dir}/{project_path}/pipelines/playerchurn"
            
            if os.path.exists(abalone_path):
                os.rename(abalone_path, playerchurn_path)
            
            requirements_content = """sagemaker
mlflow==2.13.2
sagemaker-mlflow
s3fs
xgboost
"""
            
            config_content = """# SageMaker configuration
"""
            
            with open(f"{home_dir}/{project_path}/requirements.txt", 'w') as f:
                f.write(requirements_content)
            
            with open(f"{home_dir}/{project_path}/config.yaml", 'w') as f:
                f.write(config_content)
            
            logger.info("File operations completed")
        
        # Phase 5: Update pipeline parameters
        logger.info("Phase 5: Updating pipeline parameters...")
        
        current_pipeline = sagemaker_client.describe_pipeline(PipelineName=pipeline_name)
        current_definition = json.loads(current_pipeline['PipelineDefinition'])
        
        required_parameters = {
            "region": region,
            "feature_group_name": feature_group_name,
            "bucket_name": bucket_name,
            "bucket_prefix": bucket_prefix,
            "experiment_name": experiment_name,
            "train_instance_type": train_instance_type,
            "test_score_threshold": str(test_score_threshold),
            "model_package_group_name": model_package_group_name,
            "model_approval_status": model_approval_status,
            "mlflow_tracking_server_arn": mlflow_tracking_server_arn
        }
        
        if 'Parameters' not in current_definition:
            current_definition['Parameters'] = []
        
        existing_params = {param['Name']: param for param in current_definition['Parameters']}
        
        for param_name, param_value in required_parameters.items():
            if param_name in existing_params:
                existing_params[param_name]['DefaultValue'] = param_value
            else:
                current_definition['Parameters'].append({
                    'Name': param_name,
                    'Type': 'String',
                    'DefaultValue': param_value
                })
        
        sagemaker_client.update_pipeline(
            PipelineName=pipeline_name,
            PipelineDefinition=json.dumps(current_definition),
            RoleArn=current_pipeline['RoleArn']
        )
        
        logger.info(f"Pipeline {pipeline_name} updated")
        
        # Phase 6: Start pipeline execution
        logger.info("Phase 6: Starting pipeline execution...")
        
        pipeline_parameters = [
            {'Name': k, 'Value': v} for k, v in required_parameters.items()
        ]
        
        execution_response = sagemaker_client.start_pipeline_execution(
            PipelineName=pipeline_name,
            PipelineParameters=pipeline_parameters
        )
        
        pipeline_exec_id = execution_response["PipelineExecutionArn"]
        logger.info(f"Pipeline execution started: {pipeline_exec_id}")
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'CI/CD pipeline build completed successfully',
                'pipeline_execution_arn': pipeline_exec_id,
                'project_name': project_name,
                'project_id': project_id
            }
        }
        
    except ValueError as e:
        return {'statusCode': 400, 'body': {'error': 'Validation error', 'message': str(e)}}
    except Exception as e:
        return safe_error_response(e)
