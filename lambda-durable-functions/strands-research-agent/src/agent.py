"""
Strands Research Agent with Lambda Durable Functions

Demonstrates a multi-step research workflow where each Strands agent call
is checkpointed. If any step fails, the workflow resumes from the last
checkpoint without re-executing expensive agent calls.
"""

from aws_durable_execution_sdk_python import DurableContext, durable_execution
from aws_durable_execution_sdk_python.config import StepConfig
from aws_durable_execution_sdk_python.retries import RetryDecision, Duration
from strands import Agent
from strands.models import BedrockModel


def invoke_research_agent(query: str) -> str:
    """
    Research agent that gathers information on a topic.
    Uses Strands to orchestrate LLM calls with tools.
    """
    agent = Agent(
        model=BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        system_prompt="""You are a research assistant. Your task is to gather 
        comprehensive information about the given topic. Focus on:
        - Key facts and definitions
        - Recent developments
        - Important statistics or data points
        - Notable examples or use cases
        
        Be thorough but concise. Cite sources when possible.""",
    )
    
    result = agent(f"Research this topic: {query}")
    return result.message["content"][0]["text"]


def invoke_analysis_agent(research_findings: str) -> str:
    """
    Analysis agent that evaluates research findings.
    Identifies patterns, insights, and implications.
    """
    agent = Agent(
        model=BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        system_prompt="""You are an analytical expert. Your task is to analyze 
        research findings and extract insights. Focus on:
        - Key patterns and trends
        - Important implications
        - Potential challenges or opportunities
        - Critical insights that stand out
        
        Provide clear, actionable analysis.""",
    )
    
    result = agent(f"Analyze these research findings:\n\n{research_findings}")
    return result.message["content"][0]["text"]


def invoke_summary_agent(research: str, analysis: str, query: str) -> str:
    """
    Summary agent that creates a comprehensive final report.
    Synthesizes research and analysis into a cohesive document.
    """
    agent = Agent(
        model=BedrockModel(model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
        system_prompt="""You are a report writer. Your task is to create a 
        comprehensive, well-structured report that synthesizes research and 
        analysis. The report should:
        - Have a clear executive summary
        - Present findings in a logical flow
        - Include key insights and recommendations
        - Be professional and easy to understand
        
        Format the report with clear sections and headings.""",
    )
    
    prompt = f"""Create a comprehensive report on: {query}

Research Findings:
{research}

Analysis:
{analysis}

Generate a well-structured final report."""
    
    result = agent(prompt)
    return result.message["content"][0]["text"]


class SimulatedFailure(Exception):
    """Simulated failure for demo purposes."""
    pass


@durable_execution
def lambda_handler(event: dict, context: DurableContext):
    """
    Main handler for the research workflow with checkpoint demo.
    
    Demo modes:
    - Normal: {"query": "topic"} - runs full workflow
    - Demo checkpoint: {"query": "topic", "demo_checkpoint": true}
      → Runs steps 1 & 2, then waits 10s, then step 3
      → On resume, steps 1 & 2 SKIP (cached), only step 3 runs
    
    The wait demonstrates checkpoint recovery - when the function
    resumes after the wait, completed steps return cached results
    instantly without re-executing the expensive LLM calls.
    """
    import time
    
    event = event or {}
    query = event.get("query", "AWS Lambda Durable Functions")
    demo_checkpoint = event.get("demo_checkpoint", False)
    
    # Define retry strategy for Bedrock calls
    def bedrock_retry_strategy(error: Exception, attempt_count: int) -> RetryDecision:
        if attempt_count >= 3:
            return RetryDecision.no_retry()
        delay_seconds = 2 * (2 ** (attempt_count - 1))
        return RetryDecision.retry(Duration(seconds=delay_seconds))
    
    # Step 1: Research agent gathers information
    print(f"[STEP 1] Starting research agent for: {query}")
    start = time.time()
    research = context.step(
        lambda _: invoke_research_agent(query),
        name="research-agent",
        config=StepConfig(retry_strategy=bedrock_retry_strategy),
    )
    duration1 = time.time() - start
    print(f"[STEP 1] Research completed in {duration1:.1f}s")
    
    # Step 2: Analysis agent evaluates findings
    print(f"[STEP 2] Starting analysis agent...")
    start = time.time()
    analysis = context.step(
        lambda _: invoke_analysis_agent(research),
        name="analysis-agent",
        config=StepConfig(retry_strategy=bedrock_retry_strategy),
    )
    duration2 = time.time() - start
    print(f"[STEP 2] Analysis completed in {duration2:.1f}s")
    
    # Demo checkpoint: wait to show replay behavior
    if demo_checkpoint:
        print("[CHECKPOINT DEMO] Waiting 10 seconds...")
        print("[CHECKPOINT DEMO] Function will suspend and resume.")
        print("[CHECKPOINT DEMO] On resume, steps 1 & 2 will SKIP (cached)!")
        context.wait(Duration(seconds=10))  # Wait 10 seconds - function suspends here
        print("[CHECKPOINT DEMO] Resumed from wait!")
    
    # Step 3: Summary agent creates final report
    print(f"[STEP 3] Starting summary agent...")
    start = time.time()
    report = context.step(
        lambda _: invoke_summary_agent(research, analysis, query),
        name="summary-agent",
        config=StepConfig(retry_strategy=bedrock_retry_strategy),
    )
    duration3 = time.time() - start
    print(f"[STEP 3] Summary completed in {duration3:.1f}s")
    
    # Show timing summary
    print(f"\n[TIMING] Step 1: {duration1:.1f}s, Step 2: {duration2:.1f}s, Step 3: {duration3:.1f}s")
    if demo_checkpoint and duration1 < 1 and duration2 < 1:
        print("[CHECKPOINT DEMO] ✅ Steps 1 & 2 were INSTANT - used cached results!")
    
    return {
        "status": "completed",
        "query": query,
        "timing": {
            "step1_research": f"{duration1:.1f}s",
            "step2_analysis": f"{duration2:.1f}s",
            "step3_summary": f"{duration3:.1f}s",
        },
        "checkpoint_demo": demo_checkpoint,
        "research": research[:500] + "..." if len(research) > 500 else research,
        "analysis": analysis[:500] + "..." if len(analysis) > 500 else analysis,
        "report": report,
    }
