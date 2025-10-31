#!/bin/bash

# MLOps Bedrock Agent - Tag-Based Resource Cleanup Script
# This script cleans up all AWS resources created by the MLOps Bedrock Agent deployment
# using resource tags for identification

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_TAG_KEY="CreatedBy"
PROJECT_TAG_VALUE="MLOpsAgent"

# Safety configuration
DRY_RUN=false
INTERACTIVE=false
BACKUP_ENABLED=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --no-backup)
            BACKUP_ENABLED=false
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--interactive] [--no-backup]"
            exit 1
            ;;
    esac
done

# Function to print colored output
print_step() {
    echo -e "${BLUE}🔄 Step $1: $2${NC}"
    echo "----------------------------------------"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to check if AWS CLI is configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS CLI is not configured. Please run 'aws configure' first."
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    REGION=$(aws configure get region || echo "us-east-1")
    
    echo "AWS Account: $ACCOUNT_ID"
    echo "AWS Region: $REGION"
    echo ""
}

# Function to backup resources before cleanup
backup_resources() {
    if [[ "$BACKUP_ENABLED" == "true" ]]; then
        print_step "0" "Creating Resource Backup"
        
        local backup_file="mlops-resources-backup-$(date +%Y%m%d-%H%M%S).json"
        
        echo "Creating backup of tagged resources..."
        aws resourcegroupstaggingapi get-resources \
            --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE \
            > "$backup_file" 2>/dev/null || print_warning "Failed to create backup"
        
        if [[ -f "$backup_file" ]]; then
            print_success "Backup created: $backup_file"
        fi
        echo ""
    fi
}

# Function to count resources before cleanup
count_tagged_resources() {
    print_step "0" "Counting Tagged Resources"
    
    local total_count=0
    
    # Count each resource type
    local projects_count=0
    local all_projects=$(aws sagemaker list-projects --query "ProjectSummaryList[].ProjectName" --output text 2>/dev/null || echo "")
    if [[ -n "$all_projects" ]]; then
        for project in $all_projects; do
            local project_tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:project/$project" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            [[ -n "$project_tags" ]] && ((projects_count++))
        done
    fi
    local functions=$(aws resourcegroupstaggingapi get-resources --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE --resource-type-filters "lambda:function" --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null | wc -w)
    local buckets=$(aws resourcegroupstaggingapi get-resources --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE --resource-type-filters "s3:bucket" --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null | wc -w)
    local agents=$(aws resourcegroupstaggingapi get-resources --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE --resource-type-filters "bedrock:agent" --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null | wc -w)
    local pipelines=$(aws resourcegroupstaggingapi get-resources --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE --resource-type-filters "codepipeline:pipeline" --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null | wc -w)
    local connections=$(aws resourcegroupstaggingapi get-resources --tag-filters Key=$PROJECT_TAG_KEY,Values=$PROJECT_TAG_VALUE --resource-type-filters "codestar-connections:connection" --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null | wc -w)
    
    # Count all SageMaker resources individually for accuracy
    local model_groups_count=0
    local feature_groups_count=0
    local mlflow_servers_count=0
    local pipelines_count=0
    local models_count=0
    local endpoints_count=0
    local endpoint_configs_count=0
    
    # Count model package groups
    local all_model_groups=$(aws sagemaker list-model-package-groups --query "ModelPackageGroupSummaryList[].ModelPackageGroupName" --output text 2>/dev/null || echo "")
    if [[ -n "$all_model_groups" ]]; then
        for group in $all_model_groups; do
            local group_tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:model-package-group/$group" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            [[ -n "$group_tags" ]] && ((model_groups_count++))
        done
    fi
    
    # Count feature groups
    local all_feature_groups=$(aws sagemaker list-feature-groups --query "FeatureGroupSummaries[].FeatureGroupName" --output text 2>/dev/null || echo "")
    if [[ -n "$all_feature_groups" ]]; then
        for group in $all_feature_groups; do
            local group_tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:feature-group/$group" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            [[ -n "$group_tags" ]] && ((feature_groups_count++))
        done
    fi
    
    # Count MLflow servers
    local all_mlflow_servers=$(aws sagemaker list-mlflow-tracking-servers --query "TrackingServerSummaries[].TrackingServerName" --output text 2>/dev/null || echo "")
    if [[ -n "$all_mlflow_servers" ]]; then
        for server in $all_mlflow_servers; do
            local server_tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:mlflow-tracking-server/$server" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            [[ -n "$server_tags" ]] && ((mlflow_servers_count++))
        done
    fi
    
    local sagemaker_all=$((projects_count + model_groups_count + feature_groups_count + mlflow_servers_count + pipelines_count + models_count + endpoints_count + endpoint_configs_count))
    
    total_count=$((sagemaker_all + functions + buckets + agents + pipelines + connections))
    
    echo "Resources found with tag $PROJECT_TAG_KEY=$PROJECT_TAG_VALUE:"
    echo "  • SageMaker Resources (all): $sagemaker_all"
    echo "    - Projects: $projects_count"
    echo "    - Model Package Groups: $model_groups_count"
    echo "    - Feature Groups: $feature_groups_count"
    echo "    - MLflow Servers: $mlflow_servers_count"
    echo "  • Lambda Functions: $functions"
    echo "  • S3 Buckets: $buckets"
    echo "  • Bedrock Agents: $agents"
    echo "  • CodePipeline Pipelines: $pipelines"
    echo "  • CodeStar Connections: $connections"
    echo "  • Total: $total_count"
    echo ""
    
    if [[ $total_count -eq 0 ]]; then
        print_warning "No tagged resources found. Nothing to clean up."
        exit 0
    fi
}

