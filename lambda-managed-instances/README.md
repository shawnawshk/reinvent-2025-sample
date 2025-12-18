# Lambda Managed Instances Demo

A simple demonstration of AWS Lambda Managed Instances - running Lambda functions on EC2 instances with serverless simplicity.

## What is Lambda Managed Instances?

Lambda Managed Instances allows you to run Lambda functions on Amazon EC2 instances while AWS handles all operational tasks (instance lifecycle, patching, scaling, load balancing). Key benefits:

- **Multi-concurrent execution**: Each execution environment handles multiple requests simultaneously
- **No cold starts**: Pre-provisioned execution environments
- **EC2 pricing**: Leverage Savings Plans and Reserved Instances
- **Specialized hardware**: Access to specific instance types

## Prerequisites

- AWS CLI installed and configured
- IAM permissions to create Lambda functions, capacity providers, and EC2 resources
- Python 3.13+ (for the demo function)

## Quick Start

Run the deployment script:

```bash
./deploy.sh
```

This will:
1. Create required IAM roles
2. Set up VPC resources
3. Create a capacity provider
4. Deploy a simple Lambda function
5. Publish and invoke the function

## Manual Deployment

Follow the steps in `deploy.sh` or see the [AWS documentation](https://docs.aws.amazon.com/lambda/latest/dg/lambda-managed-instances-getting-started.html).

## Testing

Invoke the function:

```bash
aws lambda invoke \
  --function-name managed-instance-demo:1 \
  --payload '{"name": "World"}' \
  response.json

cat response.json
```

## Cleanup

Remove all resources:

```bash
./cleanup.sh
```

## Cost Considerations

- EC2 instance charges (supports Savings Plans/Reserved Instances)
- 15% compute management fee on EC2 costs
- Standard Lambda request charges

## Learn More

- [Lambda Managed Instances Documentation](https://docs.aws.amazon.com/lambda/latest/dg/lambda-managed-instances.html)
- [Announcement Blog Post](https://aws.amazon.com/blogs/aws/introducing-aws-lambda-managed-instances-serverless-simplicity-with-ec2-flexibility/)
