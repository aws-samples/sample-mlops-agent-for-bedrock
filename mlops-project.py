import json
import boto3
import logging
import time
import subprocess
import os
import zipfile
import tempfile
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
sagemaker_client = boto3.client('sagemaker')
codeconnections_client = boto3.client('codeconnections')
servicecatalog_client = boto3.client('servicecatalog')
logs_client = boto3.client('logs')

def tag_mlops_log_groups():
    """
    Tag all MLOps-related log groups with CreatedBy: MLOpsAgent
    """
    try:
        # Patterns for MLOps-related log groups
        patterns = [
            '/aws/codebuild/sagemaker-mlops-',
            '/aws/lambda/sagemaker-p-',
            '/aws/sagemaker/mlflow/'
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
    
    # Add default CreatedBy tag
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
    """
    Main handler for MLOps project management actions
    """
    
    # Tag the Lambda log group on first execution
    try:
        log_group_name = f"/aws/lambda/{context.function_name}"
        tag_log_group(log_group_name, {
            'CreatedBy': 'MLOpsAgent',
            'Purpose': 'MLOpsAutomation'
        })
        
        # Tag other MLOps-related log groups
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
    
    logger.info("About to enter routing logic...")
    
    try:
        # Route to appropriate handler based on API path
        logger.info(f"Checking API path: '{api_path}'")
        if api_path == '/create-code-connection' or api_path == '/configure-code-connection':
            logger.info("Matched /configure-code-connection, calling create_code_connection")
            return create_code_connection(params)
        elif api_path == '/create-mlops-project':
            return create_mlops_project(params)
        elif api_path == '/build-cicd-pipeline':
            return build_cicd_pipeline(params)
        elif api_path == '/manage-model-approval':
            return manage_model_approval(params)
        elif api_path == '/manage-staging-approval':
            return manage_staging_approval(params)
        elif api_path == '/list-mlops-templates':
            return list_mlops_templates(params)
        elif api_path == '/create-feature-store-group':
            return create_feature_store_group(params)
        elif api_path == '/create-mlflow-tracking-server':
            return create_mlflow_tracking_server(params)
        elif api_path == '/manage-project-lifecycle':
            return manage_project_lifecycle(params)
        else:
            return {
                'statusCode': 400,
                'body': f'Unknown API path: {api_path}'
            }
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': f'Internal server error: {str(e)}'
        }

def extract_parameters_from_request_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract parameters from Bedrock Agent event structure
    """
    logger.info("Starting parameter extraction...")
    logger.info(f"Event keys: {list(event.keys())}")
    
    params = {}
    
    # Check for parameters array (newer format)
    if 'parameters' in event and isinstance(event['parameters'], list):
        logger.info(f"Found parameters array with {len(event['parameters'])} items")
        for param in event['parameters']:
            if isinstance(param, dict) and 'name' in param and 'value' in param:
                params[param['name']] = param['value']
                logger.info(f"Extracted parameter: {param['name']} = {param['value']}")
    
    # Check for requestBody (older format)
    if 'requestBody' in event:
        logger.info("Found requestBody in event")
        request_body = event['requestBody']
        
        if isinstance(request_body, dict):
            if 'content' in request_body:
                content = request_body['content']
                if 'application/json' in content:
                    json_content = content['application/json']
                    if 'properties' in json_content:
                        properties = json_content['properties']
                        for key, value_obj in properties.items():
                            if isinstance(value_obj, dict) and 'value' in value_obj:
                                params[key] = value_obj['value']
                                logger.info(f"Extracted from requestBody: {key} = {value_obj['value']}")
            else:
                # Direct properties in requestBody
                for key, value in request_body.items():
                    if isinstance(value, dict) and 'value' in value:
                        params[key] = value['value']
                    else:
                        params[key] = value
                    logger.info(f"Extracted direct from requestBody: {key} = {params[key]}")
    else:
        logger.info("No requestBody found in event (using parameters array)")
    
    logger.info(f"Final extracted parameters: {params}")
    return params

def create_code_connection(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create AWS CodeConnections connection for GitHub integration
    """
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
                },
                {
                    'Key': 'sagemaker',
                    'Value': 'true'
                }
            ]
        )
        
        logger.info(f"CodeConnections response: {json.dumps(response, default=str)}")
        
        connection_arn = response['ConnectionArn']
        connection_status = response.get('ConnectionStatus', 'PENDING')
        
        result = {
            'messageVersion': '1.0',
            'response': {
                'actionGroup': 'ProjectManagement',
                'apiPath': '/configure-code-connection',
                'httpMethod': 'POST',
                'httpStatusCode': 201,
                'responseBody': {
                    'application/json': {
                        'body': json.dumps({
                            'message': f'Successfully created CodeConnections connection: {connection_name}',
                            'connection_name': connection_name,
                            'connection_arn': connection_arn,
                            'connection_status': connection_status,
                            'provider_type': provider_type,
                            'next_steps': [
                                'Complete the connection setup in the AWS Console',
                                'Authorize the connection with your GitHub account',
                                'Verify the connection status shows as Available'
                            ]
                        })
                    }
                }
            }
        }
        
        logger.info(f"Returning result: {json.dumps(result, default=str)}")
        return result
        
    except Exception as e:
        logger.error(f"Error creating CodeConnections connection: {str(e)}", exc_info=True)
        
        error_message = str(e)
        if 'already exists' in error_message.lower():
            return {
                'statusCode': 409,
                'body': f'CodeConnections connection already exists: {connection_name}'
            }
        else:
            return {
                'statusCode': 500,
                'body': f'Failed to create CodeConnections connection: {error_message}'
            }

