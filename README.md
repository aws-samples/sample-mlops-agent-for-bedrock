# Building Gaming MLOps CI/CD with Amazon Bedrock Agents

## Introduction

In today's competitive gaming landscape, understanding and predicting player behavior is crucial for maintaining engagement and maximizing revenue. Player churn—when users stop playing a game—represents one of the most significant challenges facing game developers and publishers. Traditional approaches to building machine learning systems for churn prediction often require extensive DevOps expertise, manual pipeline configuration, and complex infrastructure management that can slow down innovation and time-to-market.

Amazon SageMaker AI provides powerful MLOps capabilities, but orchestrating the complete CI/CD pipeline—from model development to production deployment—typically involves navigating multiple AWS services, managing intricate dependencies, and coordinating approval workflows. This complexity can create barriers for game studios or game analytics teams who want to focus on building great predictive models rather than wrestling with infrastructure.

This blog post demonstrates how to leverage Amazon Bedrock Agents to create an intelligent MLOps assistant that simplifies the entire CI/CD pipeline construction and management process. By combining the conversational capabilities of Amazon Bedrock with the robust MLOps features of Amazon SageMaker AI, we'll build a system that allows game teams to create, manage, and deploy player churn prediction models using natural language commands.

Our solution addresses common pain points in gaming analytics:

- **Rapid experimentation**: Quickly spin up new churn prediction experiments without infrastructure overhead
- **Automated workflows**: Streamline the path from model training to production deployment
- **Approval management**: Handle staging-to-production approvals through conversational interfaces
- **Multi-project coordination**: Manage multiple game titles and their respective churn models from a single interface

By the end of this walkthrough, you'll have a fully functional MLOps agent capable of managing complex machine learning workflows for gaming analytics, enabling your team to deploy player churn prediction systems with simple conversational commands like "Create a churn prediction pipeline for my mobile puzzle game" or "Approve the latest retention model for production deployment."

## Steps to Create the MLOps Management Agent

### Set Up the Foundation Infrastructure

Before creating our Bedrock agent, we need to establish the core AWS infrastructure that will support our MLOps workflows.

Create an `mlops-agent-role` that adds the managed `AWSLambdaBasicExecutionRole` permissions. Next, Add permissions with Create inline policy and create an `mlops-agent-policy`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:*",
        "sagemaker:*",
        "sagemaker-mlflow:*",
        "codestar-connections:*",
        "codeconnections:*",
        "codepipeline:*",
        "codebuild:*",
        "servicecatalog:*",
        "cloudformation:*",
        "s3:*",
        "iam:PassRole",
        "iam:GetRole"
      ],
      "Resource": "*"
    }
  ]
}
```

After attaching the policy, add AWS Lambda and Amazon Bedrock trust relationships by selecting the Trust relationships tab and adding the following Trusted entities:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "lambda.amazonaws.com",
          "events.amazonaws.com",
          "sagemaker.amazonaws.com"
        ]
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

### Set Up S3 Storage

Create an S3 bucket to store ML artifacts, model outputs, and pipeline configurations:

```bash
aws s3 mb s3://game-ml-artifacts-$(aws sts get-caller-identity --query Account --output text)
```

### Create MLOps Lambda Function

The Lambda function serves as the backend engine for the Bedrock agent, handling all MLOps operations through an API. The Amazon Bedrock action group invocation calls the Lambda function using an action group schema that maps endpoints to actions.

To create the Lambda function, in the AWS Console:

1. Select the Lambda service
2. Toggle **Author from scratch**
3. Enter a Function name such as `mlops-project-management`
4. Choose a Python 3.1x Runtime
5. Toggle x86_64 or arm64
6. Change the default execution role to use the existing `mlops-agent-role` previously created
7. Select **Create function**

Download the Lambda function zip file or clone the function from Github. Upload the zip file or copy and paste the function code into the Lambda code window.

Select the **Configuration** tab for the function and **General configuration**. Choose **Edit** and update the function **Timeout** value to 15 minutes.

The function is now ready to act as an Amazon Bedrock Agent and support the following actions:

- `/configure-code-connection`: Sets up GitHub integration via AWS CodeStar Connections
- `/create-mlops-project`: Creates SageMaker projects using Service Catalog templates
- `/build-cicd-pipeline`: Orchestrates complete CI/CD pipeline construction
- `/manage-model-approval`: Handles Model Registry approval workflows
- `/manage-staging-approval`: Manages CodePipeline deployment approvals
- `/list-mlops-templates`: Discovers available MLOps project templates

In addition, the Lambda function automatically handles:

- Repository seed code population from GitHub
- Dynamic buildspec generation with project-specific parameters
- Pipeline parameter injection and configuration
- Multi-stage approval workflow management
- Error handling and detailed logging for troubleshooting

### Create the Amazon Bedrock MLOps Agent

1. Navigate to the Amazon Bedrock console
2. Select "Agents" from the left navigation panel under Build
3. Click "Create Agent"

Configure the agent with these settings:

- **Agent Name**: "MLOpsOrchestrator"
- **Description**: "Intelligent assistant for gaming MLOps CI/CD pipeline management"
- **Foundation Model**: US Anthropic Claude 3.7 Sonnet
- Use existing service role, `mlops-agent-role` for Agent resource role

### Configure Agent Instructions

Provide instructions that establish the agent's identity and capabilities:

```
You are an expert MLOps engineer specializing in SageMaker pipeline orchestration. Help users create, manage, and deploy ML models through automated CI/CD pipelines. Always follow AWS best practices and provide clear status updates.

