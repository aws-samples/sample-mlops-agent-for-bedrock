# MLOps AWS Resource Cleanup Toolkit

A comprehensive set of bash scripts for managing and cleaning up AWS resources in MLOps environments. Perfect for demo environments, development workflows, and cost management.

## 🛡️ **Smart & Safe Cleanup**

This toolkit is designed with **safety-first principles** - it won't delete anything you don't want it to.

### **🔍 Always Preview First:**
```bash
# See exactly what would be cleaned up (nothing gets deleted)
./cleanup-by-tags.sh --dry-run
```

### **✨ Built-in Safety Features:**
- **Dry-run mode** - Preview before any changes
- **Interactive confirmation** - Choose what to delete
- **Automatic backups** - JSON backup of all resources
- **Smart tagging** - Only deletes what you've tagged

📖 **New to this?** See the usage examples and troubleshooting section below.

## 🎯 **Problem Solved**
When working with MLOps on AWS, resources can accumulate quickly across multiple services:
- Lambda functions for ML inference
- S3 buckets for model artifacts and data
- IAM roles for service permissions
- Bedrock agents for AI workflows
- SageMaker resources for training and hosting

This toolkit provides automated cleanup based on resource tags, making it easy to tear down entire MLOps environments safely and efficiently.

## 📁 **What's Inside**

### 🎯 **Main Script**

**`cleanup-by-tags.sh`** - The comprehensive cleanup tool that deletes ALL AWS resources tagged with `CreatedBy=MLOpsAgent`. Handles resources created by SageMaker projects via Service Catalog, including:
- **SageMaker resources**: Projects, endpoints, model package groups, MLflow servers
- **CI/CD resources**: CodeBuild projects, CodePipeline pipelines (created by SageMaker projects)
- **Core resources**: Lambda functions, S3 buckets, IAM roles, Bedrock agents
- **Infrastructure**: CloudFormation stacks, CodeStar connections

### 🔍 **Helper Scripts**

**`list-taggable-resources.sh`** - Discovery tool that shows you what AWS resources currently exist in your account. Enhanced to include CodeBuild projects, CodePipeline pipelines, SageMaker endpoints, and CloudFormation stacks created by SageMaker projects.

**Note**: For security reasons, automatic tagging of existing resources has been removed. Resources created by the MLOps deployment should be tagged during creation, or tagged manually through the AWS Console with the `CreatedBy=MLOpsAgent` tag.

### 📚 **Documentation**
All documentation is contained in this README for simplicity.

## 🚀 **Quick Start**

### Prerequisites
- AWS CLI installed and configured
- Appropriate AWS permissions for resource management
- Bash shell (macOS/Linux)

### ⚡ **Quick Start** (Most Common)
```bash
# 1. Make scripts executable
chmod +x *.sh

# 2. Preview what would be cleaned up (safe to run)
./cleanup-by-tags.sh --dry-run

# 3. Clean up with confirmation prompts
./cleanup-by-tags.sh --interactive
```

**That's it!** The toolkit handles the rest safely.

### Full Workflow (For SageMaker Projects with Service Catalog)
```bash
# 1. Make scripts executable
chmod +x *.sh

# 2. Discover what resources exist (optional)
./list-taggable-resources.sh

# 3. Manually tag Service Catalog resources through AWS Console with CreatedBy=MLOpsAgent
# (Lambda function automatically tags resources it creates)

# 4. Clean up all tagged resources
./cleanup-by-tags.sh
```

## 🏷️ **How Tagging Works**

All scripts use the tag: `CreatedBy=MLOpsAgent`

This tag acts as a "cleanup marker" - any AWS resource with this tag will be deleted by the cleanup script. The MLOps Lambda function automatically tags resources it creates with this tag. You can modify this tag in each script by changing the `PROJECT_TAG_KEY` and `PROJECT_TAG_VALUE` variables.

### 🎯 **Automatic Tagging**

The MLOps Lambda function automatically tags the following resources when created:
- S3 buckets for ML artifacts
- CodeStar connections for GitHub/GitLab integration
- SageMaker projects and associated resources
- Model package groups in the Model Registry
- Feature Store groups
- MLflow tracking servers

### ⚠️ **Service Catalog Resources**

**Important**: When SageMaker projects are created via Service Catalog, they deploy CloudFormation templates that create additional resources like:
- CodeBuild projects (`sagemaker-{project}-{id}-modelbuild`)
- CodePipeline pipelines (`sagemaker-{project}-{id}-modeldeploy`) 
- SageMaker inference endpoints (`{project}-staging`, `{project}-prod`)
- CloudFormation stacks

**These Service Catalog-created resources are NOT automatically tagged** during creation and must be tagged manually through the AWS Console with `CreatedBy=MLOpsAgent` if cleanup is desired.

### 📝 **CloudWatch Log Groups**

**Important**: AWS does not automatically tag CloudWatch log groups, even when they're created by tagged resources. Log groups must be manually tagged if cleanup is desired.

**Common log group patterns:**
- `/aws/lambda/{function-name}` - Created by Lambda functions
- `/aws/sagemaker/Endpoints/{endpoint-name}` - Created by SageMaker endpoints
- `/aws/sagemaker/TrainingJobs` - Created by SageMaker training jobs
- `/aws/codebuild/{project-name}` - Created by CodeBuild projects

**To tag a log group:**
```bash
aws logs tag-log-group \
  --log-group-name /aws/lambda/mlops-project-management \
  --tags CreatedBy=MLOpsAgent
```

