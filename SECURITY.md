# Security Policy

## Reporting Security Issues

The AWS team and community take security bugs in this project seriously. We appreciate your efforts to responsibly disclose your findings, and will make every effort to acknowledge your contributions.

To report a security issue:

- **For the current GitLab repository**: Contact the repository maintainer directly through GitLab issues
- **After migration to AWS Samples**: Use the GitHub Security Advisory "Report a Vulnerability" tab on the aws-samples repository

The AWS team will send a response indicating the next steps in handling your report. After the initial reply to your report, the security team will keep you informed of the progress towards a fix and full announcement, and may ask for additional information or guidance.

## Security Best Practices

### For Users

When deploying this MLOps sample:

#### Authentication & Authorization
- **Use IAM roles** with least privilege principles for all AWS service interactions
- **Never hardcode credentials** in your deployment - use IAM roles and AWS credential providers
- **Enable MFA** on all AWS accounts used for deployment
- **Regularly rotate** access keys if using programmatic access

#### Safe Deployment Practices
- **Always use dry-run mode** before executing cleanup operations:
  ```bash
  ./cleanup-by-tags.sh --dry-run
  ```
- **Use interactive mode** for selective resource management:
  ```bash
  ./cleanup-by-tags.sh --interactive
  ```
- **Review resource lists** carefully before confirming deletions
- **Backup critical data** before running cleanup operations

#### Resource Tagging Security
- **Use specific project tags** to avoid accidental resource deletion
- **Verify tag accuracy** before running cleanup scripts
- **Implement tag governance** in your AWS organization
- **Monitor tag changes** through AWS CloudTrail

#### Monitoring & Auditing
- **Enable AWS CloudTrail** to track all API calls made by the MLOps agent
- **Monitor Lambda function logs** in CloudWatch for unusual activity
- **Set up CloudWatch alarms** for unexpected resource creation/deletion
- **Review IAM access patterns** regularly

### For Developers

#### Code Security
- **Input validation**: All user inputs are validated before processing
- **Error handling**: Comprehensive error handling prevents information disclosure
- **Logging**: Security-relevant events are logged without exposing sensitive data
- **Dependencies**: Keep all dependencies updated and scan for vulnerabilities

#### Secrets Management
- **No hardcoded secrets**: All authentication uses IAM roles or environment variables
- **Environment isolation**: Use separate AWS accounts for development, staging, and production
- **Secure configuration**: Store sensitive configuration in AWS Systems Manager Parameter Store or AWS Secrets Manager

#### Testing Security
- **Test with minimal permissions** to ensure least privilege access works
- **Validate cleanup operations** in isolated test environments
- **Test error conditions** to ensure graceful failure handling
- **Verify resource isolation** between different deployments

## Security Features

### Built-in Safety Mechanisms

This project includes several security and safety features:

#### Destructive Operation Protection
- **Dry-run mode**: Preview all changes before execution
- **Interactive confirmation**: Manual approval for each resource deletion
- **Resource counting**: Validation of expected vs actual resource counts
- **Automatic backups**: JSON backup of all resources before cleanup

#### Precise Resource Targeting
- **Tag-based filtering**: Only affects resources with specific project tags
- **Pattern matching**: Smart filtering to avoid unrelated resources
- **Dependency handling**: Proper deletion order to prevent orphaned resources
- **Rollback information**: Detailed logs for recovery if needed

#### Comprehensive Validation
- **AWS CLI validation**: Ensures proper AWS configuration before operations
- **Permission checking**: Validates required permissions before execution
- **Resource existence**: Confirms resources exist before attempting operations
- **Region validation**: Ensures operations occur in intended AWS regions

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |

This is a sample project intended for demonstration and learning purposes. Always use the latest version and adapt the code for your specific security requirements.

## Security Architecture

### Trust Boundaries

1. **AWS Account Boundary**: All operations occur within your AWS account
2. **IAM Role Boundary**: Lambda function operates with specific IAM permissions
3. **Resource Tag Boundary**: Cleanup operations limited to tagged resources
4. **Region Boundary**: Operations scoped to specific AWS regions

### Data Flow Security

1. **Input**: User commands through Bedrock Agent (natural language)
2. **Processing**: Lambda function with IAM role-based permissions
3. **AWS API Calls**: Authenticated via IAM roles, logged via CloudTrail
4. **Output**: Structured responses with operation status

### Security Controls

- **Authentication**: AWS IAM roles and policies
- **Authorization**: Least privilege access patterns
- **Encryption**: All data encrypted in transit (HTTPS/TLS)
- **Logging**: Comprehensive audit trail via CloudWatch and CloudTrail
- **Monitoring**: CloudWatch metrics and alarms for anomaly detection

## Compliance Considerations

### AWS Well-Architected Security Pillar

This sample follows AWS Well-Architected Framework security principles:

- **Identity and Access Management**: IAM roles with least privilege
- **Detective Controls**: CloudTrail and CloudWatch logging
- **Infrastructure Protection**: VPC and security group best practices
- **Data Protection**: Encryption in transit and at rest
- **Incident Response**: Comprehensive logging for forensic analysis

### Regulatory Compliance

When adapting this sample for production use, consider:

- **Data residency requirements**: Ensure AWS regions comply with local regulations
- **Audit requirements**: CloudTrail provides comprehensive audit logs
- **Data retention**: Configure log retention policies per compliance needs
- **Access controls**: Implement organization-specific access policies

## Incident Response

### If You Suspect a Security Issue

1. **Immediate Actions**:
   - Stop any running operations
   - Preserve logs and evidence
   - Isolate affected resources if possible

2. **Assessment**:
   - Review CloudTrail logs for unauthorized activity
   - Check CloudWatch logs for anomalous behavior
   - Verify resource states and configurations

3. **Reporting**:
   - Contact repository maintainer through GitLab issues (current) or GitHub Security Advisory (after migration)
   - Contact AWS Support for account-level issues
   - Document timeline and impact assessment

4. **Recovery**:
   - Use backup files created by cleanup operations
   - Restore from AWS backups if available
   - Implement additional controls to prevent recurrence

## Security Updates

This project will be updated to address security issues. Monitor the repository for:

- Security advisories and patches
- Dependency updates
- AWS service security recommendations
- Best practice updates

## Contact

For security-related questions about this sample:

- **Repository Issues**: For general security questions and improvements (GitLab currently, GitHub after migration)
- **Security Advisories**: For reporting vulnerabilities (GitHub Security Advisory after migration to aws-samples)
- **AWS Support**: For AWS service-specific security questions

---

**Note**: This is a sample project for demonstration purposes. Always review and adapt the security measures for your specific production requirements and compliance needs.