Key Responsibilities:
- Create and manage SageMaker MLOps projects for gaming analytics
- Set up CI/CD pipelines for player churn prediction models
- Manage model approval workflows from development to production
- Provide guidance on gaming-specific ML best practices
```

### Configure Action Groups

#### Create the MLOps Action Group

In the Agent builder, under Action groups, select **Add**:

- **Name**: "ProjetManagement"
- **Description**: "Actions for managing SageMaker MLOps projects and GitHub integration"
- **Action Group Type**: "Define with API schemas"
- Select an existing Lambda function: `mlops-project-management`

Under Action group schema, toggle **Define via in-line schema editor**. Download the MLOps agent OpenAPI schema from the GitHub aws-samples repository. Select JSON from the drop-down and paste the provided OpenAPI schema in the editor.

Choose **Save and exit**.

## Use the MLOps agent

With agent created and configured, it's ready to use for launching AWS resources to support an MLOps CI/CD pipeline. As a foundation of the pipeline, an Amazon Service Catalog template defines AWS CodeBuild, AWS CodePipeline, SageMaker AI inference endpoints for staging and production. Creating an Amazon SageMaker AI project launches the resources with configuration specified with the MLOps agent.

Before creating an Amazon SageMaker AI MLOps with the AWS Service Catalog template, MLOps template for model building, training, and deployment with third-party Git repositories using CodePipeline, first create prerequisites such as an AWS CodeConnection to access GitHub, a managed MLflow tracking server and a feature store with sample player churn features. The Feature Store Group features are based on a synthetic player churn data set.

The final prerequisite is required by the AWS Service Catalog template. Create two empty private repositories:

- `player-churn-model-build`
- `player-churn-model-deploy`

To use the agent, Select **Test and Prepare** in the Amazon Bedrock Agents console. Enter prompts to create resources using natural language.

### Use the agent to create a Feature Store group for game analytics

```
Create Feature Store group named "player-churn-features" with feature description "player_id as string identifier, player_lifetime as number, player_churn as integer, time_of_day features as floats, cohort_id features as binary flags, event_time as event time feature" and description "Feature group for player churn prediction model containing player behavior and engagement metrics"
```

### Set-up a managed MLflow tracking server

```
Create MLflow tracking server named "player-churn-tracking-server" with artifact store "s3://game-ml-artifacts/mlflow/" and size "Medium"
```

### Establish GitHub integration

```
Create an AWS CodeConnection called "mlops-github" for GitHub integration
```

### Create an MLOps CI/CD project

```
Create MLOps project named "mlops-player-churn" with GitHub username "your Github username", build repository "player-churn-model-build", deploy repository "player-churn-model-deploy", using connection ARN "your-connection-arn"
```

### Create an MLOps CI/CD Pipeline

```
Build CI/CD pipeline for project "mlops-player-churn" with model build repository "gitUserName/player-churn-model-build", deploy repository "gitUserName/player-churn-model-deploy", connection ARN "your-connection-arn", feature group "player-churn-features", S3 bucket "game-ml-artifacts", MLflow server "your-mlflow-arn", and pipeline "player-churn-training-pipeline"
```

To verify and visualize the pipeline, in the AWS console, navigate to AWS CodePipeline and select **Pipelines** in the left-hand navigation pane. There will be two pipelines: one for build and another for deploy. Select the link of the build project and a visual view show the pipeline steps.

To trigger the CI/CD pipeline, push changed code to the model-build repository and the deploy part of the pipeline will automatically execute. Open a terminal window, change directories to Git `player-churn-model-build` folder and execute a commit:

```bash
git config --global user.email "you@example.com"
git config --global user.name "Your Name"
git add -A
git commit -am "customize project"
git push
```

The `git push` will launch the deploy step of the model building pipeline and launch two Amazon SageMaker AI inference endpoints: `DeployStaing` and `DeployProd`. Navigating to the AWS CodePipelines deploy pipeline will show the new pipeline steps.

Using an Amazon Bedrock Agent, a complete MLOps model build and deploy CI/CD pipeline has been created. Try out additional agent prompts to experiment with the flexibility and function of the agent.

Amazon SageMaker AI Canvas can be used to connect to data sources such as transactional databases, data warehouses, Amazon S3 or over 50 other data providers. Canvas can be used to feature engineer data and used as a data source for the MLOps model build and deploy pipeline.

## Cleanup

To avoid ongoing charges, use the enhanced cleanup toolkit included in this repository. The toolkit uses smart resource tagging to safely identify and remove all MLOps deployed resources.

**Safe cleanup process:**
```bash
# Navigate to the cleanup toolkit
cd mlops-aws-resource-cleanup-toolkit