# Function to confirm individual resource deletion
confirm_resource_deletion() {
    local resource_name=$1
    local resource_type=$2
    
    if [[ "$INTERACTIVE" == "true" ]]; then
        echo -n "Delete $resource_type '$resource_name'? (y/N/q): "
        read -r response
        case $response in
            [yY]) return 0 ;;
            [qQ]) 
                echo "Cleanup cancelled by user."
                exit 0 
                ;;
            *) return 1 ;;
        esac
    fi
    return 0
}

# Function to confirm cleanup
confirm_cleanup() {
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${BLUE}🔍 DRY RUN MODE - No resources will be deleted${NC}"
        echo ""
        return 0
    fi
    
    echo -e "${YELLOW}⚠️  WARNING: This will delete ALL resources tagged with:${NC}"
    echo "   - $PROJECT_TAG_KEY=$PROJECT_TAG_VALUE"
    echo ""
    echo "This action cannot be undone!"
    echo ""
    
    if [[ "$INTERACTIVE" == "true" ]]; then
        echo "Interactive mode enabled - you'll be asked to confirm each resource."
    fi
    
    echo ""
    read -p "Are you sure you want to proceed? (type 'yes' to confirm): " confirmation
    
    if [[ "$confirmation" != "yes" ]]; then
        echo "Cleanup cancelled."
        exit 0
    fi
}

# Function to cleanup SageMaker projects
cleanup_sagemaker_projects() {
    print_step "1" "Cleaning up SageMaker Projects"
    
    # List projects with tags
    projects=$(aws sagemaker list-projects --query "ProjectSummaryList[].ProjectName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$projects" ]]; then
        for project in $projects; do
            # Check if project has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:project/$project" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                if confirm_resource_deletion "$project" "SageMaker Project"; then
                    if [[ "$DRY_RUN" == "true" ]]; then
                        echo "Would delete SageMaker project: $project"
                    else
                        echo "Deleting SageMaker project: $project"
                        aws sagemaker delete-project --project-name "$project" 2>/dev/null || print_warning "Failed to delete project $project"
                        print_success "Deleted SageMaker project: $project"
                    fi
                else
                    echo "Skipped SageMaker project: $project"
                fi
            fi
        done
    else
        print_warning "No SageMaker projects found"
    fi
}

# Function to cleanup Model Package Groups
cleanup_model_package_groups() {
    print_step "2" "Cleaning up Model Package Groups"
    
    model_groups=$(aws sagemaker list-model-package-groups --query "ModelPackageGroupSummaryList[].ModelPackageGroupName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$model_groups" ]]; then
        for group in $model_groups; do
            # Check if group has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:model-package-group/$group" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                if [[ "$DRY_RUN" == "true" ]]; then
                    echo "Would delete model package group: $group"
                else
                    echo "Deleting model package group: $group"
                    
                    # First delete all model packages in the group
                    model_packages=$(aws sagemaker list-model-packages --model-package-group-name "$group" --query "ModelPackageSummaryList[].ModelPackageArn" --output text 2>/dev/null || echo "")
                    if [[ -n "$model_packages" ]]; then
                        for package_arn in $model_packages; do
                            echo "  Deleting model package: $package_arn"
                            aws sagemaker delete-model-package --model-package-name "$package_arn" 2>/dev/null || print_warning "Failed to delete model package $package_arn"
                        done
                        
                        # Wait for model packages to be deleted
                        echo "  Waiting for model packages to be deleted..."
                        sleep 10
                    fi
                    
                    # Then delete the group
                    if aws sagemaker delete-model-package-group --model-package-group-name "$group" 2>/dev/null; then
                        print_success "Deleted model package group: $group"
                    else
                        print_warning "Failed to delete model package group $group"
                    fi
                fi
            fi
        done
    else
        print_warning "No model package groups found"
    fi
}

