# Enable EKS Capabilities on an EKS Cluster

This guide shows how to enable all three EKS Capabilities (ArgoCD, ACK, and kro) on an existing Amazon EKS cluster.

## What are EKS Capabilities?

EKS Capabilities are fully managed, Kubernetes-native platform features that run on AWS-owned infrastructure. AWS handles all scaling, patching, and upgrades. The three capabilities are:

- **ArgoCD** - GitOps continuous deployment
- **ACK** (AWS Controllers for Kubernetes) - Manage AWS resources from Kubernetes
- **kro** (Kube Resource Orchestrator) - Create custom Kubernetes APIs

## Prerequisites

- Existing EKS cluster
- AWS CLI configured
- `kubectl` configured for your cluster
- AWS Identity Center configured (required for ArgoCD)

## Required Addons for WordPress Demo

After enabling EKS Capabilities, install these addons for the WordPress demo:

```bash
# Secrets Store CSI Driver (for Secrets Manager integration)
eksctl create addon --cluster <cluster-name> --name aws-secrets-store-csi-driver-provider --region <region>

# Pod Identity Agent (for IAM authentication)
eksctl create addon --cluster <cluster-name> --name eks-pod-identity-agent --region <region>
```

## 1. Enable ArgoCD Capability

### Create IAM Role

```bash
cat > argocd-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "capabilities.eks.amazonaws.com"
      },
      "Action": [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
    }
  ]
}
EOF

aws iam create-role \
  --role-name ArgoCDCapabilityRole \
  --assume-role-policy-document file://argocd-trust-policy.json
```

### Get Identity Center Configuration

```bash
# Get Identity Center instance (typically in us-east-1)
IDC_INSTANCE_ARN=$(aws sso-admin list-instances --region us-east-1 --query 'Instances[0].InstanceArn' --output text)
IDC_REGION="us-east-1"

# Get Identity Store ID
IDC_STORE_ID=$(aws sso-admin list-instances --region us-east-1 --query 'Instances[0].IdentityStoreId' --output text)

# Get a user ID to assign as admin
IDC_USER_ID=$(aws identitystore list-users \
  --region us-east-1 \
  --identity-store-id $IDC_STORE_ID \
  --query 'Users[0].UserId' \
  --output text)

echo "IDC_INSTANCE_ARN=$IDC_INSTANCE_ARN"
echo "IDC_USER_ID=$IDC_USER_ID"
```

### Create ArgoCD Capability

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
CLUSTER_NAME="your-cluster-name"
REGION="us-west-2"

aws eks create-capability \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --capability-name argocd \
  --type ARGOCD \
  --role-arn arn:aws:iam::$ACCOUNT_ID:role/ArgoCDCapabilityRole \
  --delete-propagation-policy RETAIN \
  --configuration '{
    "argoCd": {
      "awsIdc": {
        "idcInstanceArn": "'$IDC_INSTANCE_ARN'",
        "idcRegion": "'$IDC_REGION'"
      },
      "rbacRoleMappings": [{
        "role": "ADMIN",
        "identities": [{
          "id": "'$IDC_USER_ID'",
          "type": "SSO_USER"
        }]
      }]
    }
  }'
```

### Verify ArgoCD is Active

```bash
aws eks describe-capability \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --capability-name argocd \
  --query 'capability.status' \
  --output text

# Check custom resources
kubectl api-resources | grep argoproj.io
```

## 2. Enable ACK Capability

### Create IAM Role

```bash
cat > ack-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "capabilities.eks.amazonaws.com"
      },
      "Action": [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
    }
  ]
}
EOF

aws iam create-role \
  --role-name ACKCapabilityRole \
  --assume-role-policy-document file://ack-trust-policy.json

# Attach permissions (use AdministratorAccess for demo, restrict for production)
aws iam attach-role-policy \
  --role-name ACKCapabilityRole \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
```

### Create ACK Capability

```bash
aws eks create-capability \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --capability-name ack \
  --type ACK \
  --role-arn arn:aws:iam::$ACCOUNT_ID:role/ACKCapabilityRole \
  --delete-propagation-policy RETAIN
```

### Verify ACK is Active

```bash
aws eks describe-capability \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --capability-name ack \
  --query 'capability.status' \
  --output text

# Check custom resources
kubectl api-resources | grep services.k8s.aws
```

## 3. Enable kro Capability

### Create IAM Role

```bash
cat > kro-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "capabilities.eks.amazonaws.com"
      },
      "Action": [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
    }
  ]
}
EOF

aws iam create-role \
  --role-name KROCapabilityRole \
  --assume-role-policy-document file://kro-trust-policy.json
```

### Create kro Capability

```bash
aws eks create-capability \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --capability-name kro \
  --type KRO \
  --role-arn arn:aws:iam::$ACCOUNT_ID:role/KROCapabilityRole \
  --delete-propagation-policy RETAIN
```

### Grant kro Permissions

```bash
aws eks associate-access-policy \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --principal-arn arn:aws:iam::$ACCOUNT_ID:role/KROCapabilityRole \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

### Verify kro is Active

```bash
aws eks describe-capability \
  --region $REGION \
  --cluster-name $CLUSTER_NAME \
  --capability-name kro \
  --query 'capability.status' \
  --output text

# Check custom resources
kubectl api-resources | grep kro.run
```

## Verify All Capabilities

```bash
# List all capabilities
aws eks list-capabilities --region $REGION --cluster-name $CLUSTER_NAME --output table

# Check all custom resources
kubectl api-resources | grep -E "(argoproj.io|services.k8s.aws|kro.run)"
```

## Next Steps

### ArgoCD
- Access UI through EKS console or server URL
- Configure Git repository access
- Create Applications to deploy from Git

### ACK
- Create AWS resources using Kubernetes manifests
- Example: S3 buckets, DynamoDB tables, Lambda functions

### kro
- Define ResourceGraphDefinitions
- Create custom APIs composing multiple resources

## References

- [EKS Capabilities Documentation](https://docs.aws.amazon.com/eks/latest/userguide/capabilities.html)
- [ArgoCD Capability](https://docs.aws.amazon.com/eks/latest/userguide/working-with-argocd.html)
- [ACK Capability](https://docs.aws.amazon.com/eks/latest/userguide/ack.html)
- [kro Capability](https://docs.aws.amazon.com/eks/latest/userguide/kro.html)
