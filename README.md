# Building Gaming MLOps pipelines with Amazon Bedrock Agents


**Building gaming MLOps pipelines with Amazon Bedrock Agents**

In today's competitive gaming landscape, machine learning (ML) has become essential for delivering personalized experiences, optimizing game mechanics, and driving business outcomes. However, traditional approaches to building and deploying ML systems often require extensive DevOps expertise, manual pipeline configuration, and complex infrastructure management that can slow down innovation and time-to-market. Game studios need agile, automated solutions that can rapidly iterate on ML models, while maintaining production reliability and scalability across diverse gaming use cases.

**Amazon SageMaker AI and MLOps**

[Amazon SageMaker AI](https://aws.amazon.com/sagemaker/ai/) provides powerful MLOps capabilities. However, orchestrating the complete continuous integration and continuous delivery (CI/CD) pipeline—from model development to production deployment—typically involves navigating multiple Amazon Web Services (AWS) services. These include managing intricate dependencies, and coordinating approval workflows. This complexity can create barriers for game studios, or game analytics teams, who want to focus on building great predictive models rather than wrestling with infrastructure.

We will demonstrate how to leverage [Amazon Bedrock Agents](https://aws.amazon.com/bedrock/agents/) to create an intelligent MLOps assistant that streamlines the entire CI/CD pipeline construction and management process. We will combine the conversational capabilities of [Amazon Bedrock](https://aws.amazon.com/bedrock/) with the robust MLOps features of Amazon SageMaker AI. With this solution game teams can create, manage, and deploy gaming prediction models using natural language commands.

Our solution addresses common pain points in gaming machine learning model build, train, and deploy pipelines:

- **Rapid experimentation:** Quickly spin up new prediction experiments without infrastructure overhead
- **Automated workflows:** Streamline the path from model training to production deployment
- **Approval management:** Handle model approvals through conversational interfaces
- **Multi-project coordination:** Manage multiple game titles and their respective models from a single interface

By the end of this walkthrough we will have created a fully functional MLOps agent, capable of managing complex machine learning workflows for gaming analytics. Your team can then deploy the gaming prediction solution with conversational commands such as, "Create a player churn CI/CD pipeline for my mobile puzzle game," or "Show status of build pipeline execution”.

**Prerequisites**

Before starting you will need to make certain you have done or have the following:

- A [Githu](https://github.com/)b account with remote access
- The [AWS Command Line Interface](https://aws.amazon.com/cli/) installed
- An [Amazon SageMaker AI domain and user](https://docs.aws.amazon.com/sagemaker/latest/dg/onboard-quick-start.html)

**Create and configure an MLOps management agent**

**Set up the foundation infrastructure**

Before creating the Amazon Bedrock Agent, establish the core AWS infrastructure that will support the MLOps workflows.

The infrastructure includes two AWS Identity and Access Management (IAM) roles:

- mlops-agent-role
- lambda-agent-role

Trust relationships and policies for each role have been provided and referenced in the create role steps.

**Roles**

First, create an mlops-agent-role with attached inline policies to enable the Amazon Bedrock Agent to access required AWS services that support an MLOps pipeline.

- Create an AWS IAM role, **mlops-agent-role **with Trusted entity type **AWS service** and Use case **Lambda**
- Select** **the** Trust relationships** tab**, Edit** the **trust policy** and paste the **[trust relationship policy](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/mlops-agent-role-trust-relationship.json)** in the trusted entities editor
- Add permissions with **Create inline policy** and paste the *[*mlops-agent-policy](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/mlops-agent-policy.json)** in the policy editor box
- Create** **a second inline policy for AWS Lambda invocation access, and paste the **[lambda-invoke-access](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/lambda-invoke-access.json)** policy in the policy editor
- Replace *ACCOUNT_ID* with your AWS account ID in the policy document

Next, create an IAM role that allows the AWS Lambda action invocation to access required AWS services.

- Create an IAM role called **lambda-agent-role **with Trusted entity type **AWS service** and use case **Lambda**
- Search for the AWSLambdaBasicExecutionRole managed policy and add
- Select** **the** Trust relationships** tab**, **Edit the **trust policy** and paste the **[trust relationship policy](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/lambda-agent-role-trust-relationship.json)** in the trusted entities editor
- Next, add permissions with **Create inline policy** and add a **[lambda-agent-policy](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/lambda-tagging-policy.json)**

**	**

Add a policy to the AWS managed AmazonSageMakerServiceCatalogProductsLaunchRole**.**

- Add permissions with Create inline policy and add [lambda-tagging-policy](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/lambda-tagging-policy.json)

**MLOps AWS Lambda function **

The AWS Lambda function serves as the backend engine for the Amazon Bedrock Agent, handling all MLOps operations through an API. The Amazon Bedrock action group invocation calls the AWS Lambda function using an action group schema that maps endpoints to actions.

Use the following steps to create the AWS Lambda function:

- In the console, select **AWS Lambda**
- Select **Author from scratch**
- Enter a *Function name*, we used: mlops-project-management
- Choose a Python 3.1x Runtime
- Select **x86_64**
- Change the default execution role to **use the existing lambda-agent-role** previously created
- Select** **the** Create function** button

Figure 1 – Create AWS Lambda function

- Download the AWS Lambda function file or clone the function from our [Github AWS Samples repository](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/mlops-project.py)
- Copy and paste the function code into the Lambda code window

Figure 2 – Add code to AWS Lambda function

- Select the **Configuration** tab to access the function and General configuration** **
- Choose** **the **Edit** button and update the function *Timeout* value to 15 minutes
- On the **Configuration** tab, select Permissions and **Add permissions** for Resource-based policy statementsChoose **AWS Service**
- For Service, select **other**
- Statement ID: **bedrock-agent-invoke**
- Principal: **bedrock.amazonaws.com**
- Source ARN: **arn:aws:bedrock:&lt;region&gt;:&lt;accountid&gt;:agent/***
- Action: **lambda:InvokeFunction** and **Save**

- Deploy the function

Figure 3 – Set AWS Lambda function timeout value

The function is now ready to act as an Amazon Bedrock Agent and support the following actions:

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
- Dynamic [AWS CodeBuild](https://aws.amazon.com/codebuild/) build script generation with project-specific parameters
- Pipeline parameter injection and configuration
- Multi-stage approval workflow management
- Error handling and detailed logging for troubleshooting

**Amazon Bedrock MLOps Agent**

Use the following steps to create the agent:

- In the console, Navigate to **Amazon Bedrock**
- Select** Agents** from the left navigation panel under Build
- Choose** Create Agent**
- Configure the agent with these settings: Agent Name: *MLOpsOrchestrator*
- Description: *Intelligent assistant for gaming MLOps CI/CD pipeline management*
- Foundation Model: US Anthropic Claude 3.7 Sonnet
- Use the existing service role, *mlops-agent-role* for the agent resource role

- Configure the agent Instructions—provide instructions that establish the agent's identity and capabilities by using the following:

You are an expert MLOps engineer specializing in SageMaker pipeline orchestration. Help users create, manage, and deploy ML models through automated CI/CD pipelines. Always follow AWS best practices and provide clear status updates.

Available actions include:

- Creating CodeConnections for GitHub integration

- Setting up MLOps projects and CI/CD pipelines

- Managing feature stores and MLflow tracking

- Handling model and deployment approvals

Figure 4 – Create Amazon Bedrock Agent

**Amazon Bedrock Agent action groups**

Use the following steps to create action groups:

- In the Agent builder, under Action groups, Select** Add**Enter the group name: **ProjectManagement**
- Enter the following description: **Actions for managing SageMaker MLOps projects and GitHub integration**
- Select the Action group type: **Define with API schemas**
- Under *Action group invocation*, make certain to select**: Select an existing Lambda function**
- Under *Select Lambda function*, select **mlops-project-management**, with *Function version* as **$LATEST**

Figure 5 – Configure Amazon Bedrock Agent action group

- Under *Action group schema*, select** Define via in-line schema editor**
- Download the **MLOps agent OpenAPI schema** from the [GitHub AWS Samples repository](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/mlops-schema.json)
- Select** JSON** from the drop-down and paste the provided OpenAPI schema in the editor
- Choose** Save and exit**

Figure 6 – Create Amazon Bedrock Agent OpenAPI schema

**Use the MLOps agent**

With the agent created and configured, it’s ready to use for launching AWS resources to support an MLOps CI/CD pipeline. As a foundation of the pipeline, an AWS Service Catalog template defines AWS CodeBuild projects, AWS CodePipeline pipelines, and SageMaker AI inference endpoints for staging and production.

Creating an Amazon SageMaker AI project launches these resources with configuration specified with the MLOps agent. Before creating an Amazon SageMaker AI project with the AWS Service Catalog template, you'll need to set up several prerequisites.

These prerequisites include:

- An AWS CodeConnection to access GitHub
- A managed MLflow tracking server
- A feature store with sample features for the MLOps template that handles model building, training, and deployment with third-party Git repositoriesThe Feature Store Group features are based on a [synthetic player churn data set](https://github.com/aws-solutions-library-samples/guidance-for-predicting-player-behavior-with-ai-on-aws/blob/main/assets/examples/player-churn.csv)

For the AWS Service Catalog template, create two empty private GitHub repositories:player-churn-model-buildplayer-churn-model-deployTo use the agent:

- Select** Test and Prepare** in the Amazon Bedrock Agents console
- Enter a prompt to create resources using natural languageStart with **what MLOps tasks can you perform?**
- When using provided, example prompts, note created resources values and replace where appropriate

Figure 7 – Show MLOps tasks

- Use the agent to create a Feature Store group for gaming analytics by using the following prompt:

Create Feature Store group named "player-churn-features" with feature description "player_id as string identifier, player_lifetime as number, player_churn as integer, time_of_day features as floats, cohort_id features as binary flags, event_time as event time feature" and description "Feature group for player churn prediction model containing player behavior and engagement metrics"

Figure 8 – Create a feature store

- Next, Create an Amazon SageMaker AI managed MLflow tracking server by entering the following prompt.  Use your account ID where indicated:

Create MLflow tracking server named "player-churn-tracking-server" with artifact store "s3://game-ml-artifacts-ACCOUNT_ID/mlflow/" and size "Medium" and role_arn "arn:aws:iam::ACCOUNT_ID:role/mlops-agent-role"

Figure 9 – Create a MLflow tracking server

- Use the following prompt to establish GitHub integration:

Create an AWS CodeConnection called "mlops-github" for GitHub integration

Figure 10 – Create an AWS CodeConnection to Github

- To complete AWS CodeConnection setup, select the created connection in the AWS Console and choose **Update pending connection**.
- Select **Install a new app**.
- You will be redirected to GitHub to authenticate and select repository access.
- Choose **Connect** and the connection status will change from **Pending** to **Available**.

With supporting MLOps infrastructure created, navigate to the **MLOpsOrchestrator**

agent in the AWS console.

- Create an Amazon SageMaker AI MLOps project by using the following prompt:

Create an MLOps project named "mlops-player-churn" with GitHub username "your Github username", build repository "player-churn-model-build", deploy repository "player-churn-model-deploy", using connection ARN "your connection arn"

- The MLOps project creates and executes an Amazon SageMaker AI pipeline.  Copy the model package group name from the prompt response.  The pipeline execution adds a model to the Amazon SageMaker AI Model Registry in **Pending manual approval** status.  Approve the model by using the following prompt:

Approve model in model package group "your model package group name"

- Create an MLOps CI/CD Pipeline by using the following:

Build a CI/CD pipeline for project "mlops-player-churn" with model build repository "gitUserName/player-churn-model-build", deploy repository “gitUserName/player-churn-model-deploy”, connection ARN "your connection arn", feature group "player-churn-features", S3 bucket "game-ml-artifacts-ACCOUNT_ID", MLflow server "your-mlflow-arn", and pipeline "player-churn-training-pipeline"

- To verify and visualize the pipeline, in the AWS console, navigate to *AWS CodePipeline*. Select** Pipelines** in the left-hand navigation pane.There will be two pipelines, one for build and another for deploy.

Select the** link of the build project** to view pipeline steps.Figure 12 – Build pipeline

- To deploy a production inference endpoint, navigate to the *AWS CodePipelines* deploy pipeline.Select ApproveDeployment in the DeployStaging box.

Figure 13 – Deploy pipeline

- To trigger CI/CD pipeline execution, push any changed code to the *model-build repository*.

Using an Amazon Bedrock Agent, a complete MLOps model build and deployment of a CI/CD pipeline has been created. Try out additional agent prompts to experiment with the flexibility and function of the agent.

[Amazon SageMaker Canvas](https://aws.amazon.com/sagemaker/ai/canvas/) can be used to connect to data sources (such as transactional databases, data warehouses, Amazon S3) or over 50 other data providers. SageMaker Canvas can be used to feature engineer data and as a data source for the MLOps model build and deploy pipeline.

**Cleanup**

To avoid ongoing charges, navigate to these [AWS services](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/mlops-aws-resource-cleanup-toolkit/RESOURCE_CLEANUP.md) in the console and terminate those resources.

A command line automated [cleanup script](https://github.com/aws-samples/sample-mlops-agent-for-bedrock/blob/main/mlops-aws-resource-cleanup-toolkit/cleanup-by-tags.sh) is available to delete resources as well. The script uses resource tags to safely identify and remove all MLOps deployed resources. The script automatically removes all MLOps resources tagged with *CreatedBy=MLOpsAgent*. Run** cleanup-by-tags.sh** to terminate resources.

**Conclusion**

Building an intelligent MLOps CI/CD pipeline management system using Amazon Bedrock Agents represents an advancement in how gaming teams can approach machine learning operations. Throughout this walkthrough, we've demonstrated how to transform complex, multi-service MLOps workflows into streamlined, conversational interactions that reduce the barrier to entry for gaming analytics.

Contact an [AWS Representative](https://pages.awscloud.com/Amazon-Game-Tech-Contact-Us.html) to know how we can help accelerate your business.

**Further reading**

- [Amazon SageMaker AI workflows](https://docs.aws.amazon.com/sagemaker/latest/dg/workflows.html)
- [Amazon SageMaker Pipelines](https://aws.amazon.com/sagemaker/ai/pipelines/)
- [Amazon SageMaker for MLOps](https://aws.amazon.com/sagemaker/ai/mlops/)
- [MLOps Amazon SageMaker AI notebook samples](https://github.com/aws-samples/mlops-sagemaker-mlflow)
- [Operationalize Machine Learning with Amazon SageMaker MLOps and MLFlow workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/b9405337-9690-4fb2-9f7d-76e6babb7a2c/en-US)