# Architecture Deep Dive

## Workflow Visualization

```
User Query: "AWS Lambda Durable Functions"
    │
    ▼
┌───────────────────────────────────────────────────────────────┐
│  Lambda Durable Function (strands-research-agent-dev:live)    │
├───────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Step 1: Research Agent                              │     │
│  │ ─────────────────────────────────────────────────── │     │
│  │ Strands Agent → Bedrock Claude 3.5 Sonnet          │     │
│  │ System Prompt: "You are a research assistant..."    │     │
│  │                                                      │     │
│  │ Output: Comprehensive research findings             │     │
│  │ ✓ CHECKPOINTED                                      │     │
│  └─────────────────────────────────────────────────────┘     │
│                         │                                     │
│                         ▼                                     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Step 2: Analysis Agent                              │     │
│  │ ─────────────────────────────────────────────────── │     │
│  │ Strands Agent → Bedrock Claude 3.5 Sonnet          │     │
│  │ System Prompt: "You are an analytical expert..."    │     │
│  │ Input: Research findings from Step 1                │     │
│  │                                                      │     │
│  │ Output: Key insights and analysis                   │     │
│  │ ✓ CHECKPOINTED                                      │     │
│  └─────────────────────────────────────────────────────┘     │
│                         │                                     │
│                         ▼                                     │
│  ┌─────────────────────────────────────────────────────┐     │
│  │ Step 3: Summary Agent                               │     │
│  │ ─────────────────────────────────────────────────── │     │
│  │ Strands Agent → Bedrock Claude 3.5 Sonnet          │     │
│  │ System Prompt: "You are a report writer..."         │     │
│  │ Input: Research + Analysis from Steps 1 & 2         │     │
│  │                                                      │     │
│  │ Output: Comprehensive final report                  │     │
│  │ ✓ CHECKPOINTED                                      │     │
│  └─────────────────────────────────────────────────────┘     │
│                         │                                     │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
                    Final Report
```

## Retry Scenario

### Without Durable Functions (Traditional Lambda)

```
Attempt 1:
  Step 1: Research (30s, $0.05) ✓
  Step 2: Analysis (20s, $0.03) ✓
  Step 3: Summary (25s, $0.04) ✗ FAILED

Retry (Attempt 2):
  Step 1: Research (30s, $0.05) ✓ REPEATED
  Step 2: Analysis (20s, $0.03) ✓ REPEATED
  Step 3: Summary (25s, $0.04) ✓ SUCCESS

Total: 150 seconds, $0.24
Wasted: 50 seconds, $0.08
```

### With Durable Functions (This Implementation)

```
Attempt 1:
  Step 1: Research (30s, $0.05) ✓ Checkpointed
  Step 2: Analysis (20s, $0.03) ✓ Checkpointed
  Step 3: Summary (25s, $0.04) ✗ FAILED

Retry (Attempt 2 - Automatic):
  Step 1: Research → Cached (0s, $0.00) ✓
  Step 2: Analysis → Cached (0s, $0.00) ✓
  Step 3: Summary (25s, $0.04) ✓ SUCCESS

Total: 100 seconds, $0.16
Saved: 50 seconds, $0.08 (33% cost reduction)
```

## Component Breakdown

### 1. Strands Agent

Each agent is a self-contained AI system:

```python
agent = Agent(
    model=BedrockModel(model_id="anthropic.claude-3-5-sonnet-20241022-v2:0"),
    system_prompt="You are a research assistant..."
)
result = agent("Research this topic: AWS Lambda")
```

**What happens inside:**
1. Strands invokes Bedrock with system prompt + user query
2. Claude reasons about the task
3. Claude may call tools (if provided)
4. Strands orchestrates the agentic loop
5. Returns final result

### 2. Durable Step

Each step wraps a Strands agent:

```python
research = context.step(
    lambda _: invoke_research_agent(query),
    name="research-agent",
    config=StepConfig(
        retry_strategy=RetryStrategy(max_attempts=3, backoff_rate=2.0)
    )
)
```

**What happens:**
1. Execute the Strands agent
2. Save result to checkpoint storage
3. If failure → retry with exponential backoff
4. On replay → return cached result (no re-execution)

### 3. Durable Execution

The entire workflow is durable:

```python
@durable_execution
def lambda_handler(event: dict, context: DurableContext):
    # All steps are automatically managed
```

