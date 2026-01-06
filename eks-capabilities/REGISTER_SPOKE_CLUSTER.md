# Registering a Spoke Cluster to EKS ArgoCD Capability

This guide covers how to register a new EKS cluster (spoke) to an existing EKS ArgoCD Capability (hub) using a dedicated project.

## Prerequisites

- Hub cluster with ArgoCD Capability enabled
- ArgoCD Capability IAM role ARN (e.g., `ArgoCDCapabilityRole`)
- kubectl configured for hub cluster

## Step 1: Grant ArgoCD Access to Spoke Cluster

Create an access entry and associate cluster admin policy on the spoke cluster:

```bash
# Create access entry
aws eks create-access-entry \
  --cluster-name <spoke-cluster> \
  --region <region> \
  --principal-arn arn:aws:iam::<account-id>:role/ArgoCDCapabilityRole

# Associate cluster admin policy
aws eks associate-access-policy \
  --cluster-name <spoke-cluster> \
  --region <region> \
  --principal-arn arn:aws:iam::<account-id>:role/ArgoCDCapabilityRole \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster
```

## Step 2: Create ArgoCD Project

Create a dedicated project for spoke workloads (skip if already exists):

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: spoke-workloads
  namespace: argocd
spec:
  destinations:
    - namespace: '*'
      name: <spoke-cluster>  # Add each spoke cluster
  sourceRepos:
    - '*'
  clusterResourceWhitelist:
    - group: '*'
      kind: '*'
  sourceNamespaces:
    - argocd  # Required for apps in argocd namespace
```

To add more clusters to an existing project:

```bash
kubectl patch appproject spoke-workloads -n argocd --type=json \
  -p='[{"op": "add", "path": "/spec/destinations/-", "value": {"namespace": "*", "name": "<new-spoke-cluster>"}}]'
```

## Step 3: Register Cluster via Secret

Create a Kubernetes secret to register the spoke cluster:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: <spoke-cluster>
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: cluster
    environment: dev  # Optional: for ApplicationSet selectors
  annotations:
    region: <region>  # Optional: metadata
stringData:
  name: <spoke-cluster>
  server: arn:aws:eks:<region>:<account-id>:cluster/<spoke-cluster>
  project: spoke-workloads
```

> **Important**: The `server` field must be the EKS cluster ARN, not the Kubernetes API URL or IAM role ARN.

## Step 4: Deploy Application

Create an ArgoCD Application targeting the spoke cluster:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: spoke-workloads
  source:
    repoURL: https://github.com/org/repo
    targetRevision: HEAD
    path: .
  destination:
    name: <spoke-cluster>  # Matches the secret name
    namespace: default
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
```

## Quick Reference

| Field | Value | Note |
|-------|-------|------|
| `server` in Secret | EKS cluster ARN | `arn:aws:eks:<region>:<account>:cluster/<name>` |
| `destination.name` | Cluster secret name | Not the server URL |
| `sourceNamespaces` | `argocd` | Required in AppProject |

## Troubleshooting

### Application stuck in Unknown status

Check if the project allows the application:

```bash
kubectl get application <app-name> -n argocd -o jsonpath='{.status.conditions[*].message}'
```

If you see "not permitted to use project", ensure `sourceNamespaces: [argocd]` is set in the AppProject.

### Cluster not reachable

Verify access entry exists:

```bash
aws eks list-access-entries --cluster-name <spoke-cluster> --region <region>
```

Verify access policy is associated:

```bash
aws eks list-associated-access-policies \
  --cluster-name <spoke-cluster> \
  --region <region> \
  --principal-arn arn:aws:iam::<account-id>:role/ArgoCDCapabilityRole
```

### Force refresh application

```bash
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
```
