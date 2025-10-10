
**Building Gaming MLOps pipelines with Amazon Bedrock Agents**

In today\'s competitive gaming landscape, machine learning (ML) has become essential for delivering personalized experiences, optimizing game mechanics, and driving business outcomes. However, traditional approaches to building and deploying ML systems often require extensive DevOps expertise, manual pipeline configuration, and complex infrastructure management that can slow down innovation and time-to-market. Game studios need agile, automated solutions that can rapidly iterate on ML models while maintaining production reliability and scalability across diverse gaming use cases.

**Amazon SageMaker AI and MLOps**

[Amazon SageMaker AI](https://aws.amazon.com/sagemaker/ai/) provides powerful MLOps capabilities, but orchestrating the complete CI/CD pipeline---from model development to production deployment---typically involves navigating multiple AWS services, managing intricate dependencies, and coordinating approval workflows. This complexity can create barriers for game studios or game analytics teams who want to focus on building great predictive models rather than wrestling with infrastructure.

This blog post demonstrates how to leverage [Amazon Bedrock Agents](https://aws.amazon.com/bedrock/agents/) to create an intelligent MLOps assistant that simplifies the entire CI/CD pipeline construction and management process. By combining the conversational capabilities of Amazon Bedrock with the robust MLOps features of Amazon SageMaker AI, we\'ll build a system that allows game teams to create, manage, and deploy gaming prediction models using natural language commands.

Our solution addresses common pain points in gaming machine learning model build, train, and deploy pipelines:

- Rapid experimentation: Quickly spin up new prediction experiments without infrastructure overhead

- Automated workflows: Streamline the path from model training to production deployment

- Approval management: Handle model approvals through conversational interfaces

- Multi-project coordination: Manage multiple game titles and their respective models from a single interface

By the end of this walkthrough, you\'ll have a fully functional MLOps agent capable of managing complex machine learning workflows for gaming analytics. This will enable your team to deploy gaming prediction systems with simple conversational commands like \"Create a player churn CI/CD pipeline for my mobile puzzle game\" or \"Show status of build pipeline execution".

**Create an MLOps Management Agent**

**Set Up the Foundation Infrastructure**

Before creating the Bedrock agent, establish the core AWS infrastructure that will support the MLOps workflows. The infrastructure includes two [AWS Identity and Access Management (IAM)](https://aws.amazon.com/iam/) roles: mlops-agent-role and lambda-agent-role. Trust relationships and policies for each role have been provided and referenced in the create role steps. First, create an mlops-agent-role with attached inline policies to enable the Amazon Bedrock Agent to access required AWS services that support an MLOps pipeline.

1.  **Create** an AWS IAM role, mlops-agent-role

2.  **Select** the Trust relationships tab**, Edit** trust policy and paste the [trust relationship policy](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample/-/blob/main/mlops-agent-role-trust-relationship.json) in the trusted entities editor

3.  Add permissions with **Create inline policy** and paste the [mlops-agent-policy](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample/-/blob/main/mlops-agent-policy.json) in the policy editor box

4.  **Create** a second inline policy for AWS Lambda invocation access and paste the [lambda-invoke-access](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample/-/blob/main/lambda-invoke-access.json) policy in the policy editor

5.  Replace ACCOUNT_ID with your AWS account ID in the policy document

Next, create an AWS IAM role that allows the [AWS Lambda](https://aws.amazon.com/lambda/) action invocation to access required AWS services.

1.  **Create** an AWS IAM role lambda-agent-role, that adds the [AWSLambdaBasicExecutionRole](https://docs.aws.amazon.com/aws-managed-policy/latest/reference/AWSLambdaBasicExecutionRole.html) managed role

2.  **Select** the Trust relationships tab**, Edit** trust policy and paste the [trust relationship policy](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample/-/blob/main/lambda-agent-role-trust-relationship.json) in the trusted entities editor

3.  Next, add permissions with **Create inline policy** and add a [lambda-agent-policy](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample/-/blob/main/lambda-agent-policy.json)

Configure [Amazon S3](https://aws.amazon.com/s3/) Storage to store machine learning artifacts, model outputs, and pipeline configurations either in the [AWS Management Console](https://aws.amazon.com/console/) or with the [AWS Command Line Interface](https://aws.amazon.com/cli/).

aws s3 mb s3://game-ml-artifacts-\$(aws sts get-caller-identity \--query Account \--output text)

**Create an MLOps AWS Lambda Function**

The AWS Lambda function serves as the backend engine for the Amazon Bedrock Agent, handling all MLOps operations through an API. The Amazon Bedrock action group invocation calls the AWS Lambda function using an action group schema that maps endpoints to actions.

To create the AWS Lambda function, in the AWS Management Console, **select** the AWS Lambda service.

1.  Select **Author from scratch**

2.  **Enter** a Function name such as mlops-project-management

3.  **Choose** a Python 3.1x Runtime

4.  **Select** x86_64 or arm64

5.  **Change** the default execution role to use the existing mlops-agent-role previously created

6.  **Select Create function**

7.  Download the AWS Lambda function zip file or clone the function from [Github AWS Samples repository](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample)

8.  **Upload** the zip file or copy and paste the function code into the Lambda code window

9.  **Select** the Configuration tab for the function and General configuration

10. **Choose Edit** and update the function Timeout value to 15 minutes

11. **Deploy** the function

Figure 3 -- Set AWS Lambda function timeout value

The function is now ready to act as an Amazon Bedrock Agent and support the following actions.

- /configure-code-connection - Set up [AWS CodeConnections](https://docs.aws.amazon.com/codeconnections/latest/APIReference/Welcome.html) connection for GitHub integration

- /create-mlops-project - Create a new SageMaker MLOps project with GitHub integration

- /create-feature-store-group - Create SageMaker Feature Store Feature Group

- /create-model-group - Create SageMaker Model Package Group

- /create-mlflow-server - Create [Amazon SageMaker AI MLflow Tracking Server](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow.html)

- /build-cicd-pipeline - Build CI/CD pipeline using seed code from GitHub

- /manage-model-approval - Manage model package approval in Amazon SageMaker AI Model Registry

- /manage-staging-approval - List models in staging ready for manual approval

- /manage-project-lifecycle - Handle project updates and lifecycle management

- /list-mlops-templates - List available MLOps [AWS Service Catalog](https://aws.amazon.com/servicecatalog/) templates

In addition, the Lambda function automatically manages:

- Repository seed code population from GitHub

- Dynamic AWS CodeBuild buildspec generation with project-specific parameters

- Pipeline parameter injection and configuration

- Multi-stage approval workflow management

- Error handling and detailed logging for troubleshooting

**Create the Amazon Bedrock MLOps Agent**

1.  In the AWS Management Console, **Navigate** to Amazon Bedrock

2.  **Select Agents** from the left navigation panel under Build

3.  **Choose Create Agent**

4.  Configure the agent with these settings:

    - Agent Name: \"MLOpsOrchestrator\"

    - Description: \"Intelligent assistant for gaming MLOps CI/CD pipeline management\"

    - Foundation Model: US Anthropic Claude 3.7 Sonnet

    - Use existing service role, mlops-agent-role for Agent resource role

5.  Configure Agent Instructions\--provide instructions that establish the agent\'s identity and capabilities

You are an expert MLOps engineer specializing in SageMaker pipeline orchestration. Help users create, manage, and deploy ML models through automated CI/CD pipelines. Always follow AWS best practices and provide clear status updates.

Key Responsibilities:

\- Create and manage SageMaker MLOps projects for gaming analytics

\- Set up CI/CD pipelines for prediction models

\- Manage model approval workflows from development to production

\- Provide guidance on gaming-specific ML best practices

**Create Amazon Bedrock Agent Action Groups**

1.  In the Agent builder, under Action groups, **Select Add**

2.  Name: **ProjetManagement**

3.  Description: **Actions for managing SageMaker MLOps projects and GitHub integration**

4.  Action Group Type: **Define with API schemas**

5.  **Select** an existing Lambda function: mlops-project-management


1.  Under Action group schema, **toggle Define via in-line schema editor**

2.  Download the MLOps agent OpenAPI schema from the [GitHub AWS Samples repository](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample)

3.  **Select JSON** from the drop-down and paste the provided OpenAPI schema in the editor

4.  **Choose Save and exit**

**Use the MLOps agent**

With the agent created and configured, it's ready to use for launching AWS resources to support an MLOps CI/CD pipeline. As a foundation of the pipeline, an [AWS Service Catalog](https://aws.amazon.com/servicecatalog/) template defines [AWS CodeBuild](https://aws.amazon.com/codebuild/), [AWS CodePipeline](https://aws.amazon.com/codepipeline/), SageMaker AI inference endpoints for staging and production. Creating an Amazon SageMaker AI project launches the resources with configuration specified with the MLOps agent. Before creating an Amazon SageMaker AI project with the AWS Service Catalog template, you\'ll need to set up several prerequisites. These include an [AWS CodeConnection](https://docs.aws.amazon.com/codeconnections/latest/APIReference/Welcome.html) to access GitHub, a managed MLflow tracking server, and a feature store with sample features for the MLOps template that handles model building, training, and deployment with third-party Git repositories.. The Feature Store Group features are based on a [synthetic player churn data set](https://github.com/aws-solutions-library-samples/guidance-for-predicting-player-behavior-with-ai-on-aws/blob/main/assets/examples/player-churn.csv). The final prerequisite is required by the AWS Service Catalog template. Create two empty private [GitHub](https://github.com/) repositories:

- player-churn-model-build

- player-churn-model-deploy

To use the agent

1.  **Select Test and Prepare** in the Amazon Bedrock Agents console

<!-- -->

1.  **Enter prompts** to create resources using natural language

2.  Start with **describe agent actions**

Use the agent to create a Feature Store group for gaming analytics

Create Feature Store group named \"player-churn-features\" with feature description \"player_id as string identifier, player_lifetime as number, player_churn as integer, time_of_day features as floats, cohort_id features as binary flags, event_time as event time feature\" and description \"Feature group for player churn prediction model containing player behavior and engagement metrics\"

Create an Amazon SageMaker AI managed MLflow tracking server

Create MLflow tracking server named \"player-churn-tracking-server\" with artifact store \"s3://game-ml-artifacts/mlflow/\" and size \"Medium\" and role_arn \"arn:aws:iam::123445567789:role/mlops-agent-role\"

Establish GitHub integration

Create an AWS CodeConnection called \"mlops-github\" for GitHub integration

Create an MLOps CI/CD project

Create MLOps project named \"mlops-player-churn\" with GitHub username \"your Github username\", build repository \"player-churn-model-build\", deploy repository \"player-churn-model-deploy\", using connection ARN \"your-connection-arn\"

Create an MLOps CI/CD Pipeline

Build CI/CD pipeline for project \"mlops-player-churn\" with model build repository \"gitUserName/player-churn-model-build\", deploy repository "gitUserName/player-churn-model-deploy", connection ARN \"your-connection-arn\", feature group \"player-churn-features\", S3 bucket \"game-ml-artifacts\", MLflow server \"your-mlflow-arn\", and pipeline \"player-churn-training-pipeline\"

To verify and visualize the pipeline, in the AWS console, navigate to AWS CodePipeline and **select Pipelines** in the left-hand navigation pane. There will be two pipelines: one for build and another for deploy. **Select the link of the build project** to view pipeline steps.

To trigger the CI/CD pipeline, push changed code to the model-build repository and the deploy step of the pipeline will automatically execute. Open a terminal window, change directories to player-churn-model-build folder and execute a commit.

git config \--global user.email \"you@example.com\"

git config \--global user.name \"Your Name\"

git add -A

git commit -am \"customize project\"

git push

The git push will launch the deploy step of the model building pipeline and create two Amazon SageMaker AI inference endpoints: DeployStaing and DeployProd. Navigate to the AWS CodePipelines deploy pipeline to view the pipeline steps.

Using an Amazon Bedrock Agent, a complete MLOps model build and deploy CI/CD pipeline has been created. Try out additional agent prompts to experiment with the flexibility and function of the agent. [Amazon SageMaker Canvas](https://aws.amazon.com/sagemaker/ai/canvas/) can be used to connect to data sources such as transactional databases, data warehouses, Amazon S3 or over 50 other data providers. Canvas can be used to feature engineer data and used as a data source for the MLOps model build and deploy pipeline.

**Cleanup**

To avoid ongoing charges, navigate to the following AWS services in the AWS Management Console and terminate resources.

**Amazon Bedrock** Agents

**AWS CodeConnection** Connections (GitHub integration)

**Amazon SageMaker AI**

- SageMaker project

- SageMaker MLflow tracking server

- SageMaker feature group (Feature Store)

- SageMaker model package group (Model Registry)

- SageMaker pipeline

- SageMaker inference endpoints (staging and production)

- SageMaker models

**Amazon S3**

- S3 bucket (for MLflow artifacts)

- S3 objects (buildspec files, configuration files, requirements.txt)

**AWS CodePipeline** pipelines (build and deploy)

**AWS CodeBuild** projects

[**AWS CloudFormation**](https://aws.amazon.com/cloudformation/) stacks (created by AWS Service Catalog)

**AWS Lambda** function (MLOps agent)

A command line automated [cleanup script](https://gitlab.aws.dev/sflast/amazon-bedrock-mlops-agent-sample/-/blob/main/mlops-aws-resource-cleanup-toolkit/cleanup-by-tags.sh?ref_type=heads) is available to delete resources as well. The script uses resource tags to safely identify and remove all MLOps deployed resources. The script automatically removes all MLOps resources tagged with **CreatedBy=MLOpsAgent**. Run** cleanup-by-tags.sh**  to terminate resources.

**Conclusion**

Building an intelligent MLOps CI/CD pipeline management system using Amazon Bedrock Agents represents a significant advancement in how gaming teams can approach machine learning operations. Throughout this walkthrough, we\'ve demonstrated how to transform complex, multi-service MLOps workflows into simple, conversational interactions that dramatically reduce the barrier to entry for sophisticated gaming analytics.

**Further reading**

[MLOps Amazon SageMaker AI notebook samples](https://github.com/aws-samples/mlops-sagemaker-mlflow)

[Amazon SageMaker AI workflows](https://docs.aws.amazon.com/sagemaker/latest/dg/workflows.html)

[Amazon SageMaker Pipelines](https://aws.amazon.com/sagemaker/ai/pipelines/)

[Amazon SageMaker for MLOps](https://aws.amazon.com/sagemaker/ai/mlops/)

[Operationalize Machine Learning with Amazon SageMaker MLOps and MLFlow workshop](https://studio.us-east-1.prod.workshops.aws/workshops/b9405337-9690-4fb2-9f7d-76e6babb7a2c#permissions)