def create_mlops_project(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create SageMaker MLOps project using Service Catalog
    """
    logger.info(f"create_mlops_project called with params: {params}")
    
    project_name = params.get('project_name')
    github_username = params.get('github_username')
    github_repo_build = params.get('github_repo_build')
    github_repo_deploy = params.get('github_repo_deploy')
    connection_arn = params.get('connection_arn')
    
    if not all([project_name, github_username, github_repo_build, github_repo_deploy, connection_arn]):
        missing_params = []
        if not project_name: missing_params.append('project_name')
        if not github_username: missing_params.append('github_username')
        if not github_repo_build: missing_params.append('github_repo_build')
        if not github_repo_deploy: missing_params.append('github_repo_deploy')
        if not connection_arn: missing_params.append('connection_arn')
        
        return {
            'statusCode': 400,
            'body': f'Missing required parameters: {", ".join(missing_params)}'
        }
    
    try:
        logger.info("Step 1: Finding MLOps Service Catalog template...")
        
        # Search for the specific MLOps template dynamically using FullTextSearch
        target_template_name = "MLOps template for model building, training, and deployment with third-party Git repositories using CodePipeline"
        
        search_response = servicecatalog_client.search_products(
            Filters={
                'FullTextSearch': [target_template_name]
            }
        )
        
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
        
        if not product_id:
            raise Exception(f"Service Catalog template '{target_template_name}' not found in this account")
        
        # Verify the product still exists (optional check)
        try:
            artifacts_response = servicecatalog_client.list_provisioning_artifacts(
                ProductId=product_id
            )
            artifacts = artifacts_response.get('ProvisioningArtifactDetails', [])
            logger.info(f"Product verified: {len(artifacts)} artifacts available")
        except Exception as verify_error:
            logger.warning(f"Could not verify product (but will try anyway): {verify_error}")
        
        logger.info(f"Found template - Product ID: {product_id}, Artifact ID: {provisioning_artifact_id}")
        
        logger.info("Step 2: Setting up project parameters...")
        
        # Set up repository names
        model_build_code_repository_full_name = f"{github_username}/{github_repo_build}"
        model_deploy_code_repository_full_name = f"{github_username}/{github_repo_deploy}"
        
        logger.info(f"Build repo: {model_build_code_repository_full_name}")
        logger.info(f"Deploy repo: {model_deploy_code_repository_full_name}")
        
        # Configure project parameters for v2.1 template
        project_parameters = [
            {
                'Key': 'ModelBuildCodeRepositoryFullname',
                'Value': model_build_code_repository_full_name
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
        
        logger.info("Step 3: Creating SageMaker MLOps project...")
        
        project_response = sagemaker_client.create_project(
            ProjectName=project_name,
            ProjectDescription="MLOps project for model building and deployment with GitHub integration",
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
                    'Key': 'Purpose',
                    'Value': 'MLOpsAutomation'
                }
            ]
        )
        
        project_arn = project_response['ProjectArn']
        project_id = project_response['ProjectId']
        
        logger.info(f"Project creation initiated: {project_arn}")
        
        # Wait for project creation to complete
        logger.info("Waiting for project creation completion...")
        
        max_wait_time = 300  # 5 minutes
        wait_interval = 10   # 10 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                project_status_response = sagemaker_client.describe_project(ProjectName=project_name)
                current_status = project_status_response['ProjectStatus']
                
                logger.info(f"Current project status: {current_status} (elapsed: {elapsed_time}s)")
                
                if current_status == 'CreateCompleted':
                    logger.info("Project creation completed successfully!")
                    break
                elif current_status == 'CreateFailed':
                    logger.error("Project creation failed with status: CreateFailed")
                    return {
                        'statusCode': 500,
                        'body': {
                            'error': 'Project creation failed',
                            'message': 'Project creation failed with status: CreateFailed',
                            'project_name': project_name,
                            'project_id': project_id,
                            'status': current_status
                        }
                    }
                
                time.sleep(wait_interval)
                elapsed_time += wait_interval
                
            except Exception as status_error:
                logger.warning(f"Error checking project status: {status_error}")
                time.sleep(wait_interval)
                elapsed_time += wait_interval
        
        return {
            'statusCode': 201,
            'body': {
                'message': f'Successfully created MLOps project: {project_name}',
                'project_name': project_name,
                'project_arn': project_arn,
                'project_id': project_id,
                'build_repository': model_build_code_repository_full_name,
                'deploy_repository': model_deploy_code_repository_full_name,
                'connection_arn': connection_arn,
                'next_steps': [
                    'Check project status in SageMaker Studio',
                    'Verify GitHub repositories are populated with seed code',
                    'Review and customize the generated CI/CD pipelines',
                    'Test the model build and deployment workflows'
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating MLOps project: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': f'Failed to create MLOps project: {str(e)}'
        }

def create_mlflow_tracking_server(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create SageMaker MLflow Tracking Server
    """
    logger.info(f"create_mlflow_tracking_server called with params: {params}")
    
    tracking_server_name = params.get('tracking_server_name')
    artifact_store_uri = params.get('artifact_store_uri')
    server_size = params.get('server_size', 'Small')
    
    if not tracking_server_name:
        return {
            'statusCode': 400,
            'body': 'Missing required parameter: tracking_server_name'
        }
    
    try:
        # Validate and setup S3 bucket for artifact store
        if artifact_store_uri:
            bucket_valid, bucket_message, bucket_name = validate_and_setup_s3_bucket(artifact_store_uri)
            if not bucket_valid:
                return {
                    'statusCode': 400,
                    'body': f'S3 bucket validation failed: {bucket_message}'
                }
            s3_message = bucket_message
        else:
            # Create default artifact store URI
            try:
                sts_client = boto3.client('sts')
                account_id = sts_client.get_caller_identity()['Account']
                bucket_name = f"mlflow-artifacts-{account_id}"
                artifact_store_uri = f"s3://{bucket_name}/mlflow/"
                
                bucket_valid, bucket_message, _ = validate_and_setup_s3_bucket(artifact_store_uri)
                if not bucket_valid:
                    return {
                        'statusCode': 400,
                        'body': f'Failed to create default S3 bucket: {bucket_message}'
                    }
                s3_message = bucket_message
            except Exception as bucket_error:
                return {
                    'statusCode': 500,
                    'body': f'Failed to setup S3 bucket: {str(bucket_error)}'
                }
        
        # Create MLflow Tracking Server
        create_params = {
            'TrackingServerName': tracking_server_name,
            'ArtifactStoreUri': artifact_store_uri,
            'TrackingServerSize': server_size,
            'Tags': [
                {
                    'Key': 'CreatedBy',
                    'Value': 'MLOpsAgent'
                },
                {
                    'Key': 'Purpose',
                    'Value': 'MLOpsAutomation'
                }
            ]
        }
        
        # Add role ARN if available
        role_arn = get_sagemaker_execution_role()
        if role_arn:
            create_params['RoleArn'] = role_arn
            logger.info(f"Using execution role: {role_arn}")
        else:
            logger.warning("No suitable execution role found, proceeding without explicit role")
            
        # Create MLflow Tracking Server
        response = sagemaker_client.create_mlflow_tracking_server(**create_params)
        
        tracking_server_arn = response['TrackingServerArn']
        logger.info(f"MLflow server creation initiated: {tracking_server_arn}")
        
        # Tag the MLflow CloudWatch log group
        try:
            log_group_name = f"/aws/sagemaker/mlflow/{tracking_server_name}"
            tag_log_group(log_group_name, {
                'CreatedBy': 'MLOpsAgent',
                'sagemaker': 'true',
                'mlflow': 'true'
            })
        except Exception as e:
            logger.warning(f"Could not tag MLflow log group: {str(e)}")
        
        return {
            'statusCode': 202,
            'body': {
                'message': f'Successfully initiated MLflow Tracking Server creation: {tracking_server_name}',
                'tracking_server_name': tracking_server_name,
                'tracking_server_arn': tracking_server_arn,
                'artifact_store_uri': artifact_store_uri,
                's3_bucket': bucket_name,
                's3_setup': s3_message,
                'server_size': server_size,
                'status': 'Creating',
                'next_steps': [
                    'Wait for tracking server to become available (this may take several minutes)',
                    'Check server status in SageMaker console',
                    'Configure MLflow client to use the tracking server URL',
                    'Start logging experiments and models'
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error creating MLflow Tracking Server: {str(e)}", exc_info=True)
        
        error_message = str(e)
        if 'already exists' in error_message.lower():
            return {
                'statusCode': 409,
                'body': f'MLflow Tracking Server already exists: {tracking_server_name}'
            }
        else:
            return {
                'statusCode': 500,
                'body': f'Failed to create MLflow Tracking Server: {error_message}'
            }

def validate_and_setup_s3_bucket(s3_uri: str) -> tuple[bool, str, Optional[str]]:
    """
    Validate S3 URI and create bucket if it doesn't exist
    Returns: (is_valid, message, bucket_name)
    """
    try:
        # Parse S3 URI
        if not s3_uri.startswith('s3://'):
            return False, "Invalid S3 URI format - must start with s3://", None
        
        # Extract bucket name from URI
        uri_parts = s3_uri[5:].split('/', 1)  # Remove 's3://' prefix
        if not uri_parts[0]:
            return False, "Invalid S3 URI - no bucket name found", None
        
        bucket_name = uri_parts[0]
        
        s3_client = boto3.client('s3')
        
        # Check if bucket exists and is accessible
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            return True, f"Using existing S3 bucket: {bucket_name}", bucket_name
            
        except s3_client.exceptions.NoSuchBucket:
            # Bucket doesn't exist, try to create it
            logger.info(f"Bucket {bucket_name} doesn't exist, attempting to create...")
            
            try:
                # Get current region
                session = boto3.Session()
                current_region = session.region_name or 'us-east-1'
                
                if current_region == 'us-east-1':
                    # us-east-1 doesn't need LocationConstraint
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': current_region}
                    )
                
                # Add tags to the bucket
                s3_client.put_bucket_tagging(
                    Bucket=bucket_name,
                    Tagging={
                        'TagSet': [
                            {'Key': 'CreatedBy', 'Value': 'MLOpsAgent'},
                            {'Key': 'Purpose', 'Value': 'MLOpsAutomation'}
                        ]
                    }
                )
                
                return True, f"Successfully created S3 bucket: {bucket_name}", bucket_name
                
            except Exception as create_error:
                logger.error(f"Failed to create bucket {bucket_name}: {create_error}")
                
                # Handle bucket name conflicts
                if 'BucketAlreadyExists' in str(create_error) or 'already exists' in str(create_error).lower():
                    # Suggest alternative bucket names
                    try:
                        account_id = boto3.client('sts').get_caller_identity()['Account']
                        timestamp = int(time.time())
                        
                        suggested_names = [
                            f"{bucket_name}-{account_id}",
                            f"{bucket_name}-{timestamp}",
                            f"{bucket_name}-{account_id}-{timestamp}"
                        ]
                        
                        return False, f"Bucket name '{bucket_name}' already exists globally. Try one of these alternatives: {', '.join(suggested_names)}", None
                        
                    except Exception:
                        return False, f"Bucket name '{bucket_name}' already exists globally. Please choose a different name.", None
                else:
                    return False, f"Failed to create bucket: {str(create_error)}", None
                    
        except Exception as head_error:
            # Check if it's a permissions issue vs bucket owned by another account
            if 'Forbidden' in str(head_error) or '403' in str(head_error):
                logger.error(f"Bucket {bucket_name} exists but is owned by another account")
                
                try:
                    account_id = boto3.client('sts').get_caller_identity()['Account']
                    timestamp = int(time.time())
                    
                    suggested_names = [
                        f"{bucket_name}-{account_id}",
                        f"{bucket_name}-{timestamp}",
                        f"{bucket_name}-{account_id}-{timestamp}"
                    ]
                    
                    return False, f"Bucket '{bucket_name}' is owned by another account. Try one of these alternatives: {', '.join(suggested_names)}", None
                    
                except Exception:
                    return False, f"Bucket '{bucket_name}' is owned by another account. Please choose a different name.", None
            else:
                return False, f"Error accessing bucket: {str(head_error)}", None
                
    except Exception as e:
        logger.error(f"Error validating S3 URI: {str(e)}")
        return False, f"Error validating S3 URI: {str(e)}", None

def get_sagemaker_execution_role() -> Optional[str]:
    """
    Get or create a suitable SageMaker execution role
    """
    try:
        iam_client = boto3.client('iam')
        
        # Try to find existing SageMaker execution roles
        role_arn = None
        
        if not role_arn:
            try:
                sts_client = boto3.client('sts')
                caller_identity = sts_client.get_caller_identity()
                account_id = caller_identity['Account']
                
                # Try common SageMaker role names
                possible_roles = [
                    f"arn:aws:iam::{account_id}:role/service-role/AmazonSageMaker-ExecutionRole",
                    f"arn:aws:iam::{account_id}:role/SageMakerExecutionRole",
                    f"arn:aws:iam::{account_id}:role/sagemaker-execution-role",
                    f"arn:aws:iam::{account_id}:role/lambda-execution-role"
                ]
                
                iam_client = boto3.client('iam')
                for potential_role in possible_roles:
                    try:
                        role_name = potential_role.split('/')[-1]
                        iam_client.get_role(RoleName=role_name)
                        role_arn = potential_role
                        logger.info(f"Found existing role: {role_arn}")
                        break
                    except iam_client.exceptions.NoSuchEntityException:
                        continue
                        
            except Exception as role_error:
                logger.warning(f"Could not determine execution role: {role_error}")
        
        return role_arn
        
    except Exception as e:
        logger.warning(f"Error getting SageMaker execution role: {str(e)}")
        return None

def list_mlops_templates(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    List available MLOps Service Catalog templates
    """
    logger.info(f"list_mlops_templates called with params: {params}")
    
    # Dynamically discover available MLOps templates using FullTextSearch
    try:
        # Search for MLOps templates using FullTextSearch
        mlops_search_terms = [
            "MLOps template for model building, training, and deployment with third-party Git repositories using CodePipeline",
            "MLOps",
            "SageMaker"
        ]
        
        available_templates = []
        found_products = set()  # Track unique products
        
        for search_term in mlops_search_terms:
            try:
                search_response = servicecatalog_client.search_products(
                    Filters={
                        'FullTextSearch': [search_term]
                    }
                )
                
                for product in search_response.get('ProductViewSummaries', []):
                    # Only add MLOps-related products and avoid duplicates
                    if (product['ProductId'] not in found_products and 
                        ('mlops' in product['Name'].lower() or 'sagemaker' in product['Name'].lower())):
                        
                        available_templates.append({
                            'ProductId': product['ProductId'],
                            'Name': product['Name'],
                            'ShortDescription': product.get('ShortDescription', 'MLOps template for CI/CD pipelines'),
                            'Owner': product.get('Owner', 'Amazon SageMaker'),
                            'Keywords': ['github', 'build', 'deploy', 'cicd', 'ci/cd', 'integration', 'mlops', 'project']
                        })
                        found_products.add(product['ProductId'])
                        
            except Exception as search_error:
                logger.warning(f"Error searching for '{search_term}': {str(search_error)}")
                
    except Exception as e:
        logger.error(f"Error discovering Service Catalog templates: {str(e)}")
        # Fallback to empty list if discovery fails
        available_templates = []
    
    # Get the user's input text from the event (if available)
    user_input = ""
    try:
        user_input = params.get('query', '').lower()
    except:
        pass
    
    # For now, just return all available templates since it's mainly for testing
    templates_to_return = available_templates
    
    # Simple response
    return {
        'statusCode': 200,
        'body': {
            'message': f'Found {len(templates_to_return)} MLOps templates',
            'templates': templates_to_return,
            'total_count': len(templates_to_return)
        }
    }

# Additional functions would continue here...
# This is a condensed version focusing on the key updated functions

if __name__ == "__main__":
    # Test the functions locally if needed
    pass
