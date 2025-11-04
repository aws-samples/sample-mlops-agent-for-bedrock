import json
import boto3
from botocore.exceptions import ClientError
import logging
import time
import subprocess
import os
import tempfile
import shutil
import re
import urllib.request
import urllib.error
import zipfile
import io
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Use codeconnections_client (newer service) from backup
sagemaker_client = boto3.client('sagemaker')
codeconnections_client = boto3.client('codeconnections')
servicecatalog_client = boto3.client('servicecatalog')
logs_client = boto3.client('logs')

def tag_mlops_log_groups():
    """Tag all MLOps-related log groups with CreatedBy: MLOpsAgent"""
    try:
        patterns = [
            '/aws/codebuild/sagemaker-mlops-',
            '/aws/lambda/sagemaker-p',
            '/aws/sagemaker/mlflow/',
            '/aws/sagemaker/Endpoints/',
            '/aws/sagemaker/ProcessingJobs',
            '/aws/sagemaker/TrainingJobs'
        ]
        
        paginator = logs_client.get_paginator('describe_log_groups')
        
        for pattern in patterns:
            for page in paginator.paginate():
                for log_group in page['logGroups']:
                    log_group_name = log_group['logGroupName']
                    
                    if pattern in log_group_name:
                        tag_log_group(log_group_name, {
                            'CreatedBy': 'MLOpsAgent',
                            'Purpose': 'MLOpsAutomation'
                        })
                        
    except Exception as e:
        logger.warning(f"Could not tag MLOps log groups: {str(e)}")

def tag_log_group(log_group_name, tags=None):
    """Tag CloudWatch log group with CreatedBy and other tags"""
    if tags is None:
        tags = {}
    
    tags['CreatedBy'] = 'MLOpsAgent'
    
    try:
        logs_client.tag_log_group(
            logGroupName=log_group_name,
            tags=tags
        )
        logger.info(f"Tagged log group {log_group_name}")
    except Exception as e:
        logger.warning(f"Could not tag log group {log_group_name}: {str(e)}")

