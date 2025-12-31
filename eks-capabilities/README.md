# EKS Capabilities Demo

This demo showcases all three EKS Capabilities working together to deploy a WordPress application with AWS-managed infrastructure.

## What are EKS Capabilities?

EKS Capabilities are fully managed, Kubernetes-native platform features that run on AWS-owned infrastructure. AWS handles all scaling, patching, and upgrades.

| Capability | Description |
|------------|-------------|
| **ArgoCD** | GitOps continuous deployment |
| **ACK** | AWS Controllers for Kubernetes - manage AWS resources declaratively |
| **kro** | Kube Resource Orchestrator - create custom Kubernetes APIs |

## Demo Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WordPressApp Custom Resource                      │
│                    (Single YAML to deploy all)                       │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         kro (Orchestration)                          │
│              ResourceGraphDefinition manages 10 resources            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  ACK (AWS)    │       │  K8s Native     │       │  CSI Driver     │
├───────────────┤       ├─────────────────┤       ├─────────────────┤
│ • IAM Policy  │       │ • ServiceAccount│       │ • SecretProvider│
│ • IAM Role    │       │ • Deployment    │       │   Class         │
│ • Pod Identity│       │ • Service       │       │                 │
│ • DBSubnetGrp │       │ • Secrets       │       │                 │
│ • RDS MySQL   │       │                 │       │                 │
└───────────────┘       └─────────────────┘       └─────────────────┘
        │                                                   │
        ▼                                                   ▼
┌───────────────┐                                 ┌─────────────────┐
│  AWS Services │                                 │ Secrets Manager │
├───────────────┤                                 ├─────────────────┤
│ • RDS MySQL   │                                 │ • DB Password   │
│ • IAM         │                                 │                 │
│ • EKS         │                                 │                 │
└───────────────┘                                 └─────────────────┘
```

## Resources Managed by kro (10 Total)

| # | Resource | API | Description |
|---|----------|-----|-------------|
| 1 | IAM Policy | `iam.services.k8s.aws` | Secrets Manager access policy |
| 2 | IAM Role | `iam.services.k8s.aws` | Pod Identity role |
| 3 | ServiceAccount | `v1` | K8s service account for pods |
| 4 | PodIdentityAssociation | `eks.services.k8s.aws` | Links SA to IAM role |
| 5 | SecretProviderClass | `secrets-store.csi.x-k8s.io` | Mounts secrets from AWS |
| 6 | DBSubnetGroup | `rds.services.k8s.aws` | RDS network config |
| 7 | DBInstance | `rds.services.k8s.aws` | MySQL 8.0 database |
| 8 | Secret (DB Connection) | `v1` | DB host/port info |
| 9 | Deployment | `apps/v1` | WordPress pods |
| 10 | Service | `v1` | ClusterIP service |

## Prerequisites

1. EKS cluster with capabilities enabled (see `ENABLE_EKS_CAPABILITIES.md`)
2. AWS Secrets Store CSI Driver addon installed
3. EKS Pod Identity Agent addon installed
4. Secret in AWS Secrets Manager with DB password

### Install Required Addons

```bash
# Secrets Store CSI Driver
eksctl create addon --cluster <cluster-name> --name aws-secrets-store-csi-driver-provider --region <region>

# Pod Identity Agent
eksctl create addon --cluster <cluster-name> --name eks-pod-identity-agent --region <region>
```

### Create Secret in Secrets Manager

```bash
aws secretsmanager create-secret \
  --region us-west-2 \
  --name demo-wordpress-db-password \
  --secret-string '{"password":"YourSecurePassword123!"}'
```

## Quick Start

### 1. Apply the ResourceGraphDefinition

```bash
kubectl apply -f wordpress-demo/kro/wordpress-full-rgd.yaml
```

### 2. Verify Custom API is Registered

```bash
kubectl api-resources | grep wordpressapp
# Output: wordpressapps   demo.eks.aws/v1alpha1   true   WordPressApp
```

### 3. Create WordPress Instance

Edit `wordpress-demo/kro/wordpress-instance.yaml` with your values:

```yaml
apiVersion: demo.eks.aws/v1alpha1
kind: WordPressApp
metadata:
  name: demo-wordpress
  namespace: default
spec:
  name: demo-wordpress
  replicas: 2
  dbInstanceClass: db.t3.micro
  storageSize: 20
  subnetIDs:
    - subnet-xxx  # Your private subnet 1
    - subnet-yyy  # Your private subnet 2
    - subnet-zzz  # Your private subnet 3
  clusterName: your-cluster-name
  secretName: demo-wordpress-db-password  # Secrets Manager secret name
```

```bash
kubectl apply -f wordpress-demo/kro/wordpress-instance.yaml
```

### 4. Monitor Deployment

```bash
# Watch WordPressApp status
kubectl get wordpressapp demo-wordpress -w

# Check all resources
kubectl get policy.iam,role.iam,sa,podidentityassociation.eks,dbsubnetgroup.rds,dbinstance.rds,deployment,svc | grep demo-wordpress
```

### 5. Access WordPress

```bash
kubectl port-forward svc/demo-wordpress 8080:80
# Open http://localhost:8080
```

## How It Works

1. **User creates** a `WordPressApp` custom resource
2. **kro** reads the ResourceGraphDefinition and creates all 10 resources
3. **ACK** provisions AWS resources (IAM, RDS, Pod Identity)
4. **CSI Driver** mounts the password from Secrets Manager
5. **WordPress** connects to RDS using the mounted secret
6. **Dependencies** are automatically managed by kro (e.g., RDS waits for subnet group)

## Key Features Demonstrated

### kro (Resource Orchestration)
- Custom API creation (`WordPressApp`)
- Dependency management between resources
- CEL expressions for dynamic values
- Composing ACK + K8s resources

### ACK (AWS Resource Management)
- IAM Policy and Role creation
- EKS Pod Identity Association
- RDS MySQL provisioning
- DBSubnetGroup configuration

### Secrets Manager Integration
- Password stored in AWS Secrets Manager
- CSI driver mounts secret as file
- Pod Identity for authentication
- No hardcoded credentials in manifests

## Cleanup

```bash
# Delete WordPress instance (kro deletes all child resources)
kubectl delete wordpressapp demo-wordpress

# Delete the RGD
kubectl delete resourcegraphdefinition wordpressapp

# Delete Secrets Manager secret
aws secretsmanager delete-secret --secret-id demo-wordpress-db-password --region us-west-2
```

## Files

```
eks-capabilities/
├── ENABLE_EKS_CAPABILITIES.md    # How to enable capabilities
├── README.md                      # This file
└── wordpress-demo/
    └── kro/
        ├── wordpress-full-rgd.yaml    # ResourceGraphDefinition
        └── wordpress-instance.yaml    # Example instance
```
