# Strands Research Agent - Lambda Durable Functions Demo

A multi-step AI research workflow demonstrating **Strands Agents** + **AWS Lambda Durable Functions**: automatic checkpointing, deterministic replay, and cost-effective retry handling for expensive LLM calls.

## Execution Flow

```
┌────────────────────────────────────────────────────────────────┐
│                    Strands Research Agent                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Step 1: Research Agent (Strands + Bedrock Claude)             │
│  └─> Gather comprehensive information on topic                 │
│      • Checkpointed after completion                           │
│      • 3x retry with exponential backoff                       │
│                                                                │
│  Step 2: Analysis Agent (Strands + Bedrock Claude)             │
│  └─> Analyze findings and extract insights                     │
│      • Uses cached research from Step 1 on replay              │
│      • 3x retry with exponential backoff                       │
│                                                                │
│  [Optional] Wait (checkpoint demo)                             │
│  └─> Function suspends, no compute charges                     │
│                                                                │
│  Step 3: Summary Agent (Strands + Bedrock Claude)              │
│  └─> Create comprehensive final report                         │
│      • Uses cached research + analysis on replay               │
│      • 3x retry with exponential backoff                       │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## Why This Pattern?

### Problem Without Durable Functions
- Each Strands agent makes expensive LLM calls (~15-20s each)
- If Step 3 fails, you'd re-run Steps 1 & 2 (wasting time and money)
- Complex state management needed for retries

### Solution With Durable Functions
- **Checkpointing**: Each step's result is saved automatically
- **Deterministic Replay**: On retry, completed steps return cached results instantly
- **Cost Savings**: Never repeat expensive agent calls
- **Automatic Retry**: Built-in retry with exponential backoff

## Checkpoint Demo Results

The demo shows checkpoint recovery in action:

```
First Invocation:
  11:06:07 | [STEP 1] Research completed in 13.2s
  11:06:20 | [STEP 2] Analysis completed in 13.2s
  11:06:33 | [CHECKPOINT DEMO] Waiting 10 seconds...
           | Function suspends (no compute charges)

After Resume (11:06:43):
  11:06:43 | [STEP 1] Research completed in 0.0s  ← INSTANT (cached!)
  11:06:43 | [STEP 2] Analysis completed in 0.0s  ← INSTANT (cached!)
  11:06:43 | [CHECKPOINT DEMO] Resumed from wait!
  11:06:59 | [STEP 3] Summary completed in 15.7s

Final Timing:
  [TIMING] Step 1: 0.0s, Step 2: 0.0s, Step 3: 15.7s
  [CHECKPOINT DEMO] ✅ Steps 1 & 2 were INSTANT - used cached results!
```

**Savings**: ~26 seconds of LLM calls avoided on resume!

## Prerequisites

- **AWS Account** with Bedrock access (us-east-1)
- **AWS SAM CLI** v1.150.0+
- **Python** 3.13+
- **Bedrock Model Access**: Claude 3.5 Sonnet v2

### Enable Bedrock Model Access

1. Go to [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Model access** → **Manage model access**
3. Enable: **Anthropic - Claude 3.5 Sonnet v2**
4. Click **Save changes**

## Quick Start

### 1. Deploy

```bash
cd lambda-durable-functions/strands-research-agent
sam build
sam deploy --guided
```

### 2. Test Normal Workflow

```bash
aws lambda invoke \
  --function-name strands-research-agent-dev:live \
  --region us-east-1 \
  --invocation-type Event \
  --payload '{"query": "serverless computing benefits"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json
```

### 3. Test Checkpoint Demo

```bash
# Run with checkpoint demo enabled
aws lambda invoke \
  --function-name strands-research-agent-dev:live \
  --region us-east-1 \
  --invocation-type Event \
  --payload '{"query": "edge computing trends", "demo_checkpoint": true}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/response.json