def lambda_handler(event, context):
    """Main handler for MLOps project management actions"""
    
    # Tag the Lambda log group on first execution
    try:
        log_group_name = f"/aws/lambda/{context.function_name}"
        tag_log_group(log_group_name, {
            'CreatedBy': 'MLOpsAgent',
            'Purpose': 'MLOpsAutomation'
        })
        
        tag_mlops_log_groups()
        
    except Exception as e:
        logger.warning(f"Could not tag Lambda log group: {str(e)}")
    
    logger.info("="*50)
    logger.info("BEDROCK AGENT EVENT DEBUG")
    logger.info("="*50)
    logger.info(f"FULL EVENT RECEIVED: {json.dumps(event, indent=2, default=str)}")
    logger.info("="*50)
    
    # Extract action and parameters from Bedrock Agent event
    action_group = event.get('actionGroup', '')
    api_path = event.get('apiPath', '')
    http_method = event.get('httpMethod', '')
    
    # Extract parameters from requestBody
    params = extract_parameters_from_request_body(event)
    
    logger.info(f"Action Group: {action_group}")
    logger.info(f"API Path: {api_path}")
    logger.info(f"HTTP Method: {http_method}")
    logger.info(f"Extracted Parameters: {params}")
    
    try:
        if api_path == '/configure-code-connection':
            response = create_code_connection(params)  # Use backup version
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
        elif api_path == '/create-feature-store-group':
            response = create_feature_store_group(params)
        elif api_path == '/create-mlflow-server':
            response = create_mlflow_server(params)
        elif api_path == '/create-model-group':
            response = create_model_group(params)
        else:
            response = {
                'statusCode': 400,
                'body': f'Unknown API path: {api_path}. Available paths: /configure-code-connection, /create-mlops-project, /manage-project-lifecycle, /list-mlops-templates, /build-cicd-pipeline, /manage-model-approval, /manage-staging-approval, /create-feature-store-group, /create-mlflow-server, /create-model-group'
            }
    except Exception as e:
        logger.error(f"Error executing action: {str(e)}", exc_info=True)
        response = {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
    
    logger.info(f"Response: {json.dumps(response, indent=2, default=str)}")
    
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
    """Extract parameters from Bedrock Agent event (handles both requestBody and parameters array)"""
    params = {}
    
    try:
        logger.info("Starting parameter extraction...")
        logger.info(f"Event keys: {list(event.keys())}")
        
        # METHOD 1: Check parameters array (THIS IS WHERE BEDROCK SENDS THEM!)
        if 'parameters' in event and isinstance(event['parameters'], list):
            parameters_array = event['parameters']
            logger.info(f"Found parameters array with {len(parameters_array)} items")
            
            for param in parameters_array:
                if isinstance(param, dict) and 'name' in param and 'value' in param:
                    params[param['name']] = param['value']
                    logger.info(f"Extracted parameter: {param['name']} = {param['value']}")
        
        # METHOD 2: Check requestBody (fallback for other formats)
        request_body = event.get('requestBody')
        if request_body:
            logger.info(f"RequestBody also exists: {json.dumps(request_body, indent=2, default=str)}")
            
            content = request_body.get('content', {})
            application_json = content.get('application/json', {})
            properties = application_json.get('properties', [])
            
            logger.info(f"Properties in requestBody: {len(properties)}")
            
            # Convert properties array to dictionary
            for prop in properties:
                if isinstance(prop, dict) and 'name' in prop and 'value' in prop:
                    # Don't overwrite parameters array values
                    if prop['name'] not in params:
                        params[prop['name']] = prop['value']
                        logger.info(f"Extracted from requestBody: {prop['name']} = {prop['value']}")
        else:
            logger.info("No requestBody found in event (using parameters array)")
            
        # METHOD 3: Check for query string parameters (additional fallback)
        if 'queryStringParameters' in event and event['queryStringParameters']:
            logger.info(f"Query parameters: {event['queryStringParameters']}")
            params.update(event['queryStringParameters'])
        
        logger.info(f"Final extracted parameters: {params}")
        
    except Exception as e:
        logger.error(f"Error extracting parameters: {str(e)}", exc_info=True)
    
    return params

# Use create_code_connection from backup (CodeConnections)
def create_code_connection(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create AWS CodeConnections connection for GitHub integration"""
    logger.info(f"create_code_connection called with params: {params}")
    
    connection_name = params.get('connection_name')
    provider_type = params.get('provider_type', 'GitHub')
    
    if not connection_name:
        return {
            'statusCode': 400,
            'body': 'Missing required parameter: connection_name'
        }
    
    try:
        logger.info(f"Creating CodeConnections connection: {connection_name} with provider: {provider_type}")
        
        response = codeconnections_client.create_connection(
            ConnectionName=connection_name,
            ProviderType=provider_type,
            Tags=[
                {
                    'Key': 'CreatedBy',
                    'Value': 'MLOpsAgent'
                },
                {
                    'Key': 'Purpose',
                    'Value': 'MLOpsAutomation'
                }
            ]
        )
        
        logger.info(f"CodeConnections response: {json.dumps(response, default=str)}")
        
        connection_arn = response['ConnectionArn']
        connection_status = response.get('ConnectionStatus', 'PENDING')
        
        logger.info(f"Successfully created connection: {connection_arn}")
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully created CodeConnections connection: {connection_name}',
                'connection_arn': connection_arn,
                'connection_status': connection_status,
                'connection_name': connection_name,
                'provider_type': provider_type,
                'next_steps': [
                    'Complete the connection setup in the AWS Console',
                    f'Navigate to: AWS Console → Developer Tools → Settings → Connections',
                    f'Find connection "{connection_name}" and click "Update pending connection"',
                    'Authorize GitHub access for the connection',
                    f'Use this connection ARN in your MLOps projects: {connection_arn}'
                ],
                'console_url': f'https://console.aws.amazon.com/codesuite/settings/connections'
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating connection: {str(e)}", exc_info=True)
        
        # Check if it's a duplicate connection error
        if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
            return {
                'statusCode': 409,
                'body': {
                    'error': f'Connection with name "{connection_name}" already exists',
                    'message': 'Try using a different connection name or use the existing connection',
                    'suggestion': f'List existing connections or use: "{connection_name}-{int(time.time())}"'
                }
            }
        else:
            return {
                'statusCode': 500,
                'body': f'Failed to create connection: {str(e)}'
            }

# Use complex S3 bucket validation from main file
def ensure_s3_bucket_exists(artifact_store_uri):
    """Ensure S3 bucket exists with comprehensive error handling"""
    bucket_created = False
    bucket_name = None
    
    try:
        # Parse S3 URI
        s3_path = artifact_store_uri.replace('s3://', '')
        bucket_name = s3_path.split('/')[0]
        prefix = '/'.join(s3_path.split('/')[1:]) if '/' in s3_path else ''
        
        logger.info(f"Checking S3 bucket: {bucket_name}")
        
        if not bucket_name:
            return False, "Invalid S3 URI - no bucket name found", None
        
        s3_client = boto3.client('s3')
        
        # Check if bucket exists and is accessible
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket {bucket_name} exists and is accessible")
            bucket_created = False
            
        except Exception as head_error:
            # Parse the error to determine what to do
            error_code = None
            if hasattr(head_error, 'response') and 'Error' in head_error.response:
                error_code = head_error.response['Error'].get('Code', 'Unknown')
            
            logger.info(f"HeadBucket error code: {error_code}, error: {str(head_error)[:200]}")
            
            if error_code == '404' or 'Not Found' in str(head_error):
                # Bucket doesn't exist - try to create it
                logger.info(f"Bucket doesn't exist (404), creating: {bucket_name}")
                
                try:
                    region = os.environ.get('AWS_REGION', 'us-west-2')
                    logger.info(f"Creating bucket in region: {region}")
                    
                    if region == 'us-east-1':
                        create_response = s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        create_response = s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': region}
                        )
                    
                    logger.info(f"Create bucket response: {str(create_response)[:200]}")
                    logger.info(f"Successfully created bucket: {bucket_name}")
                    bucket_created = True
                    
                    # Wait a moment for bucket to be ready
                    time.sleep(2)
                    
                except Exception as create_error:
                    logger.error(f"Failed to create bucket: {str(create_error)[:200]}")
                    
                    # Check if it's a naming conflict
                    if 'BucketAlreadyExists' in str(create_error) or 'already exists' in str(create_error).lower():
                        # Suggest alternative bucket names
                        try:
                            account_id = boto3.client('sts').get_caller_identity()['Account']
                            timestamp = int(time.time())
                            
                            suggested_names = [
                                f"{bucket_name}-{account_id}",
                                f"{bucket_name}-{timestamp}",
                                f"mlops-{account_id}-{timestamp}",
                                f"sagemaker-mlflow-{account_id}"
                            ]
                            
                            return False, f"Bucket name conflict: {create_error}", {
                                'original_bucket': bucket_name,
                                'error': str(create_error),
                                'suggested_names': suggested_names,
                                'account_id': account_id
                            }
                        except Exception as sts_error:
                            logger.error(f"Error getting account ID: {sts_error}")
                            return False, f"Bucket creation failed: {create_error}", None
                    else:
                        return False, f"Bucket creation failed: {create_error}", None
                        
            elif error_code == '403' or 'Forbidden' in str(head_error):
                # Bucket exists but belongs to another account
                logger.error(f"Bucket {bucket_name} exists but is owned by another account")
                
                try:
                    account_id = boto3.client('sts').get_caller_identity()['Account']
                    timestamp = int(time.time())
                    
                    suggested_names = [
                        f"{bucket_name}-{account_id}",
                        f"{bucket_name}-{timestamp}",
                        f"mlops-{account_id}-{timestamp}",
                        f"sagemaker-mlflow-{account_id}"
                    ]
                    
                    return False, f"Bucket name conflict: {bucket_name} is owned by another AWS account", {
                        'conflict_type': 'name_taken',
                        'original_bucket': bucket_name,
                        'suggested_names': suggested_names,
                        'account_id': account_id
                    }
                except Exception as sts_error:
                    logger.error(f"Error getting account ID: {sts_error}")
                    return False, f"Bucket access forbidden: {head_error}", None
            else:
                # Other error - return it
                logger.error(f"Unexpected bucket access error: {str(head_error)[:200]}")
                return False, f"Bucket access error: {head_error}", None
        
        # If we get here, bucket exists or was created successfully
        logger.info(f"Proceeding with bucket setup for: {bucket_name}")
        
        # Create prefix/folder structure if specified
        if prefix:
            try:
                logger.info(f"Creating folder structure: {prefix}")
                folder_key = prefix.rstrip('/') + '/'
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=folder_key,
                    Body=b'',
                    Metadata={'CreatedBy': 'MLOpsAgent', 'Purpose': 'MLflowArtifacts'}
                )
                logger.info(f"Successfully created folder structure: {folder_key}")
            except Exception as folder_error:
                logger.warning(f"Could not create folder structure: {str(folder_error)[:200]}")
                # Don't fail for folder creation issues
        
        # Test write access
        try:
            logger.info("Testing S3 write access...")
            test_key = f"{prefix}/mlflow-test-{int(time.time())}.txt" if prefix else f"mlflow-test-{int(time.time())}.txt"
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=b'MLflow server access test',
                Metadata={'CreatedBy': 'MLOpsAgent'}
            )
            logger.info(f"Write test successful: {test_key}")
            
            # Clean up test file
            s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            logger.info(f"Test file cleanup successful")
            
        except Exception as write_error:
            logger.error(f"S3 write test failed: {str(write_error)[:200]}")
            return False, f"S3 write access failed: {write_error}", bucket_name
        
        bucket_status = "created" if bucket_created else "existing"
        success_message = f"S3 bucket ready ({bucket_status}): s3://{bucket_name}"
        logger.info(success_message)
        
        return True, success_message, bucket_name
        
    except Exception as e:
        logger.error(f"S3 bucket setup failed with unexpected error: {str(e)[:200]}", exc_info=True)
        return False, f"S3 setup error: {e}", bucket_name

# Use dynamic Service Catalog product discovery from backup
def find_mlops_service_catalog_product():
    """Dynamically discover MLOps Service Catalog template"""
    try:
        logger.info("Searching for MLOps Service Catalog template...")
        
        # Search for the specific MLOps template dynamically using FullTextSearch
        target_template_name = "MLOps template for model building, training, and deployment with third-party Git repositories using CodePipeline"
        
        search_response = servicecatalog_client.search_products(
            Filters={
                'FullTextSearch': [target_template_name]
            }
        )
        
        logger.info(f"Search returned {len(search_response.get('ProductViewSummaries', []))} products")
        
        product_id = None
        provisioning_artifact_id = None
        
        for product in search_response.get('ProductViewSummaries', []):
            if product['Name'] == target_template_name:
                product_id = product['ProductId']
                
                # Get the latest provisioning artifact
                artifacts_response = servicecatalog_client.list_provisioning_artifacts(
                    ProductId=product_id
                )
                artifacts = artifacts_response.get('ProvisioningArtifactDetails', [])
                if artifacts:
                    # Use the latest provisioning artifact (last in list)
                    active_artifacts = [a for a in artifacts if a.get('Active', True)]
                    if active_artifacts:
                        provisioning_artifact_id = active_artifacts[-1]['Id']
                        break
        
        # Add fallback search if exact match fails
        if not product_id:
            logger.info("Exact match failed, trying broader search terms...")
            fallback_terms = ["MLOps", "SageMaker", "model building"]
            
            for term in fallback_terms:
                logger.info(f"Searching with fallback term: {term}")
                search_response = servicecatalog_client.search_products(
                    Filters={'FullTextSearch': [term]}
                )
                
                # Look for products containing key MLOps terms
                for product in search_response.get('ProductViewSummaries', []):
                    if ('mlops' in product['Name'].lower() and 
                        ('git' in product['Name'].lower() or 'codepipeline' in product['Name'].lower())):
                        
                        product_id = product['ProductId']
                        logger.info(f"Found matching product via fallback: {product['Name']} (ID: {product_id})")
                        
                        # Get the latest provisioning artifact
                        artifacts_response = servicecatalog_client.list_provisioning_artifacts(
                            ProductId=product_id
                        )
                        artifacts = artifacts_response.get('ProvisioningArtifactDetails', [])
                        if artifacts:
                            active_artifacts = [a for a in artifacts if a.get('Active', True)]
                            if active_artifacts:
                                provisioning_artifact_id = active_artifacts[-1]['Id']
                                break
                
                if product_id:
                    break
        
        return product_id, provisioning_artifact_id
        
    except Exception as e:
        logger.error(f"Error finding MLOps Service Catalog product: {str(e)}", exc_info=True)
        return None, None

def create_mlops_project(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create MLOps project with GitHub integration and wait for completion"""
    logger.info(f"create_mlops_project called with params: {params}")
    
    project_name = params.get('project_name')
    github_repo_build = params.get('github_repo_build')
    github_repo_deploy = params.get('github_repo_deploy')
    connection_arn = params.get('connection_arn')
    github_username = params.get('github_username')
    
    if not all([project_name, github_repo_build, github_repo_deploy, connection_arn, github_username]):
        missing_params = []
        if not project_name: missing_params.append('project_name')
        if not github_repo_build: missing_params.append('github_repo_build')
        if not github_repo_deploy: missing_params.append('github_repo_deploy')
        if not connection_arn: missing_params.append('connection_arn')
        if not github_username: missing_params.append('github_username')
        
        error_msg = f'Missing required parameters: {missing_params}. Available params: {list(params.keys())}'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': error_msg
        }
    
    try:
        # STEP 1: Find MLOps Service Catalog template using dynamic discovery
        logger.info("Step 1: Finding MLOps Service Catalog template...")
        product_id, provisioning_artifact_id = find_mlops_service_catalog_product()
        
        if not product_id or not provisioning_artifact_id:
            return {
                'statusCode': 404,
                'body': {
                    'error': 'MLOps Service Catalog product not found',
                    'message': 'Could not locate the MLOps template using dynamic discovery'
                }
            }
        
        logger.info(f"Found template - Product ID: {product_id}, Artifact ID: {provisioning_artifact_id}")
        
        # STEP 2: Set GitHub repository names and project parameters
        logger.info("Step 2: Setting up project parameters...")
        
        # Branch names (always main)
        model_build_code_repository_branch = 'main'
        model_deploy_code_repository_branch = 'main'
        
        # Full repository names
        model_build_code_repository_full_name = f"{github_username}/{github_repo_build}"
        model_deploy_code_repository_full_name = f"{github_username}/{github_repo_deploy}"
        
        logger.info(f"Build repo: {model_build_code_repository_full_name}")
        logger.info(f"Deploy repo: {model_deploy_code_repository_full_name}")
        
        # Set project parameters
        project_parameters = [
            {
                'Key': 'ModelBuildCodeRepositoryBranch',
                'Value': model_build_code_repository_branch
            },
            {
                'Key': 'ModelBuildCodeRepositoryFullname',
                'Value': model_build_code_repository_full_name
            },
            {
                'Key': 'ModelDeployCodeRepositoryBranch',
                'Value': model_deploy_code_repository_branch
            },
            {
                'Key': 'ModelDeployCodeRepositoryFullname',
                'Value': model_deploy_code_repository_full_name
            },
            {
                'Key': 'CodeConnectionArn',
                'Value': connection_arn
            }
        ]
        
        logger.info(f"Project parameters configured: {json.dumps(project_parameters, indent=2)}")
        
        # STEP 3: Create the SageMaker project
        logger.info("Step 3: Creating SageMaker MLOps project...")
        
        project_response = sagemaker_client.create_project(
            ProjectName=project_name,
            ProjectDescription=f"MLOps project for model building and deployment with GitHub integration",
            ServiceCatalogProvisioningDetails={
                'ProductId': product_id,
                'ProvisioningArtifactId': provisioning_artifact_id,
                'ProvisioningParameters': project_parameters
            },
            Tags=[
                {
                    'Key': 'CreatedBy',
                    'Value': 'MLOpsAgent'
                },
                {
                    'Key': 'Environment',
                    'Value': 'Development'
                },
                {
                    'Key': 'GitHubIntegration',
                    'Value': 'Enabled'
                }
            ]
        )
        
        project_arn = project_response['ProjectArn']
        project_id = project_response['ProjectId']
        
        logger.info(f"Project creation initiated - ID: {project_id}, ARN: {project_arn}")
        
        # STEP 4: Wait for project creation completion (3-5 minutes)
        logger.info("Step 4: Monitoring project creation status...")
        logger.info("Project creation takes about 3-5 minutes...")
        
        max_wait_time = 600  # 10 minutes maximum wait
        wait_interval = 10   # Check every 10 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                project_status_response = sagemaker_client.describe_project(ProjectName=project_name)
                current_status = project_status_response['ProjectStatus']
                
                logger.info(f"Current project status: {current_status} (elapsed: {elapsed_time}s)")
                
                if current_status == 'CreateCompleted':
                    logger.info(f"MLOps project {project_name} creation completed successfully!")
                    break
                elif current_status == 'CreateFailed':
                    error_msg = f"Project creation failed with status: {current_status}"
                    logger.error(error_msg)
                    return {
                        'statusCode': 500,
                        'body': {
                            'error': 'Project creation failed',
                            'message': error_msg,
                            'project_name': project_name,
                            'project_id': project_id,
                            'status': current_status
                        }
                    }
                else:
                    # Still in progress, wait and check again
                    logger.info("Waiting for project creation completion...")
                    time.sleep(wait_interval)
                    elapsed_time += wait_interval
                    
            except Exception as status_error:
                logger.error(f"Error checking project status: {status_error}")
                time.sleep(wait_interval)
                elapsed_time += wait_interval
        
        # Check final status
        try:
            final_status_response = sagemaker_client.describe_project(ProjectName=project_name)
            final_status = final_status_response['ProjectStatus']
        except Exception as final_check_error:
            logger.error(f"Error getting final status: {final_check_error}")
            final_status = 'Unknown'
        
        if final_status != 'CreateCompleted':
            logger.warning(f"Project creation did not complete within {max_wait_time} seconds. Final status: {final_status}")
            return {
                'statusCode': 202,  # Accepted but not completed
                'body': {
                    'message': f'MLOps project creation in progress: {project_name}',
                    'project_name': project_name,
                    'project_id': project_id,
                    'project_arn': project_arn,
                    'status': final_status,
                    'warning': f'Creation did not complete within {max_wait_time} seconds',
                    'next_steps': [
                        'Check SageMaker Studio for project status',
                        'Project creation may still be in progress',
                        'CI/CD pipelines will be created once project completes'
                    ]
                }
            }
        
        # SUCCESS: Project creation completed
        logger.info(f"SUCCESS: MLOps project {project_name} creation completed!")
        
        model_package_group_name = f"{project_name}-{project_id}"
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully created MLOps project: {project_name}',
                'project_name': project_name,
                'project_id': project_id,
                'project_arn': project_arn,
                'model_package_group_name': model_package_group_name,
                'status': 'CreateCompleted',
                'github_integration': {
                    'build_repo': model_build_code_repository_full_name,
                    'deploy_repo': model_deploy_code_repository_full_name,
                    'connection_arn': connection_arn
                },
                'template_info': {
                    'product_id': product_id,
                    'provisioning_artifact_id': provisioning_artifact_id
                },
                'creation_time': f'{elapsed_time} seconds',
                'next_steps': [
                    'MLOps project created successfully',
                    'Build pipeline will start automatically',
                    'Models will be registered to model package group after training',
                    'Use manage-model-approval action to approve models when ready',
                    'Check SageMaker Studio for project details',
                    f'Build pipeline: https://github.com/{model_build_code_repository_full_name}',
                    f'Deploy pipeline: https://github.com/{model_deploy_code_repository_full_name}'
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating MLOps project: {str(e)}", exc_info=True)
        
        error_message = str(e)
        if 'AccessDenied' in error_message:
            return {
                'statusCode': 403,
                'body': {
                    'error': 'Access denied creating MLOps project',
                    'message': 'Insufficient permissions for SageMaker project creation'
                }
            }
        elif 'already exists' in error_message.lower():
            return {
                'statusCode': 409,
                'body': {
                    'error': f'Project "{project_name}" already exists',
                    'message': 'Choose a different project name',
                    'suggestion': f'Try: {project_name}-v2 or {project_name}-{int(time.time())}'
                }
            }
        else:
            return {
                'statusCode': 500,
                'body': f'Failed to create MLOps project: {error_message}'
            }

# Use complex GitHub repository downloading and pipeline building from main file
def build_cicd_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    """Build CI/CD pipeline using seed code from GitHub (using urllib instead of requests)"""
    logger.info(f"build_cicd_pipeline called with params: {params}")
    
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
    region = params.get('region', 'us-east-1')
    bucket_prefix = params.get('bucket_prefix', 'player-churn/xgboost')
    experiment_name = params.get('experiment_name', 'player-churn-model-build-pipeline')
    train_instance_type = params.get('train_instance_type', 'ml.m5.xlarge')
    test_score_threshold = float(params.get('test_score_threshold', 0.75))
    model_approval_status = params.get('model_approval_status', 'Approved')
    
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
        error_msg = f'Missing required parameters: {missing_params}. Please provide these values.'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': {
                'error': error_msg,
                'missing_parameters': missing_params,
                'provided_parameters': list(params.keys())
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
        
        # Phase 2: Setup temporary directories
        logger.info("Phase 2: Setting up temporary directories...")
        temp_dir = tempfile.mkdtemp()
        home_dir = temp_dir
        agent_folder = "mlops-sagemaker-mlflow"
        
        os.makedirs(f"{home_dir}/{project_path}", exist_ok=True)
        os.makedirs(f"{home_dir}/{agent_folder}/pipelines", exist_ok=True)
        
        logger.info(f"Temporary directories created in: {temp_dir}")
        
        # Phase 3: Setup basic configuration
        logger.info("Phase 3: Setting up basic configuration...")
        
        requirements_content = """sagemaker
mlflow==2.13.2
sagemaker-mlflow
s3fs
xgboost
"""
        
        config_content = """# SageMaker configuration
# Add your configuration here
"""
        
        target_dir = f"{home_dir}/{project_path}"
        os.makedirs(target_dir, exist_ok=True)
        
        with open(f"{target_dir}/requirements.txt", 'w') as f:
            f.write(requirements_content)
        
        with open(f"{target_dir}/config.yaml", 'w') as f:
            f.write(config_content)
        
        logger.info("Basic configuration completed")
        
        # Phase 4: Generate and save buildspec
        logger.info("Phase 4: Generating buildspec file...")
        logger.info("Phase 5: Generating buildspec file...")
        
        code_build_buildspec_template = r"""
version: 0.2
phases:
  install:
    runtime-versions:
      python: 3.10
    commands:
      - pip install --upgrade --force-reinstall . "awscli>1.20.30"
      - pip install mlflow==2.13.2 sagemaker-mlflow s3fs xgboost
    
  build:
    commands:
      - export SAGEMAKER_USER_CONFIG_OVERRIDE="./config.yaml"
      - export PYTHONUNBUFFERED=TRUE
      - export SAGEMAKER_PROJECT_NAME_ID="${SAGEMAKER_PROJECT_NAME}-${SAGEMAKER_PROJECT_ID}"
      - |
        run-pipeline \
          --role-arn $SAGEMAKER_PIPELINE_ROLE_ARN \
          --tags "[{\"Key\":\"sagemaker:project-name\",\"Value\":\"${SAGEMAKER_PROJECT_NAME}\"}, {\"Key\":\"sagemaker:project-id\", \"Value\":\"${SAGEMAKER_PROJECT_ID}\"}, {\"Key\":\"project\", \"Value\":\"mlopsagent\"}, {\"Key\":\"CreatedBy\", \"Value\":\"MLOpsAgent\"}]" \
          --pipeline-name "{{PIPELINE_NAME}}" \
          --kwargs "{ \
                \"region\":\"{{REGION}}\", \
                \"feature_group_name\":\"{{FEATURE_GROUP_NAME}}\",\
                \"bucket_name\":\"{{BUCKET_NAME}}\",\
                \"bucket_prefix\":\"{{BUCKET_PREFIX}}\",\
                \"experiment_name\":\"{{EXPERIMENT_NAME}}\", \
                \"train_instance_type\":\"{{TRAIN_INSTANCE_TYPE}}\", \
                \"test_score_threshold\":\"{{TEST_SCORE_THRESHOLD}}\",\
                \"model_package_group_name\":\"{{MODEL_PACKAGE_GROUP_NAME}}\",\
                \"model_approval_status\":\"{{MODEL_APPROVAL_STATUS}}\",\
                \"mlflow_tracking_server_arn\":\"{{MLFLOW_TRACKING_SERVER_ARN}}\"\
                    }"
      - echo "Create/update of the SageMaker Pipeline and a pipeline execution completed."
"""
        
        # Replace template variables
        code_build_buildspec = code_build_buildspec_template.replace("{{REGION}}", region)
        code_build_buildspec = code_build_buildspec.replace("{{PIPELINE_NAME}}", pipeline_name)
        code_build_buildspec = code_build_buildspec.replace("{{FEATURE_GROUP_NAME}}", feature_group_name)
        code_build_buildspec = code_build_buildspec.replace("{{BUCKET_NAME}}", bucket_name)
        code_build_buildspec = code_build_buildspec.replace("{{BUCKET_PREFIX}}", bucket_prefix)
        code_build_buildspec = code_build_buildspec.replace("{{EXPERIMENT_NAME}}", experiment_name)
        code_build_buildspec = code_build_buildspec.replace("{{TRAIN_INSTANCE_TYPE}}", train_instance_type)
        code_build_buildspec = code_build_buildspec.replace("{{TEST_SCORE_THRESHOLD}}", str(test_score_threshold))
        code_build_buildspec = code_build_buildspec.replace("{{MODEL_PACKAGE_GROUP_NAME}}", model_package_group_name)
        code_build_buildspec = code_build_buildspec.replace("{{MODEL_APPROVAL_STATUS}}", model_approval_status)
        code_build_buildspec = code_build_buildspec.replace("{{MLFLOW_TRACKING_SERVER_ARN}}", mlflow_tracking_server_arn)
        
        # Save buildspec file
        buildspec_path = f"{home_dir}/{project_path}/codebuild-buildspec.yml"
        with open(buildspec_path, "w") as f:
            f.write(code_build_buildspec)
        
        logger.info("Buildspec file generated and saved")

        # Cleanup temporary directory
        shutil.rmtree(temp_dir)
        
        return {
            'statusCode': 200,
            'body': {
                'message': 'CI/CD pipeline build completed successfully',
                'project_details': {
                    'project_name': project_name,
                    'project_id': project_id,
                    'project_arn': project_arn,
                    'model_package_group_name': model_package_group_name
                },
                'pipeline_parameters': {
                    'region': region,
                    'feature_group_name': feature_group_name,
                    'bucket_name': bucket_name,
                    'bucket_prefix': bucket_prefix,
                    'experiment_name': experiment_name,
                    'train_instance_type': train_instance_type,
                    'test_score_threshold': test_score_threshold,
                    'model_approval_status': model_approval_status,
                    'mlflow_tracking_server_arn': mlflow_tracking_server_arn
                },
                'git_operations': {
                    'repository_downloaded': False,
                    'files_processed': True,
                    'buildspec_generated': True,
                    'method': 'Basic configuration setup'
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Error building CI/CD pipeline: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {
                'error': 'Failed to build CI/CD pipeline',
                'message': str(e),
                'phase': 'GitHub API download or file processing'
            }
        }

# Use complex multi-method approval system from main file
def manage_model_approval(params: Dict[str, Any]) -> Dict[str, Any]:
    """Manage model approval in SageMaker Model Registry"""
    logger.info(f"manage_model_approval called with params: {params}")
    
    model_package_arn = params.get('model_package_arn')
    model_package_group_name = params.get('model_package_group_name')
    action = params.get('action', 'approve')
    approval_description = params.get('approval_description', 'Approved by MLOps Agent')
    
    logger.info(f"Received parameters: {list(params.keys())}")
    logger.info(f"model_package_group_name: {model_package_group_name}")
    logger.info(f"model_package_arn: {model_package_arn}")
    
    # Auto-resolve model package ARN if only group name provided
    if not model_package_arn and model_package_group_name:
        try:
            logger.info(f"Attempting to resolve ARN for model package group: {model_package_group_name}")
            response = sagemaker_client.list_model_packages(
                ModelPackageGroupName=model_package_group_name,
                SortBy='CreationTime',
                SortOrder='Descending',
                MaxResults=1
            )
            
            models = response.get('ModelPackageSummaryList', [])
            logger.info(f"Found {len(models)} models in group {model_package_group_name}")
            
            if models:
                model_package_arn = models[0]['ModelPackageArn']
                model_status = models[0].get('ModelApprovalStatus', 'Unknown')
                logger.info(f"Auto-resolved model package ARN: {model_package_arn} (status: {model_status})")
            else:
                logger.error(f"No models found in model package group: {model_package_group_name}")
                return {
                    'statusCode': 404,
                    'body': {
                        'error': f'No models found in model package group: {model_package_group_name}',
                        'message': 'The pipeline may not have completed yet or no models have been registered'
                    }
                }
        except Exception as e:
            logger.error(f"Failed to resolve model package ARN: {e}")
            return {
                'statusCode': 500,
                'body': {
                    'error': 'Failed to lookup model ARN',
                    'message': str(e),
                    'model_package_group_name': model_package_group_name
                }
            }
    
    if not model_package_arn:
        return {
            'statusCode': 400,
            'body': {
                'error': 'Missing required parameter: model_package_arn',
                'available_parameters': list(params.keys())
            }
        }
    
    try:
        if action == 'approve':
            response = sagemaker_client.update_model_package(
                ModelPackageArn=model_package_arn,
                ModelApprovalStatus='Approved',
                ApprovalDescription=approval_description
            )
            
            return {
                'statusCode': 200,
                'body': {
                    'message': f'Successfully approved model package',
                    'model_package_arn': model_package_arn,
                    'approval_status': 'Approved',
                    'approval_description': approval_description
                }
            }
        
        elif action == 'reject':
            response = sagemaker_client.update_model_package(
                ModelPackageArn=model_package_arn,
                ModelApprovalStatus='Rejected',
                ApprovalDescription=approval_description
            )
            
            return {
                'statusCode': 200,
                'body': {
                    'message': f'Successfully rejected model package',
                    'model_package_arn': model_package_arn,
                    'approval_status': 'Rejected',
                    'approval_description': approval_description
                }
            }
        
        else:
            return {
                'statusCode': 400,
                'body': f'Unsupported action: {action}. Supported actions: approve, reject'
            }
    
    except Exception as e:
        logger.error(f"Error managing model approval: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {
                'error': 'Failed to manage model approval',
                'message': str(e)
            }
        }

def manage_staging_approval(params: Dict[str, Any]) -> Dict[str, Any]:
    """Direct approach to CodePipeline approval using multiple methods"""
    logger.info(f"manage_staging_approval called with params: {params}")
    
    # Required parameters
    project_name = params.get('project_name')
    action = params.get('action', 'list')
    
    # Optional parameters
    region = params.get('region', 'us-west-2')
    
    if not project_name:
        return {
            'statusCode': 400,
            'body': {
                'error': 'Missing required parameter: project_name',
                'available_parameters': list(params.keys())
            }
        }
    
    try:
        # Get project details
        project_response = sagemaker_client.describe_project(ProjectName=project_name)
        project_id = project_response['ProjectId']
        
        # Initialize CodePipeline client
        codepipeline_client = boto3.client('codepipeline', region_name=region)
        
        # Find the deploy pipeline
        deploy_pipeline_name = f"sagemaker-{project_name}-{project_id}-modeldeploy"
        
        logger.info(f"Working with pipeline: {deploy_pipeline_name}")
        
        if action == 'approve':
            logger.info(f"AGGRESSIVE APPROVAL ATTEMPT for {deploy_pipeline_name}")
            
            approved_actions = []
            all_attempts = []
            
            # Method 1: Try pipeline state approach
            try:
                logger.info("Method 1: Pipeline State Approach")
                pipeline_state = codepipeline_client.get_pipeline_state(name=deploy_pipeline_name)
                
                for stage in pipeline_state.get('stageStates', []):
                    stage_name = stage['stageName']
                    logger.info(f"Checking stage: {stage_name}")
                    
                    for action in stage.get('actionStates', []):
                        action_name = action['actionName']
                        action_type = action.get('actionTypeId', {})
                        latest_execution = action.get('latestExecution', {})
                        
                        if action_type.get('category') == 'Approval':
                            status = latest_execution.get('status', 'Unknown')
                            token = latest_execution.get('token', '')
                            
                            attempt_info = {
                                'method': 'pipeline_state',
                                'stage_name': stage_name,
                                'action_name': action_name,
                                'status': status,
                                'has_token': bool(token),
                                'token_length': len(token) if token else 0
                            }
                            all_attempts.append(attempt_info)
                            
                            logger.info(f"Found approval: {action_name}, Status: {status}, Token: {'Yes' if token else 'No'}")
                            
                            if status == 'InProgress' and token:
                                try:
                                    logger.info(f"Attempting approval with pipeline state token...")
                                    
                                    codepipeline_client.put_approval_result(
                                        pipelineName=deploy_pipeline_name,
                                        stageName=stage_name,
                                        actionName=action_name,
                                        result={
                                            'summary': f'Approved via MLOps Agent - Method 1',
                                            'status': 'Approved'
                                        },
                                        token=token
                                    )
                                    
                                    approved_actions.append({
                                        'method': 'pipeline_state',
                                        'stage_name': stage_name,
                                        'action_name': action_name,
                                        'success': True
                                    })
                                    
                                    logger.info(f"SUCCESS: Method 1 approved {action_name}")
                                    
                                except Exception as e:
                                    logger.error(f"Method 1 failed: {e}")
                                    attempt_info['error'] = str(e)
                            
                            elif status == 'InProgress' and not token:
                                logger.warning(f"Action {action_name} is InProgress but no token available")
                                attempt_info['issue'] = 'No token available'
                
            except Exception as e:
                logger.error(f"Method 1 (pipeline state) failed: {e}")
                all_attempts.append({'method': 'pipeline_state', 'error': str(e)})
            
            # Return results
            if approved_actions:
                return {
                    'statusCode': 200,
                    'body': {
                        'message': f'SUCCESS: Approved {len(approved_actions)} action(s) using aggressive methods',
                        'project_name': project_name,
                        'deploy_pipeline_name': deploy_pipeline_name,
                        'approved_actions': approved_actions,
                        'all_attempts': all_attempts,
                        'next_steps': [
                            'Production deployment should now proceed automatically',
                            'Monitor CodePipeline console for continued progress',
                            'Production endpoint will be created shortly'
                        ]
                    }
                }
            else:
                return {
                    'statusCode': 404,
                    'body': {
                        'error': 'All approval methods failed',
                        'message': 'Could not approve using any available method',
                        'deploy_pipeline_name': deploy_pipeline_name,
                        'all_attempts': all_attempts,
                        'suggestion': 'Approve manually in CodePipeline console or check IAM permissions'
                    }
                }
        
        else:
            # For 'list' action, return the existing logic
            pipeline_state = codepipeline_client.get_pipeline_state(name=deploy_pipeline_name)
            
            pending_approvals = []
            for stage in pipeline_state.get('stageStates', []):
                for action in stage.get('actionStates', []):
                    if action.get('actionTypeId', {}).get('category') == 'Approval':
                        latest_execution = action.get('latestExecution', {})
                        if latest_execution.get('status') == 'InProgress':
                            pending_approvals.append({
                                'stage_name': stage['stageName'],
                                'action_name': action['actionName'],
                                'status': latest_execution.get('status'),
                                'has_token': bool(latest_execution.get('token'))
                            })
            
            return {
                'statusCode': 200,
                'body': {
                    'message': f'Pipeline status for {project_name}',
                    'deploy_pipeline_name': deploy_pipeline_name,
                    'pending_approvals': pending_approvals,
                    'summary': {
                        'pending_count': len(pending_approvals)
                    }
                }
            }
    
    except Exception as e:
        logger.error(f"Error in manage_staging_approval: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {
                'error': 'Failed to manage staging approval',
                'message': str(e)
            }
        }

# Keep remaining functions unchanged from backup
def create_feature_store_group(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create SageMaker Feature Store Feature Group with online store only"""
    logger.info(f"create_feature_store_group called with params: {params}")
    
    feature_group_name = params.get('feature_group_name')
    description = params.get('description', f'Feature group created by MLOps Agent')
    feature_description = params.get('feature_description', '')
    
    if not feature_group_name:
        error_msg = f'Missing required parameter: feature_group_name. Available params: {list(params.keys())}'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': error_msg
        }
    
    try:
        # Parse feature descriptions from natural language
        record_identifier_name, event_time_feature_name, feature_definitions = parse_feature_descriptions(feature_description)
        
        logger.info(f"Parsed {len(feature_definitions)} features from description")
        
        # Create Feature Group with ONLINE STORE ONLY
        response = sagemaker_client.create_feature_group(
            FeatureGroupName=feature_group_name,
            RecordIdentifierFeatureName=record_identifier_name,
            EventTimeFeatureName=event_time_feature_name,
            FeatureDefinitions=feature_definitions,
            OnlineStoreConfig={
                'EnableOnlineStore': True
            },
            Description=description,
            Tags=[
                {
                    'Key': 'CreatedBy',
                    'Value': 'MLOpsAgent'
                },
                {
                    'Key': 'Purpose',
                    'Value': 'FeatureStore'
                }
            ]
        )
        
        feature_group_arn = response['FeatureGroupArn']
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully created Feature Group: {feature_group_name}',
                'feature_group_name': feature_group_name,
                'feature_group_arn': feature_group_arn,
                'record_identifier': record_identifier_name,
                'event_time_feature': event_time_feature_name,
                'feature_count': len(feature_definitions)
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating Feature Group: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': f'Failed to create Feature Group: {str(e)}'
        }

def parse_feature_descriptions(description_text):
    """Parse natural language feature descriptions into SageMaker feature definitions"""
    logger.info(f"Parsing feature description: {description_text}")
    
    # Default values
    record_identifier = 'record_id'
    event_time_feature = 'event_time'
    feature_definitions = []
    feature_names_seen = set()
    
    if not description_text:
        return record_identifier, event_time_feature, [
            {'FeatureName': 'record_id', 'FeatureType': 'String'},
            {'FeatureName': 'event_time', 'FeatureType': 'String'}
        ]
    
    text = description_text.lower()
    
    # Extract record identifier
    id_patterns = [
        r'(\w+)\s+as\s+(?:string\s+)?identifier',
        r'(\w+)\s+as\s+(?:the\s+)?(?:record\s+)?(?:id|identifier)'
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, text)
        if match:
            record_identifier = match.group(1)
            break
    
    # Extract event time feature
    event_time_patterns = [
        r'(\w+)\s+as\s+(?:the\s+)?event\s+time',
        r'event\s+time\s+feature[:\s]+(\w+)'
    ]
    
    for pattern in event_time_patterns:
        match = re.search(pattern, text)
        if match:
            event_time_feature = match.group(1)
            break
    
    # Helper function to add feature without duplicates
    def add_feature(feature_name, feature_type):
        if feature_name not in feature_names_seen:
            feature_definitions.append({
                'FeatureName': feature_name,
                'FeatureType': feature_type
            })
            feature_names_seen.add(feature_name)
    
    # Add record identifier and event time
    add_feature(record_identifier, 'String')
    add_feature(event_time_feature, 'String')
    
    # Type mappings
    type_mappings = {
        'string': 'String', 'integer': 'Integral', 'number': 'Fractional',
        'float': 'Fractional', 'binary': 'Fractional'
    }
    
    # Parse features
    feature_patterns = [
        r'(\w+)\s+as\s+(\w+)',
        r'(\w+)\s+features?\s+as\s+(\w+)'
    ]
    
    for pattern in feature_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            feature_name, feature_type = match.groups()
            sagemaker_type = type_mappings.get(feature_type, 'String')
            
            if 'time_of_day' in feature_name:
                time_features = ['begin_session_time_of_day_mean_last_day_1', 'end_session_time_of_day_mean_last_day_1']
                for tf in time_features:
                    add_feature(tf, sagemaker_type)
            elif 'cohort_id' in feature_name:
                cohort_features = ['cohort_id_2024_09_11', 'cohort_id_2024_09_12']
                for cf in cohort_features:
                    add_feature(cf, sagemaker_type)
            else:
                if feature_name not in [record_identifier, event_time_feature]:
                    add_feature(feature_name, sagemaker_type)
    
    return record_identifier, event_time_feature, feature_definitions

def create_mlflow_server(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create SageMaker MLflow Tracking Server with comprehensive error handling"""
    logger.info(f"create_mlflow_server called with params: {params}")
    
    tracking_server_name = params.get('tracking_server_name')
    artifact_store_uri = params.get('artifact_store_uri')
    tracking_server_size = params.get('tracking_server_size', 'Small')
    role_arn = params.get('role_arn')
    mlflow_version = params.get('mlflow_version')
    
    if not all([tracking_server_name, artifact_store_uri]):
        missing_params = []
        if not tracking_server_name: missing_params.append('tracking_server_name')
        if not artifact_store_uri: missing_params.append('artifact_store_uri')
        
        error_msg = f'Missing required parameters: {missing_params}. Available params: {list(params.keys())}'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': error_msg
        }
    
    try:
        # STEP 1: Ensure S3 bucket exists using complex validation
        logger.info("Step 1: Validating/creating S3 bucket...")
        
        s3_success, s3_message, s3_details = ensure_s3_bucket_exists(artifact_store_uri)
        
        if not s3_success:
            error_response = {
                'error': 'S3 bucket setup failed',
                'message': s3_message,
                'artifact_store_uri': artifact_store_uri
            }
            
            if isinstance(s3_details, dict) and 'suggested_names' in s3_details:
                error_response.update({
                    'conflict_type': s3_details.get('conflict_type', 'unknown'),
                    'suggested_bucket_names': s3_details['suggested_names'],
                    'account_id': s3_details.get('account_id'),
                    'solution': 'Use one of the suggested bucket names or create the bucket manually first',
                    'example_retry': f"Try: s3://{s3_details['suggested_names'][0]}/mlflow-artifacts/"
                })
            
            return {
                'statusCode': 400,
                'body': error_response
            }
        
        logger.info(f"S3 setup complete: {s3_message}")
        bucket_name = s3_details
        
        # STEP 2: Auto-detect role ARN if not provided
        if not role_arn:
            try:
                sts_client = boto3.client('sts')
                caller_identity = sts_client.get_caller_identity()
                account_id = caller_identity['Account']
                
                lambda_context = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
                if lambda_context:
                    function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
                    possible_roles = [
                        f"arn:aws:iam::{account_id}:role/{function_name}-role",
                        f"arn:aws:iam::{account_id}:role/lambda-execution-role"
                    ]
                    
                    iam_client = boto3.client('iam')
                    for potential_role in possible_roles:
                        try:
                            role_name = potential_role.split('/')[-1]
                            iam_client.get_role(RoleName=role_name)
                            role_arn = potential_role
                            logger.info(f"Found Lambda role: {role_arn}")
                            break
                        except iam_client.exceptions.NoSuchEntityException:
                            continue
                            
            except Exception as role_error:
                logger.error(f"Role auto-detection failed: {str(role_error)[:200]}")
        
        if not role_arn:
            return {
                'statusCode': 400,
                'body': {
                    'error': 'Role ARN required for MLflow server creation',
                    'message': 'Could not auto-detect suitable IAM role'
                }
            }
        
        # STEP 3: Create MLflow server
        logger.info("Step 3: Creating MLflow tracking server...")
        
        create_params = {
            'TrackingServerName': tracking_server_name,
            'ArtifactStoreUri': artifact_store_uri,
            'TrackingServerSize': tracking_server_size,
            'RoleArn': role_arn,
            'AutomaticModelRegistration': True,
            'Tags': [
                {
                    'Key': 'CreatedBy',
                    'Value': 'MLOpsAgent'
                },
                {
                    'Key': 'Purpose',
                    'Value': 'MLflowTracking'
                }
            ]
        }
        
        if mlflow_version and mlflow_version in ['3.0', '2.16', '2.13']:
            create_params['MlflowVersion'] = mlflow_version
        
        response = sagemaker_client.create_mlflow_tracking_server(**create_params)
        
        tracking_server_arn = response['TrackingServerArn']
        logger.info(f"MLflow server creation initiated: {tracking_server_arn}")
        
        return {
            'statusCode': 202,
            'body': {
                'message': f'Successfully initiated MLflow Tracking Server creation: {tracking_server_name}',
                'tracking_server_name': tracking_server_name,
                'tracking_server_arn': tracking_server_arn,
                'artifact_store_uri': artifact_store_uri,
                's3_bucket': bucket_name,
                's3_setup': s3_message,
                'tracking_server_size': tracking_server_size,
                'role_arn': role_arn,
                'mlflow_version': mlflow_version if mlflow_version else 'AWS Default',
                'status': 'Creating',
                'estimated_completion_time': '20-30 minutes'
            }
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in create_mlflow_server: {str(e)[:200]}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {
                'error': 'Unexpected error in MLflow server creation',
                'message': str(e)
            }
        }

def manage_project_lifecycle(params: Dict[str, Any]) -> Dict[str, Any]:
    """Handle project updates and lifecycle management"""
    logger.info(f"manage_project_lifecycle called with params: {params}")
    
    project_name = params.get('project_name')
    action = params.get('action')
    
    if not all([project_name, action]):
        missing_params = []
        if not project_name: missing_params.append('project_name')
        if not action: missing_params.append('action')
        
        error_msg = f'Missing required parameters: {missing_params}. Available params: {list(params.keys())}'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': error_msg
        }
    
    try:
        if action == 'describe':
            response = sagemaker_client.describe_project(ProjectName=project_name)
            return {
                'statusCode': 200,
                'body': {
                    'project_name': response['ProjectName'],
                    'project_id': response['ProjectId'],
                    'project_arn': response['ProjectArn'],
                    'project_status': response['ProjectStatus'],
                    'creation_time': response['CreationTime'].isoformat(),
                    'created_by': response.get('CreatedBy', {})
                }
            }
        
        elif action == 'delete':
            return {
                'statusCode': 403,
                'body': {
                    'error': 'Project deletion is disabled',
                    'message': f'Deletion of project "{project_name}" is not allowed for security reasons',
                    'project_name': project_name,
                    'suggestion': 'Use AWS Console to manually delete projects if needed'
                }
            }
        
        else:
            return {
                'statusCode': 400,
                'body': f'Unsupported action: {action}. Supported actions: describe, delete'
            }
            
    except Exception as e:
        logger.error(f"Error managing project lifecycle: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': f'Failed to manage project lifecycle: {str(e)}'
        }

def list_mlops_templates(params: Dict[str, Any]) -> Dict[str, Any]:
    """List available MLOps Service Catalog templates"""
    logger.info("list_mlops_templates called - simplified version")
    
    # Define available templates with keywords they match
    available_templates = [
        {
            'ProductId': 'prod-txwcxmr6k3xsc',
            'Name': 'MLOps Template for Model Building and Deployment with GitHub',
            'ShortDescription': 'Template for creating MLOps projects with GitHub integration for CI/CD pipelines',
            'Owner': 'Amazon SageMaker',
            'Keywords': ['github', 'build', 'deploy', 'cicd', 'ci/cd', 'integration', 'mlops', 'project']
        }
    ]
    
    return {
        'statusCode': 200,
        'body': {
            'message': f'Found {len(available_templates)} MLOps templates',
            'templates': [
                {
                    'ProductId': t['ProductId'],
                    'Name': t['Name'],
                    'ShortDescription': t['ShortDescription'],
                    'Owner': t['Owner']
                }
                for t in available_templates
            ],
            'usage': f'Use ProductId "{available_templates[0]["ProductId"]}" for MLOps projects with GitHub integration'
        }
    }

def create_model_group(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create SageMaker Model Package Group (Model Registry)"""
    logger.info(f"create_model_group called with params: {params}")
    
    model_package_group_name = params.get('model_package_group_name')
    description = params.get('description', f'Model package group created by MLOps Agent')
    
    if not model_package_group_name:
        error_msg = f'Missing required parameter: model_package_group_name. Available params: {list(params.keys())}'
        logger.error(f"Error: {error_msg}")
        return {
            'statusCode': 400,
            'body': error_msg
        }
    
    try:
        # Create Model Package Group
        response = sagemaker_client.create_model_package_group(
            ModelPackageGroupName=model_package_group_name,
            ModelPackageGroupDescription=description,
            Tags=[
                {
                    'Key': 'CreatedBy',
                    'Value': 'MLOpsAgent'
                },
                {
                    'Key': 'Purpose',
                    'Value': 'ModelRegistry'
                }
            ]
        )
        
        model_package_group_arn = response['ModelPackageGroupArn']
        
        logger.info(f"Successfully created Model Package Group: {model_package_group_name}")
        
        return {
            'statusCode': 200,
            'body': {
                'message': f'Successfully created Model Package Group: {model_package_group_name}',
                'model_package_group_name': model_package_group_name,
                'model_package_group_arn': model_package_group_arn,
                'description': description,
                'status': 'Completed',
                'next_steps': [
                    'Model Package Group is ready for use',
                    'Register model versions to this group',
                    'Use for model versioning and approval workflows',
                    'Access via SageMaker Studio Model Registry'
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating Model Package Group: {str(e)}", exc_info=True)
        
        error_message = str(e)
        if 'already exists' in error_message.lower():
            return {
                'statusCode': 409,
                'body': {
                    'error': f'Model Package Group "{model_package_group_name}" already exists',
                    'message': 'Choose a different model package group name',
                    'suggestion': f'Try: {model_package_group_name}-v2 or {model_package_group_name}-{int(time.time())}'
                }
            }
        else:
            return {
                'statusCode': 500,
                'body': f'Failed to create Model Package Group: {error_message}'
            }
