#!/bin/bash
set -e

FUNCTION_NAME="managed-instance-demo"
CAPACITY_PROVIDER_NAME="demo-capacity-provider"
EXECUTION_ROLE_NAME="ManagedInstanceDemoExecutionRole"
OPERATOR_ROLE_NAME="ManagedInstanceDemoOperatorRole"

echo "Getting AWS account information..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region)

echo "Creating IAM roles..."

# Lambda execution role
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name $EXECUTION_ROLE_NAME \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json 2>/dev/null || echo "Execution role already exists"

aws iam attach-role-policy \
  --role-name $EXECUTION_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

# Operator role
aws iam create-role \
  --role-name $OPERATOR_ROLE_NAME \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json 2>/dev/null || echo "Operator role already exists"

aws iam attach-role-policy \
  --role-name $OPERATOR_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AWSLambdaManagedEC2ResourceOperator 2>/dev/null || true

echo "Waiting for IAM roles to propagate..."
sleep 10

echo "Setting up VPC resources..."

VPC_ID=$(aws ec2 create-vpc \
  --cidr-block 10.0.0.0/16 \
  --query 'Vpc.VpcId' \
  --output text 2>/dev/null || aws ec2 describe-vpcs --filters "Name=cidr,Values=10.0.0.0/16" --query 'Vpcs[0].VpcId' --output text)

SUBNET_ID=$(aws ec2 create-subnet \
  --vpc-id $VPC_ID \
  --cidr-block 10.0.1.0/24 \
  --query 'Subnet.SubnetId' \
  --output text 2>/dev/null || aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" "Name=cidr-block,Values=10.0.1.0/24" --query 'Subnets[0].SubnetId' --output text)

SECURITY_GROUP_ID=$(aws ec2 create-security-group \
  --group-name managed-instance-demo-sg \
  --description "Security group for Lambda Managed Instances demo" \
  --vpc-id $VPC_ID \
  --query 'GroupId' \
  --output text 2>/dev/null || aws ec2 describe-security-groups --filters "Name=group-name,Values=managed-instance-demo-sg" --query 'SecurityGroups[0].GroupId' --output text)

echo "Creating capacity provider..."

aws lambda create-capacity-provider \
  --capacity-provider-name $CAPACITY_PROVIDER_NAME \
  --vpc-config SubnetIds=[$SUBNET_ID],SecurityGroupIds=[$SECURITY_GROUP_ID] \
  --permissions-config CapacityProviderOperatorRoleArn=arn:aws:iam::${ACCOUNT_ID}:role/$OPERATOR_ROLE_NAME \
  --instance-requirements Architectures=[x86_64] \
  --capacity-provider-scaling-config MaxVCpuCount=30 2>/dev/null || echo "Capacity provider already exists"

echo "Packaging function..."
zip -q function.zip lambda_function.py

echo "Creating Lambda function..."

aws lambda create-function \
  --function-name $FUNCTION_NAME \
  --package-type Zip \
  --runtime python3.13 \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --role arn:aws:iam::${ACCOUNT_ID}:role/$EXECUTION_ROLE_NAME \
  --architectures x86_64 \
  --memory-size 2048 \
  --ephemeral-storage Size=512 \
  --capacity-provider-config LambdaManagedInstancesCapacityProviderConfig={CapacityProviderArn=arn:aws:lambda:${REGION}:${ACCOUNT_ID}:capacity-provider:$CAPACITY_PROVIDER_NAME} 2>/dev/null || echo "Function already exists"

echo "Publishing function version..."
aws lambda publish-version --function-name $FUNCTION_NAME

echo ""
echo "Deployment complete!"
echo "Function: $FUNCTION_NAME"
echo "Region: $REGION"
echo ""
echo "Test with:"
echo "aws lambda invoke --function-name $FUNCTION_NAME:1 --payload '{\"name\": \"World\"}' response.json && cat response.json"