```

### 4. Monitor Logs

```bash
# Watch logs in real-time
aws logs tail /aws/lambda/strands-research-agent-dev \
  --region us-east-1 --follow

# Filter for step timing
aws logs filter-log-events \
  --log-group-name /aws/lambda/strands-research-agent-dev \
  --region us-east-1 \
  --filter-pattern "\"[STEP\"" \
  --start-time $(( $(date +%s) * 1000 - 300000 ))
```

## API Reference

### Event Payload

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | "AWS Lambda Durable Functions" | Research topic |
| `demo_checkpoint` | boolean | false | Enable checkpoint demo with 10s wait |

### Response

```json
{
  "status": "completed",
  "query": "your topic",
  "timing": {
    "step1_research": "13.2s",
    "step2_analysis": "16.5s", 
    "step3_summary": "15.7s"
  },
  "checkpoint_demo": true,
  "research": "...",
  "analysis": "...",
  "report": "..."
}
```

## Project Structure

```
strands-research-agent/
├── src/
│   ├── agent.py           # Durable function with Strands agents
│   └── requirements.txt   # Dependencies
├── events/
│   ├── tech_topic.json
│   ├── simple.json
│   └── business_topic.json
├── template.yaml          # SAM template
├── samconfig.toml         # Deployment config
└── README.md
```

## Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| Function Timeout | 15 minutes | Max per invocation |
| Execution Timeout | 1 hour | Max total workflow duration |
| Retention Period | 7 days | Keep execution history |
| Memory | 512 MB | Sufficient for Strands + Bedrock |
| Model | Claude 3.5 Sonnet v2 | Cross-region inference profile |

## Key Concepts

### Durable Functions

```python
@durable_execution
def lambda_handler(event: dict, context: DurableContext):
    # Each step is automatically checkpointed
    result = context.step(
        lambda _: expensive_operation(),
        name="step-name"
    )
    
    # Wait without compute charges
    context.wait(Duration(seconds=10))
```

### Strands Agents

```python
from strands import Agent
from strands.models import BedrockModel

agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
    system_prompt="You are a research assistant..."
)
result = agent("Research this topic: AI agents")
```

### Combined Benefits

| Feature | Strands | Durable Functions |
|---------|---------|-------------------|
| LLM orchestration | ✅ Model-driven | - |
| Checkpointing | - | ✅ Automatic |
| Retry handling | - | ✅ Built-in |
| Cost optimization | - | ✅ Cached results |
| Simple code | ✅ | ✅ |

## Invocation Notes

**Important**: Durable functions with `ExecutionTimeout > 15 minutes` must be invoked **asynchronously**:

```bash
# ✅ Correct - async invocation
aws lambda invoke --invocation-type Event ...

# ❌ Error - sync invocation not supported for long timeouts
aws lambda invoke --invocation-type RequestResponse ...
```

## Troubleshooting

### AccessDeniedException on Bedrock

Enable Claude 3.5 Sonnet v2 in Bedrock Console → Model access

### Model identifier invalid

Use cross-region inference profile: `us.anthropic.claude-3-5-sonnet-20241022-v2:0`

### Cannot synchronously invoke

Durable functions with long execution timeouts require async invocation (`--invocation-type Event`)

## Cost Estimation

**Per Research Workflow:**
- Lambda: ~$0.001 (75s @ 512MB)
- Bedrock: ~$0.12 (3 Claude calls)
- **Total: ~$0.12**

**With Checkpoint Recovery:**
- Cached steps: $0.00 (instant replay)
- Only pay for new operations

## Clean Up

```bash
sam delete --stack-name strands-research-agent-stack --region us-east-1
```

## Resources

- [AWS Lambda Durable Functions](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions.html)
- [Durable Execution SDK](https://github.com/aws/aws-durable-execution-sdk-python)
- [Strands Agents](https://strandsagents.com/)
- [Amazon Bedrock](https://aws.amazon.com/bedrock/)

## License

MIT-0
