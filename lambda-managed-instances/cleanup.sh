#!/bin/bash
set -e

FUNCTION_NAME="managed-instance-demo"
CAPACITY_PROVIDER_NAME="demo-capacity-provider"
EXECUTION_ROLE_NAME="ManagedInstanceDemoExecutionRole"
OPERATOR_ROLE_NAME="ManagedInstanceDemoOperatorRole"

echo "Cleaning up resources..."

echo "Deleting Lambda function..."
aws lambda delete-function --function-name $FUNCTION_NAME 2>/dev/null || echo "Function not found"

echo "Deleting capacity provider..."
aws lambda delete-capacity-provider --capacity-provider-name $CAPACITY_PROVIDER_NAME 2>/dev/null || echo "Capacity provider not found"

echo "Waiting for capacity provider deletion..."
sleep 30

echo "Deleting VPC resources..."
SECURITY_GROUP_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=managed-instance-demo-sg" --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null)
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=cidr,Values=10.0.0.0/16" --query 'Vpcs[0].VpcId' --output text 2>/dev/null)
SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" "Name=cidr-block,Values=10.0.1.0/24" --query 'Subnets[0].SubnetId' --output text 2>/dev/null)

if [ "$SECURITY_GROUP_ID" != "None" ]; then
  aws ec2 delete-security-group --group-id $SECURITY_GROUP_ID 2>/dev/null || echo "Security group not found"
fi

if [ "$SUBNET_ID" != "None" ]; then
  aws ec2 delete-subnet --subnet-id $SUBNET_ID 2>/dev/null || echo "Subnet not found"
fi

if [ "$VPC_ID" != "None" ]; then
  aws ec2 delete-vpc --vpc-id $VPC_ID 2>/dev/null || echo "VPC not found"
fi

echo "Deleting IAM roles..."
aws iam detach-role-policy \
  --role-name $EXECUTION_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole 2>/dev/null || true

aws iam detach-role-policy \
  --role-name $OPERATOR_ROLE_NAME \
  --policy-arn arn:aws:iam::aws:policy/AWSLambdaManagedEC2ResourceOperator 2>/dev/null || true

aws iam delete-role --role-name $EXECUTION_ROLE_NAME 2>/dev/null || echo "Execution role not found"
aws iam delete-role --role-name $OPERATOR_ROLE_NAME 2>/dev/null || echo "Operator role not found"

echo "Cleanup complete!"
