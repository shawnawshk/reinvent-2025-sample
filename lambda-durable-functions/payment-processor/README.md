# Payment Processor - AWS Lambda Durable Functions Demo

A payment processing workflow demonstrating AWS Lambda Durable Functions: parallel execution, automatic retries, manual approvals, and fault tolerance.

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                         Payment Processor                              │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 1: Validate Payment (Sequential - Fail Fast)                │  │
│  │         └─> Invalid? → Reject immediately, save compute cost     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                                   ▼                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 2: Parallel Checks (Independent Operations)                 │  │
│  │         ┌─────────────────────┐  ┌─────────────────────┐         │  │
│  │         │ Fraud Detection     │  │ Customer            │         │  │
│  │         │ (with 3x retry)     │  │ Verification        │         │  │
│  │         └─────────────────────┘  └─────────────────────┘         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                   ┌───────────────┴───────────────┐                    │
│                   ▼                               ▼                    │
│  ┌────────────────────────────┐   ┌────────────────────────────────┐   │
│  │ Low Risk (< 0.7)           │   │ High Risk (≥ 0.7)              │   │
│  │ Amount < $500              │   │ Amount ≥ $500                  │   │
│  │ → Continue to charge       │   │ → Manual Approval Required     │   │
│  └────────────────────────────┘   │   • Notify Approver            │   │
│                   │               │   • Wait up to 24 hours        │   │
│                   │               │     (no compute cost)          │   │
│                   │               │   • Resume on approval         │   │
│                   │               └────────────────────────────────┘   │
│                   │                               │                    │
│                   └───────────────┬───────────────┘                    │
│                                   ▼                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 3: Charge Payment                                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                   │                                    │
│                                   ▼                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Step 4: Send Notification                                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

## Business Logic

### Why This Design?

1. **Validate First (Fail Fast)**: Cheap validation before expensive fraud checks. Invalid payments rejected immediately.

2. **Parallel Checks**: Fraud detection and customer verification are independent—run them concurrently to reduce latency by ~40%.

3. **Risk-Based Routing** (based on payment amount):
   - $0-100 → risk 0.0-0.3 → Auto-approve
   - $100-500 → risk 0.3-0.6 → Auto-approve
   - $500+ → risk 0.6-1.0 → Likely requires manual review (threshold: 0.7)

4. **Human-in-the-Loop**: High-risk payments suspend execution (no compute cost) and wait up to 24 hours for approval.

5. **Automatic Retries**: Fraud check has 3x retry with exponential backoff for transient failures.

### Durable Functions Primitives Used

| Primitive | Usage | Benefit |
|-----------|-------|---------|
| **Steps** | Each operation is a step | Automatic checkpointing, resume from failure |
| **Parallel** | Fraud + Customer checks | Concurrent execution, reduced latency |
| **Callback** | Manual approval | Suspend without compute cost |
| **Retry Strategy** | Fraud detection | Handle transient failures automatically |

## Quick Start

### Deploy
```bash
cd payment-processor
sam build
sam deploy --guided
```

### Test Low-Risk Payment ($49.99 → auto-completes)
```bash
aws lambda invoke \
  --function-name payment-processor-dev:live \
  --invocation-type Event \
  --cli-binary-format raw-in-base64-out \
  --payload file://events/low_risk.json \
  --region us-east-1 \
  response.json
```

### Test High-Risk Payment ($9999.99 → requires approval)
```bash
aws lambda invoke \
  --function-name payment-processor-dev:live \
  --invocation-type Event \
  --cli-binary-format raw-in-base64-out \
  --payload file://events/high_risk.json \
  --region us-east-1 \
  response.json
```

### Monitor
```bash
aws logs tail /aws/lambda/payment-processor --since 5m --follow
```

### Approve High-Risk Payment (via SDK)
```python
import boto3
lambda_client = boto3.client('lambda', region_name='us-east-1')
lambda_client.send_durable_execution_callback_success(
    CallbackId='<callback_id_from_logs>',
    Result='{"approved": true}'
)
```

## Project Structure

```
payment-processor/
├── src/app.py           # Lambda function code
├── template.yaml        # SAM infrastructure
├── samconfig.toml       # Deployment config
└── README.md
```

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Execution Timeout | 1 hour | Max total workflow duration |
| Callback Timeout | 24 hours | Manual approval window |
| Risk Threshold | 0.7 | Score above this requires approval |
| Retry Attempts | 3 | Fraud check retries |
| Backoff Rate | 2x | Exponential backoff |
| Failure Rate | 20% | Simulated fraud API failures |

### Risk Scoring (based on amount)
| Amount | Risk Score Range | Likely Outcome |
|--------|------------------|----------------|
| $0-100 | 0.0-0.3 | Auto-approve |
| $100-500 | 0.3-0.6 | Auto-approve |
| $500+ | 0.6-1.0 | Manual review |

## Development

Fast code sync (no CloudFormation):
```bash
sam sync --stack-name payment-processor-stack --code --watch
```

## Resources

- [Lambda Durable Functions Docs](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions.html)
- [Best Practices](https://docs.aws.amazon.com/lambda/latest/dg/durable-best-practices.html)