**What happens:**
1. Lambda tracks execution state
2. Each step creates a checkpoint
3. On interruption → save state
4. On resume → replay from beginning, skip completed steps
5. Execution can span up to 1 year

## Data Flow

```
Input Event:
{
  "query": "AWS Lambda Durable Functions"
}

↓

Step 1 Output (Checkpointed):
"AWS Lambda Durable Functions enable building resilient multi-step 
applications... [2000 words of research]"

↓

Step 2 Output (Checkpointed):
"Key insights: 1) Checkpointing saves cost, 2) Replay is deterministic... 
[1500 words of analysis]"

↓

Step 3 Output (Checkpointed):
"# Comprehensive Report on AWS Lambda Durable Functions
## Executive Summary
... [3000 words final report]"

↓

Final Response:
{
  "status": "completed",
  "query": "AWS Lambda Durable Functions",
  "research": "...",
  "analysis": "...",
  "report": "..."
}
```

## IAM Permissions

### Required Permissions

```yaml
Policies:
  # Bedrock access for Strands agents
  - Effect: Allow
    Action:
      - bedrock:InvokeModel
      - bedrock:InvokeModelWithResponseStream
    Resource: arn:aws:bedrock:*::foundation-model/*
  
  # Durable execution management
  - Effect: Allow
    Action:
      - lambda:CheckpointDurableExecutions
      - lambda:GetDurableExecutionState
    Resource: arn:aws:lambda:*:*:function:strands-research-agent-*:*
```

## Monitoring

### CloudWatch Metrics

- **Invocations**: Total function invocations
- **Errors**: Failed invocations
- **Duration**: Execution time per invocation
- **Throttles**: Bedrock throttling events

### CloudWatch Logs

```json
{
  "timestamp": "2025-12-18T10:30:00Z",
  "level": "INFO",
  "message": "Starting research agent",
  "query": "AWS Lambda Durable Functions"
}
```

### X-Ray Tracing

- End-to-end request tracing
- Bedrock API call latency
- Step execution timeline
- Error analysis

## Cost Breakdown

### Per Workflow Execution

| Component | Cost | Notes |
|-----------|------|-------|
| Lambda Compute | $0.001 | 75s @ 512MB ARM64 |
| Bedrock - Research | $0.04 | ~8K input + 2K output tokens |
| Bedrock - Analysis | $0.04 | ~10K input + 1.5K output tokens |
| Bedrock - Summary | $0.04 | ~12K input + 3K output tokens |
| **Total** | **~$0.12** | Per successful workflow |

### With Retry (Durable Functions)

| Scenario | Traditional | Durable | Savings |
|----------|-------------|---------|---------|
| No failures | $0.12 | $0.12 | $0.00 |
| 1 retry at Step 3 | $0.24 | $0.16 | $0.08 (33%) |
| 2 retries at Step 3 | $0.36 | $0.20 | $0.16 (44%) |

## Scalability

### Concurrent Executions

- Lambda scales automatically
- Each execution is independent
- No shared state between executions

### Execution Limits

- Max function timeout: 15 minutes per invocation
- Max execution timeout: 1 year total workflow
- Max retention: 90 days execution history

### Throughput

- Limited by Bedrock quotas (tokens per minute)
- Use provisioned throughput for high volume
- Consider request batching for cost optimization

## Security Considerations

### Data Protection

- All data encrypted in transit (TLS)
- Checkpoint data encrypted at rest
- Use AWS KMS for additional encryption

### Access Control

- IAM roles for function execution
- Bedrock model access controls
- VPC deployment for network isolation

### Compliance

- CloudWatch logs for audit trail
- X-Ray for request tracing
- Execution history for compliance

## Future Enhancements

### Potential Additions

1. **Human Review Step**: Add callback for manual approval
2. **Parallel Research**: Multiple agents research different aspects
3. **Tool Integration**: Add web search, database queries
4. **Multi-Agent Collaboration**: Agents communicate with each other
5. **Streaming Output**: Real-time progress updates
6. **Custom Models**: Support for fine-tuned models

### Advanced Patterns

```python
# Parallel research with map
results = context.map(
    topics,
    lambda ctx, topic: ctx.step(
        lambda _: invoke_research_agent(topic),
        name=f"research-{topic}"
    )
)

# Human review callback
approval = context.wait_for_callback(
    lambda callback_id: send_for_review(callback_id, report),
    timeout_seconds=86400  # 24 hours
)
```
