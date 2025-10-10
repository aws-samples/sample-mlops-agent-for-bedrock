#!/bin/bash

# MLOps Bedrock Agent - Resource Discovery
# Find all MLOps-related resources in your AWS account

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 MLOps Bedrock Agent - Resource Discovery${NC}"
echo "=============================================="
echo ""

# Get AWS account and region info
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")
AWS_REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

echo "AWS Account: $AWS_ACCOUNT"
echo "AWS Region: $AWS_REGION"
echo ""
echo -e "${YELLOW}📋 Discovering resources with 'mlops' in their name that would be tagged...${NC}"
echo ""

total_resources=0

# Function to list resources
list_resources() {
    local resource_type=$1
    local resources=$2
    local count=0
    
    echo -e "${BLUE}$resource_type:${NC}"
    if [ -n "$resources" ] && [ "$resources" != "" ]; then
        for resource in $resources; do
            echo "  • $resource"
            ((count++))
            ((total_resources++))
        done
    else
        echo "  (none found)"
    fi
    echo "  Total: $count"
    echo ""
}

# Function to list resources with MLOps filtering
list_mlops_resources() {
    local resource_type=$1
    local resources=$2
    local count=0
    
    echo -e "${BLUE}$resource_type:${NC}"
    if [ -n "$resources" ] && [ "$resources" != "" ]; then
        for resource in $resources; do
            # Only show resources with "mlops" in the name (case insensitive)
            if [[ "${resource,,}" == *"mlops"* ]]; then
                echo "  • $resource"
                ((count++))
                ((total_resources++))
            fi
        done
    else
        echo "  (none found)"
    fi
    echo "  Total: $count"
    echo ""
}

# Lambda Functions
echo -e "${BLUE}🔄 Scanning Lambda Functions${NC}"
lambda_functions=$(aws lambda list-functions --query 'Functions[?contains(FunctionName, `mlops`)].FunctionName' --output text 2>/dev/null || echo "")
list_resources "Lambda Functions" "$lambda_functions"

# S3 Buckets
echo -e "${BLUE}🔄 Scanning S3 Buckets${NC}"
s3_buckets=$(aws s3api list-buckets --query 'Buckets[?contains(Name, `mlops`)].Name' --output text 2>/dev/null || echo "")
list_resources "S3 Buckets" "$s3_buckets"

# IAM Roles
echo -e "${BLUE}🔄 Scanning IAM Roles${NC}"
iam_roles=$(aws iam list-roles --query 'Roles[?contains(RoleName, `mlops`)].RoleName' --output text 2>/dev/null || echo "")
list_resources "IAM Roles" "$iam_roles"

# Bedrock Agents
echo -e "${BLUE}🔄 Scanning Bedrock Agents${NC}"
bedrock_agents=$(aws bedrock-agent list-agents --query 'agentSummaries[].agentId' --output text 2>/dev/null || echo "")
if [ -n "$bedrock_agents" ] && [ "$bedrock_agents" != "" ]; then
    echo -e "${BLUE}Bedrock Agents:${NC}"
    agent_count=0
    for agent_id in $bedrock_agents; do
        agent_name=$(aws bedrock-agent get-agent --agent-id "$agent_id" --query 'agent.agentName' --output text 2>/dev/null || echo "unknown")
        
        # Only show agents with "mlops" in the name (case insensitive)
        if [[ "${agent_name,,}" == *"mlops"* ]]; then
            echo "  • $agent_name ($agent_id)"
            ((agent_count++))
            ((total_resources++))
        fi
    done
    echo "  Total: $agent_count"
else
    echo -e "${BLUE}Bedrock Agents:${NC}"
    echo "  (none found)"
    echo "  Total: 0"
fi
echo ""

# SageMaker Projects
echo -e "${BLUE}🔄 Scanning SageMaker Projects${NC}"
sagemaker_projects=$(aws sagemaker list-projects --query 'ProjectSummaryList[].ProjectName' --output text 2>/dev/null || echo "")
list_mlops_resources "SageMaker Projects" "$sagemaker_projects"

# Model Package Groups
echo -e "${BLUE}🔄 Scanning Model Package Groups${NC}"
model_groups=$(aws sagemaker list-model-package-groups --query 'ModelPackageGroupSummaryList[].ModelPackageGroupName' --output text 2>/dev/null || echo "")
list_mlops_resources "Model Package Groups" "$model_groups"