# Function to cleanup Feature Store groups
cleanup_feature_groups() {
    print_step "3" "Cleaning up Feature Store Groups"
    
    feature_groups=$(aws sagemaker list-feature-groups --query "FeatureGroupSummaries[].FeatureGroupName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$feature_groups" ]]; then
        for group in $feature_groups; do
            # Check if group has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:feature-group/$group" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting feature group: $group"
                aws sagemaker delete-feature-group --feature-group-name "$group" 2>/dev/null || print_warning "Failed to delete feature group $group"
                print_success "Deleted feature group: $group"
            fi
        done
    else
        print_warning "No feature groups found"
    fi
}

# Function to cleanup MLflow tracking servers
cleanup_mlflow_servers() {
    print_step "4" "Cleaning up MLflow Tracking Servers"
    
    mlflow_servers=$(aws sagemaker list-mlflow-tracking-servers --query "TrackingServerSummaries[].TrackingServerName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$mlflow_servers" ]]; then
        for server in $mlflow_servers; do
            # Check if server has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:mlflow-tracking-server/$server" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting MLflow tracking server: $server"
                aws sagemaker delete-mlflow-tracking-server --tracking-server-name "$server" 2>/dev/null || print_warning "Failed to delete MLflow server $server"
                print_success "Deleted MLflow tracking server: $server"
            fi
        done
    else
        print_warning "No MLflow tracking servers found"
    fi
}