# Make scripts executable
chmod +x *.sh

# Preview what would be cleaned up (safe to run)
./cleanup-by-tags.sh --dry-run

# Clean up with confirmation prompts
./cleanup-by-tags.sh --interactive
```

The toolkit includes built-in safety features:
- **Dry-run mode** to preview deletions
- **Interactive confirmation** for each resource
- **Automatic backups** of all resources before cleanup
- **Resource counting** and validation

All MLOps resources tagged with `CreatedBy=MLOpsAgent` will be safely removed. See the [cleanup toolkit documentation](mlops-aws-resource-cleanup-toolkit/README.md) for more details.

## Conclusion

Building an intelligent MLOps CI/CD pipeline management system using Amazon Bedrock Agents represents a significant advancement in how gaming teams can approach machine learning operations. Throughout this walkthrough, we've demonstrated how to transform complex, multi-service MLOps workflows into simple, conversational interactions that dramatically reduce the barrier to entry for sophisticated gaming analytics.

## Further reading

- [MLOps Amazon SageMaker AI notebook samples](https://github.com/aws/amazon-sagemaker-examples)
- [Amazon SageMaker AI workflows](https://docs.aws.amazon.com/sagemaker/latest/dg/workflows.html)
- [Amazon SageMaker Pipelines](https://docs.aws.amazon.com/sagemaker/latest/dg/pipelines.html)
- [Amazon SageMaker for MLOps](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-projects.html)
- [Operationalize Machine Learning with Amazon SageMaker](https://aws.amazon.com/sagemaker/mlops/)
- [MLOps and MLFlow workshop](https://catalog.workshops.aws/mlops-workshop)