# CodeStar Connections
echo -e "${BLUE}🔄 Scanning CodeStar Connections${NC}"
codestar_connections=$(aws codeconnections list-connections --query 'Connections[].ConnectionName' --output text 2>/dev/null || echo "")
list_mlops_resources "CodeStar Connections" "$codestar_connections"

# CodeBuild Projects (created by SageMaker projects)
echo -e "${BLUE}🔄 Scanning CodeBuild Projects${NC}"
codebuild_projects=$(aws codebuild list-projects --query 'projects[]' --output text 2>/dev/null || echo "")
list_mlops_resources "CodeBuild Projects" "$codebuild_projects"

# CodePipeline Pipelines (created by SageMaker projects)
echo -e "${BLUE}🔄 Scanning CodePipeline Pipelines${NC}"
codepipeline_pipelines=$(aws codepipeline list-pipelines --query 'pipelines[].name' --output text 2>/dev/null || echo "")
list_mlops_resources "CodePipeline Pipelines" "$codepipeline_pipelines"

# SageMaker Inference Endpoints (created by deployment pipelines)
echo -e "${BLUE}🔄 Scanning SageMaker Endpoints${NC}"
sagemaker_endpoints=$(aws sagemaker list-endpoints --query 'Endpoints[].EndpointName' --output text 2>/dev/null || echo "")
list_mlops_resources "SageMaker Endpoints" "$sagemaker_endpoints"

# SageMaker Pipelines
echo -e "${BLUE}🔄 Scanning SageMaker Pipelines${NC}"
sagemaker_pipelines=$(aws sagemaker list-pipelines --query 'PipelineSummaries[].PipelineName' --output text 2>/dev/null || echo "")
list_mlops_resources "SageMaker Pipelines" "$sagemaker_pipelines"

# SageMaker Models
echo -e "${BLUE}🔄 Scanning SageMaker Models${NC}"
sagemaker_models=$(aws sagemaker list-models --query 'Models[].ModelName' --output text 2>/dev/null || echo "")
list_mlops_resources "SageMaker Models" "$sagemaker_models"

# SageMaker Endpoint Configurations
echo -e "${BLUE}🔄 Scanning SageMaker Endpoint Configurations${NC}"
endpoint_configs=$(aws sagemaker list-endpoint-configs --query 'EndpointConfigs[].EndpointConfigName' --output text 2>/dev/null || echo "")
list_mlops_resources "SageMaker Endpoint Configurations" "$endpoint_configs"

# MLflow Tracking Servers
echo -e "${BLUE}🔄 Scanning MLflow Tracking Servers${NC}"
mlflow_servers=$(aws sagemaker list-mlflow-tracking-servers --query 'TrackingServerSummaries[].TrackingServerName' --output text 2>/dev/null || echo "")
list_mlops_resources "MLflow Tracking Servers" "$mlflow_servers"

# ECR Repositories
echo -e "${BLUE}🔄 Scanning ECR Repositories${NC}"
ecr_repos=$(aws ecr describe-repositories --query 'repositories[].repositoryName' --output text 2>/dev/null || echo "")
list_mlops_resources "ECR Repositories" "$ecr_repos"

# EventBridge Rules
echo -e "${BLUE}🔄 Scanning EventBridge Rules${NC}"
eventbridge_rules=$(aws events list-rules --query 'Rules[].Name' --output text 2>/dev/null || echo "")
list_mlops_resources "EventBridge Rules" "$eventbridge_rules"

# CloudFormation Stacks (SageMaker projects create these)
echo -e "${BLUE}🔄 Scanning CloudFormation Stacks${NC}"
cfn_stacks=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'StackSummaries[].StackName' --output text 2>/dev/null || echo "")
list_mlops_resources "CloudFormation Stacks" "$cfn_stacks"

echo "=============================================="
echo -e "${GREEN}📊 Summary${NC}"
echo "Total resources found: $total_resources"
echo ""
if [ $total_resources -gt 0 ]; then
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Manually tag these resources in AWS Console with CreatedBy=MLOpsAgent"
    echo "2. Run ./cleanup-by-tags.sh to clean them up later"
else
    echo -e "${YELLOW}No resources found with 'mlops' in their name.${NC}"
    echo "This could mean:"
    echo "• No MLOps resources are deployed"
    echo "• Resources use different naming conventions (don't contain 'mlops')"
    echo "• AWS CLI is not configured properly"
fi
echo ""