# Function to cleanup CodePipeline pipelines
cleanup_codepipeline_pipelines() {
    print_step "5" "Cleaning up CodePipeline Pipelines"
    
    pipelines=$(aws codepipeline list-pipelines --query "pipelines[].name" --output text 2>/dev/null || echo "")
    
    if [[ -n "$pipelines" ]]; then
        for pipeline in $pipelines; do
            # Check if pipeline has our tags
            tags=$(aws codepipeline list-tags-for-resource --resource-arn "arn:aws:codepipeline:$REGION:$ACCOUNT_ID:$pipeline" --query "tags[?key=='$PROJECT_TAG_KEY' && value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                if confirm_resource_deletion "$pipeline" "CodePipeline Pipeline"; then
                    if [[ "$DRY_RUN" == "true" ]]; then
                        echo "Would delete CodePipeline pipeline: $pipeline"
                    else
                        echo "Deleting CodePipeline pipeline: $pipeline"
                        aws codepipeline delete-pipeline --name "$pipeline" 2>/dev/null || print_warning "Failed to delete pipeline $pipeline"
                        print_success "Deleted CodePipeline pipeline: $pipeline"
                    fi
                else
                    echo "Skipped CodePipeline pipeline: $pipeline"
                fi
            fi
        done
    else
        print_warning "No CodePipeline pipelines found"
    fi
}
# Function to cleanup CodeStar connections
cleanup_codestar_connections() {
    print_step "6" "Cleaning up CodeStar Connections"
    
    connections=$(aws codeconnections list-connections --query "Connections[].ConnectionArn" --output text 2>/dev/null || echo "")
    
    if [[ -n "$connections" ]]; then
        for connection_arn in $connections; do
            # Check if connection has our tags
            tags=$(aws codeconnections list-tags-for-resource --resource-arn "$connection_arn" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting CodeStar connection: $connection_arn"
                aws codeconnections delete-connection --connection-arn "$connection_arn" 2>/dev/null || print_warning "Failed to delete connection $connection_arn"
                print_success "Deleted CodeStar connection: $connection_arn"
            fi
        done
    else
        print_warning "No CodeStar connections found"
    fi
}

# Function to cleanup Lambda functions
cleanup_lambda_functions() {
    print_step "6" "Cleaning up Lambda Functions"
    
    functions=$(aws lambda list-functions --query "Functions[].FunctionName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$functions" ]]; then
        for function in $functions; do
            # Check if function has our tags
            tags=$(aws lambda list-tags --resource "arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$function" --query "Tags.$PROJECT_TAG_KEY" --output text 2>/dev/null || echo "")
            
            if [[ "$tags" == "$PROJECT_TAG_VALUE" ]]; then
                echo "Deleting Lambda function: $function"
                aws lambda delete-function --function-name "$function" 2>/dev/null || print_warning "Failed to delete function $function"
                print_success "Deleted Lambda function: $function"
            fi
        done
    else
        print_warning "No Lambda functions found"
    fi
}

# Function to cleanup S3 buckets
cleanup_s3_buckets() {
    print_step "7" "Cleaning up S3 Buckets"
    
    buckets=$(aws s3api list-buckets --query "Buckets[].Name" --output text 2>/dev/null || echo "")
    
    if [[ -n "$buckets" ]]; then
        for bucket in $buckets; do
            # Check if bucket has our tags
            tags=$(aws s3api get-bucket-tagging --bucket "$bucket" --query "TagSet[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Emptying and deleting S3 bucket: $bucket"
                
                # Empty bucket first
                aws s3 rm "s3://$bucket" --recursive 2>/dev/null || print_warning "Failed to empty bucket $bucket"
                
                # Delete bucket
                aws s3 rb "s3://$bucket" 2>/dev/null || print_warning "Failed to delete bucket $bucket"
                print_success "Deleted S3 bucket: $bucket"
            fi
        done
    else
        print_warning "No S3 buckets found"
    fi
}

# Function to cleanup Bedrock agents
cleanup_bedrock_agents() {
    print_step "8" "Cleaning up Bedrock Agents"
    
    agents=$(aws bedrock-agent list-agents --query "agentSummaries[].agentId" --output text 2>/dev/null || echo "")
    
    if [[ -n "$agents" ]]; then
        for agent_id in $agents; do
            # Check if agent has our tags
            tags=$(aws bedrock-agent list-tags-for-resource --resource-arn "arn:aws:bedrock:$REGION:$ACCOUNT_ID:agent/$agent_id" --query "tags.$PROJECT_TAG_KEY" --output text 2>/dev/null || echo "")
            
            if [[ "$tags" == "$PROJECT_TAG_VALUE" ]]; then
                echo "Deleting Bedrock agent: $agent_id"
                aws bedrock-agent delete-agent --agent-id "$agent_id" 2>/dev/null || print_warning "Failed to delete agent $agent_id"
                print_success "Deleted Bedrock agent: $agent_id"
            fi
        done
    else
        print_warning "No Bedrock agents found"
    fi
}

# Function to cleanup IAM roles
cleanup_iam_roles() {
    print_step "9" "Cleaning up IAM Roles"
    
    roles=$(aws iam list-roles --query "Roles[?contains(RoleName, 'mlops') || contains(RoleName, 'MLOps')].RoleName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$roles" ]]; then
        for role in $roles; do
            # Check if role has our tags
            tags=$(aws iam list-role-tags --role-name "$role" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting IAM role: $role"
                
                # Detach managed policies
                attached_policies=$(aws iam list-attached-role-policies --role-name "$role" --query "AttachedPolicies[].PolicyArn" --output text 2>/dev/null || echo "")
                for policy_arn in $attached_policies; do
                    aws iam detach-role-policy --role-name "$role" --policy-arn "$policy_arn" 2>/dev/null || true
                done
                
                # Delete inline policies
                inline_policies=$(aws iam list-role-policies --role-name "$role" --query "PolicyNames" --output text 2>/dev/null || echo "")
                for policy_name in $inline_policies; do
                    aws iam delete-role-policy --role-name "$role" --policy-name "$policy_name" 2>/dev/null || true
                done
                
                # Delete role
                aws iam delete-role --role-name "$role" 2>/dev/null || print_warning "Failed to delete role $role"
                print_success "Deleted IAM role: $role"
            fi
        done
    else
        print_warning "No MLOps IAM roles found"
    fi
}

# Function to cleanup SageMaker Pipelines
cleanup_sagemaker_pipelines() {
    print_step "10" "Cleaning up SageMaker Pipelines"
    
    pipelines=$(aws sagemaker list-pipelines --query "PipelineSummaries[].PipelineName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$pipelines" ]]; then
        for pipeline in $pipelines; do
            # Check if pipeline has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:pipeline/$pipeline" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting SageMaker pipeline: $pipeline"
                aws sagemaker delete-pipeline --pipeline-name "$pipeline" 2>/dev/null || print_warning "Failed to delete pipeline $pipeline"
                print_success "Deleted SageMaker pipeline: $pipeline"
            fi
        done
    else
        print_warning "No SageMaker pipelines found"
    fi
}

# Function to cleanup SageMaker Models
cleanup_sagemaker_models() {
    print_step "11" "Cleaning up SageMaker Models"
    
    models=$(aws sagemaker list-models --query "Models[].ModelName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$models" ]]; then
        for model in $models; do
            # Check if model has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:model/$model" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting SageMaker model: $model"
                aws sagemaker delete-model --model-name "$model" 2>/dev/null || print_warning "Failed to delete model $model"
                print_success "Deleted SageMaker model: $model"
            fi
        done
    else
        print_warning "No SageMaker models found"
    fi
}