**Recommended**: Set retention policies to auto-expire logs:
```bash
aws logs put-retention-policy \
  --log-group-name /aws/lambda/mlops-project-management \
  --retention-in-days 7
```

## 🔍 **Supported AWS Services**

The cleanup toolkit removes resources created by the MLOps Lambda function and any other AWS resources tagged with `CreatedBy=MLOpsAgent`.

### Fully Supported (Complete cleanup)
- **Amazon S3** - Buckets (contents emptied first, then bucket deleted)
- **CodeStar Connections** - GitHub/GitLab connections
- **Amazon SageMaker** - Projects, model package groups, feature groups, pipelines, models, endpoints, endpoint configs
- **MLflow** - Tracking servers
- **Amazon ECR** - Container repositories
- **Amazon EventBridge** - Rules and targets
- **CloudWatch Logs** - Log groups (must be manually tagged)

### Additional Cleanup
- **IAM** - Roles and inline policies (policies detached first)
- **CloudFormation** - Stacks created by SageMaker projects
- **CodePipeline** - CI/CD pipelines created by SageMaker projects

## 📋 **Usage Examples**

### Example 1: Quick Demo Cleanup
```bash
# See what would be cleaned up
./cleanup-by-tags.sh --dry-run

# Clean up with confirmations
./cleanup-by-tags.sh --interactive
```

### Example 2: Development Environment Cleanup
```bash
# Discover what's currently deployed
./list-taggable-resources.sh

# Preview and clean up tagged resources
./cleanup-by-tags.sh --dry-run
./cleanup-by-tags.sh --interactive
```

### Example 3: Complete MLOps Environment Cleanup
```bash
# The Lambda function automatically tags resources it creates
# For Service Catalog resources, manually tag through AWS Console with CreatedBy=MLOpsAgent

# Then clean up everything
./cleanup-by-tags.sh
```

### Example 4: Custom Tags
Modify the `PROJECT_TAG_KEY` and `PROJECT_TAG_VALUE` variables in scripts to use your own tags:
```bash
PROJECT_TAG_KEY="Environment"
PROJECT_TAG_VALUE="Development"
```

## 💡 **Best Practices**

### **🎯 Recommended Workflow:**
1. **Preview first** - Run `./cleanup-by-tags.sh --dry-run` to see what would be cleaned
2. **Use interactive mode** - Let the tool ask before deleting each resource
3. **Check the backup** - Every cleanup creates a JSON backup automatically

### **🚀 Pro Tips:**
- **Development environments**: Use `--interactive` for selective cleanup
- **Demo cleanup**: Dry-run first, then full cleanup if it looks right
- **Production**: Always coordinate with your team and use dry-run mode

The toolkit is designed to be **safe by default** - it won't surprise you!

## 🛡️ **Required AWS Permissions**

Your AWS user/role needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:*",
        "s3:*",
        "iam:*",
        "bedrock-agent:*",
        "codeconnections:*",
        "sagemaker:*",
        "resourcegroupstaggingapi:*"
      ],
      "Resource": "*"
    }
  ]
}
```

## 🔧 **Customization**

### Change Project Tag
Edit the `PROJECT_TAG` variable in each script:
```bash
PROJECT_TAG_KEY="CreatedBy"
PROJECT_TAG_VALUE="YourProjectName"
```

### Add More Resource Types
Extend the scripts by adding new AWS service cleanup functions following the existing patterns.

### Modify Resource Filters
Change the resource discovery queries to match your naming conventions.

## 📊 **What Gets Cleaned Up (In Order)**

The cleanup process removes resources in this order to handle dependencies:
1. SageMaker projects, models, endpoints, and pipelines
2. MLflow tracking servers  
3. CodePipeline pipelines
4. CodeStar connections
5. Lambda functions
6. CloudWatch log groups
7. S3 buckets (contents emptied first)
8. Bedrock agents
9. IAM roles (policies detached first)
10. ECR repositories
11. EventBridge rules

## 🎉 **Success Indicators**

After running the scripts, you should see:
- ✅ Green checkmarks for successful operations
- 📊 Summary counts of resources processed
- 🎉 Completion messages

## 🐛 **Troubleshooting**

### Common Issues

1. **Permission Denied**
   - Ensure your AWS credentials have sufficient permissions
   - Check IAM policies for resource access

2. **Resources Not Found**
   - Verify you're in the correct AWS region
   - Check resource naming patterns match the filters

3. **Partial Cleanup**
   - Some resources may have dependencies
   - Run cleanup script multiple times if needed

### **"I don't see any resources to clean up"**
- Make sure you've tagged your resources manually through AWS Console with `CreatedBy=MLOpsAgent`
- Check that you're in the right AWS region
- Verify your AWS CLI is configured correctly

### **"I want to stop the cleanup"**
- Press `Ctrl+C` to stop the script immediately
- In interactive mode, type `q` to quit safely
- Check the backup file to see what was already processed

### **"I accidentally deleted something important"**
- Check the backup file (`mlops-resources-backup-*.json`) for details
- Review AWS CloudTrail for the exact deletion events
- Contact AWS support if you need help recovering resources

### Getting Help

1. Review AWS CLI error messages for specific issues
2. Verify AWS service limits and quotas
3. Check AWS CloudTrail for detailed operation logs

---

**Perfect for**: MLOps practitioners, AWS developers, demo environments, and cost management  
**Last Updated**: January 2025  
**License**: MIT