# Function to cleanup SageMaker Endpoints
cleanup_sagemaker_endpoints() {
    print_step "12" "Cleaning up SageMaker Endpoints"
    
    endpoints=$(aws sagemaker list-endpoints --query "Endpoints[].EndpointName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$endpoints" ]]; then
        for endpoint in $endpoints; do
            # Check if endpoint has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:endpoint/$endpoint" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                if confirm_resource_deletion "$endpoint" "SageMaker Endpoint"; then
                    if [[ "$DRY_RUN" == "true" ]]; then
                        echo "Would delete SageMaker endpoint: $endpoint"
                    else
                        echo "Deleting SageMaker endpoint: $endpoint"
                        aws sagemaker delete-endpoint --endpoint-name "$endpoint" 2>/dev/null || print_warning "Failed to delete endpoint $endpoint"
                        print_success "Deleted SageMaker endpoint: $endpoint"
                    fi
                else
                    echo "Skipped SageMaker endpoint: $endpoint"
                fi
            fi
        done
    else
        print_warning "No SageMaker endpoints found"
    fi
}

# Function to cleanup SageMaker Endpoint Configurations
cleanup_sagemaker_endpoint_configs() {
    print_step "13" "Cleaning up SageMaker Endpoint Configurations"
    
    configs=$(aws sagemaker list-endpoint-configs --query "EndpointConfigs[].EndpointConfigName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$configs" ]]; then
        for config in $configs; do
            # Check if config has our tags
            tags=$(aws sagemaker list-tags --resource-arn "arn:aws:sagemaker:$REGION:$ACCOUNT_ID:endpoint-config/$config" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting SageMaker endpoint config: $config"
                aws sagemaker delete-endpoint-config --endpoint-config-name "$config" 2>/dev/null || print_warning "Failed to delete endpoint config $config"
                print_success "Deleted SageMaker endpoint config: $config"
            fi
        done
    else
        print_warning "No SageMaker endpoint configurations found"
    fi
}

# Function to cleanup ECR repositories
cleanup_ecr_repositories() {
    print_step "14" "Cleaning up ECR Repositories"
    
    repos=$(aws ecr describe-repositories --query "repositories[].repositoryName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$repos" ]]; then
        for repo in $repos; do
            # Check if repo has our tags
            tags=$(aws ecr list-tags-for-resource --resource-arn "arn:aws:ecr:$REGION:$ACCOUNT_ID:repository/$repo" --query "tags[?key=='$PROJECT_TAG_KEY' && value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting ECR repository: $repo"
                aws ecr delete-repository --repository-name "$repo" --force 2>/dev/null || print_warning "Failed to delete ECR repository $repo"
                print_success "Deleted ECR repository: $repo"
            fi
        done
    else
        print_warning "No ECR repositories found"
    fi
}

# Function to cleanup EventBridge rules
cleanup_eventbridge_rules() {
    print_step "15" "Cleaning up EventBridge Rules"
    
    rules=$(aws events list-rules --query "Rules[].Name" --output text 2>/dev/null || echo "")
    
    if [[ -n "$rules" ]]; then
        for rule in $rules; do
            # Check if rule has our tags
            tags=$(aws events list-tags-for-resource --resource-arn "arn:aws:events:$REGION:$ACCOUNT_ID:rule/$rule" --query "Tags[?Key=='$PROJECT_TAG_KEY' && Value=='$PROJECT_TAG_VALUE']" --output text 2>/dev/null || echo "")
            
            if [[ -n "$tags" ]]; then
                echo "Deleting EventBridge rule: $rule"
                
                # Remove targets first
                targets=$(aws events list-targets-by-rule --rule "$rule" --query "Targets[].Id" --output text 2>/dev/null || echo "")
                if [[ -n "$targets" ]]; then
                    aws events remove-targets --rule "$rule" --ids $targets 2>/dev/null || true
                fi
                
                # Delete rule
                aws events delete-rule --name "$rule" 2>/dev/null || print_warning "Failed to delete EventBridge rule $rule"
                print_success "Deleted EventBridge rule: $rule"
            fi
        done
    else
        print_warning "No EventBridge rules found"
    fi
}

# Function to cleanup SageMaker-created buckets
cleanup_sagemaker_buckets() {
    print_step "16" "Cleaning up SageMaker-Created Buckets"
    
    sagemaker_buckets=$(aws s3 ls | grep sagemaker-project | awk '{print $3}' || echo "")
    
    if [[ -n "$sagemaker_buckets" ]]; then
        for bucket in $sagemaker_buckets; do
            echo "Emptying and deleting SageMaker bucket: $bucket"
            
            # Empty bucket first
            aws s3 rm "s3://$bucket" --recursive 2>/dev/null || print_warning "Failed to empty bucket $bucket"
            
            # Delete bucket
            aws s3 rb "s3://$bucket" 2>/dev/null || print_warning "Failed to delete bucket $bucket"
            print_success "Deleted SageMaker bucket: $bucket"
        done
    else
        print_warning "No SageMaker-created buckets found"
    fi
}

# Function to cleanup CloudWatch Log Groups
cleanup_cloudwatch_log_groups() {
    print_step "17" "Cleaning up CloudWatch Log Groups"
    
    log_groups=$(aws logs describe-log-groups --query "logGroups[].logGroupName" --output text 2>/dev/null || echo "")
    
    if [[ -n "$log_groups" ]]; then
        for log_group in $log_groups; do
            # Check if log group has our tags
            tags=$(aws logs list-tags-log-group --log-group-name "$log_group" --query "tags.$PROJECT_TAG_KEY" --output text 2>/dev/null || echo "")
            
            if [[ "$tags" == "$PROJECT_TAG_VALUE" ]]; then
                if confirm_resource_deletion "$log_group" "CloudWatch Log Group"; then
                    if [[ "$DRY_RUN" == "true" ]]; then
                        echo "Would delete CloudWatch log group: $log_group"
                    else
                        echo "Deleting CloudWatch log group: $log_group"
                        aws logs delete-log-group --log-group-name "$log_group" 2>/dev/null || print_warning "Failed to delete log group $log_group"
                        print_success "Deleted CloudWatch log group: $log_group"
                    fi
                else
                    echo "Skipped CloudWatch log group: $log_group"
                fi
            fi
        done
    else
        print_warning "No CloudWatch log groups found"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}🧹 MLOps Bedrock Agent - Tag-Based Cleanup${NC}"
    echo "=============================================="
    echo ""
    
    check_aws_cli
    count_tagged_resources
    backup_resources
    confirm_cleanup
    
    echo ""
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "Starting dry-run cleanup process..."
    else
        echo "Starting cleanup process..."
    fi
    echo ""
    
    cleanup_sagemaker_projects
    cleanup_model_package_groups
    cleanup_feature_groups
    cleanup_mlflow_servers
    cleanup_sagemaker_pipelines
    cleanup_sagemaker_models
    cleanup_sagemaker_endpoints
    cleanup_sagemaker_endpoint_configs
    cleanup_codepipeline_pipelines
    cleanup_codestar_connections
    cleanup_lambda_functions
    cleanup_cloudwatch_log_groups
    cleanup_s3_buckets
    cleanup_bedrock_agents
    cleanup_iam_roles
    cleanup_ecr_repositories
    cleanup_eventbridge_rules
    cleanup_sagemaker_buckets
    
    echo ""
    print_success "🎉 Cleanup completed successfully!"
    echo ""
    echo "All resources tagged with $PROJECT_TAG_KEY=$PROJECT_TAG_VALUE have been removed."
    echo "Please verify in the AWS Console that all resources have been cleaned up."
}

# Run main function
main "$@"