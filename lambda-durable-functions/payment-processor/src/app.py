import os
import json
import random
import time
import boto3

from aws_durable_execution_sdk_python import (
    DurableContext,
    StepContext,
    durable_execution,
    durable_step,
)
from aws_durable_execution_sdk_python.config import (
    Duration,
    StepConfig,
    CallbackConfig,
)
from aws_durable_execution_sdk_python.retries import (
    RetryStrategyConfig,
    create_retry_strategy,
)

# Configuration
RISK_SCORE_THRESHOLD = float(os.environ.get("RISK_SCORE_THRESHOLD", "0.7"))
APPROVAL_TIMEOUT_HOURS = int(os.environ.get("APPROVAL_TIMEOUT_HOURS", "24"))
PAYMENTS_TABLE = os.environ.get("PAYMENTS_TABLE", "payments-dev")

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(PAYMENTS_TABLE)

TERMINAL_STATUSES = {'COMPLETED', 'REJECTED'}


def update_payment_status(payment_id: str, status: str, **extra_fields):
    """Update payment record in DynamoDB."""
    try:
        response = table.get_item(Key={'payment_id': payment_id})
        if 'Item' not in response:
            return
        item = response['Item']
        current = item.get('status')
        if current in TERMINAL_STATUSES and status not in TERMINAL_STATUSES:
            return
        # Don't overwrite callback_id or regress from AWAITING_APPROVAL
        if status == 'AWAITING_APPROVAL' and current == 'AWAITING_APPROVAL':
            return  # Already awaiting approval, don't overwrite callback_id
        if 'callback_id' in extra_fields and item.get('callback_id'):
            del extra_fields['callback_id']
    except Exception:
        return
    
    update_expr = "SET #status = :status, updated_at = :updated_at"
    expr_values = {':status': status, ':updated_at': int(time.time() * 1000)}
    expr_names = {'#status': 'status'}
    
    for key, value in extra_fields.items():
        update_expr += f", {key} = :{key}"
        expr_values[f':{key}'] = value
    
    table.update_item(
        Key={'payment_id': payment_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues=expr_values,
        ExpressionAttributeNames=expr_names
    )


@durable_step
def validate_payment(step_context: StepContext, payment_data: dict) -> dict:
    """Validate payment details and create initial record."""
    payment_id = payment_data['payment_id']
    amount = payment_data.get("amount", 0)
    
    step_context.logger.info(f"Validating payment: {payment_id}")
    
    # Create initial record only if not exists
    try:
        table.put_item(
            Item={
                'payment_id': payment_id,
                'amount': str(amount),
                'status': 'VALIDATING',
                'created_at': int(time.time() * 1000),
                'updated_at': int(time.time() * 1000)
            },
            ConditionExpression='attribute_not_exists(payment_id)'
        )
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        pass
    
    if amount <= 0:
        update_payment_status(payment_id, 'REJECTED', reason='invalid_amount')
        raise ValueError("Invalid amount")
    
    update_payment_status(payment_id, 'VALIDATED')
    return {"payment_id": payment_id, "status": "validated", "amount": amount}


@durable_step
def check_fraud(step_context: StepContext, payment_id: str, amount: float) -> dict:
    """Check for fraud - deterministic risk based on amount."""
    step_context.logger.info(f"Checking fraud for payment: {payment_id}, amount: {amount}")
    
    # Deterministic risk score based on amount thresholds
    if amount < 100:
        risk_score = 0.1
    elif amount < 500:
        risk_score = 0.4
    elif amount < 1000:
        risk_score = 0.6
    else:
        risk_score = min(0.7 + (amount / 10000) * 0.3, 1.0)
    
    update_payment_status(payment_id, 'FRAUD_CHECKED', risk_score=str(round(risk_score, 4)))
    
    return {
        "payment_id": payment_id,
        "risk_score": risk_score,
        "requires_review": risk_score > RISK_SCORE_THRESHOLD  # Default threshold is 0.7
    }


@durable_step
def charge_payment(step_context: StepContext, payment_id: str, amount: float) -> dict:
    """Process payment charge."""
    step_context.logger.info(f"Charging payment: {payment_id}, amount: ${amount}")
    
    transaction_id = f"txn_{payment_id}_{random.randint(1000, 9999)}"
    update_payment_status(payment_id, 'CHARGED', transaction_id=transaction_id)
    
    return {"payment_id": payment_id, "transaction_id": transaction_id, "status": "charged"}


@durable_step
def send_notification(step_context: StepContext, payment_id: str, transaction_id: str) -> dict:
    """Send notification and finalize payment."""
    step_context.logger.info(f"Sending notification for payment: {payment_id}")
    update_payment_status(payment_id, 'COMPLETED', transaction_id=transaction_id)
    return {"payment_id": payment_id, "notification_sent": True}


@durable_step
def set_awaiting_approval(step_context: StepContext, payment_id: str, callback_id: str, risk_score: float) -> dict:
    """Set payment to awaiting approval status."""
    update_payment_status(
        payment_id,
        'AWAITING_APPROVAL',
        callback_id=callback_id,
        risk_score=str(round(risk_score, 4))
    )
    return {"status": "awaiting_approval"}


@durable_step
def handle_approval_result(step_context: StepContext, payment_id: str, approved: bool) -> dict:
    """Handle approval result - update status."""
    if approved:
        update_payment_status(payment_id, 'APPROVED')
    else:
        update_payment_status(payment_id, 'REJECTED', reason='approval_denied_or_timeout')
    return {"approved": approved}


@durable_execution
def lambda_handler(event: dict, context: DurableContext) -> dict:
    payment_data = event.get("payment", {})
    # Generate payment_id only if not provided - but store in event for replay consistency
    if not payment_data.get("payment_id"):
        payment_data["payment_id"] = f"pay_{int(time.time() * 1000)}"
    
    context.logger.info(f"Starting payment processing: {payment_data['payment_id']}")
    
    # Step 1: Validate payment - payment_id is now fixed in payment_data
    validated = context.step(validate_payment(payment_data))
    
    # Use payment_id from validated result (checkpointed) for all subsequent operations
    payment_id = validated["payment_id"]
    
    if validated["status"] != "validated":
        return {"payment_id": payment_id, "status": "rejected", "reason": "validation_failed"}
    
    context.logger.info(f"Payment validated: {validated}")
    
    # Step 2: Parallel fraud check and customer verification
    def run_fraud_check(ctx: DurableContext):
        retry_config = RetryStrategyConfig(max_attempts=3, backoff_rate=2.0)
        return ctx.step(
            check_fraud(payment_id, validated["amount"]),
            config=StepConfig(retry_strategy=create_retry_strategy(retry_config))
        )
    
    def verify_customer(ctx: DurableContext):
        return ctx.step(
            lambda step_ctx: {"payment_id": payment_id, "customer_verified": True},
            name="verify-customer"
        )
    
    parallel_results = context.parallel([run_fraud_check, verify_customer], name="fraud-and-customer-checks")
    fraud_check = parallel_results.get_results()[0]
    
    context.logger.info(f"Fraud check complete: {fraud_check}")
    
    # Step 3: Manual review if high risk
    if fraud_check["requires_review"]:
        context.logger.info("High risk detected, requesting manual review")
        
        review_callback = context.create_callback(
            name="fraud-review",
            config=CallbackConfig(timeout=Duration.from_hours(APPROVAL_TIMEOUT_HOURS))
        )
        
        # Update status inside a step
        context.step(set_awaiting_approval(payment_id, review_callback.callback_id, fraud_check["risk_score"]))
        
        context.logger.info(f"Awaiting approval for payment: {payment_id}")
        
        review_result = review_callback.result()
        context.logger.info(f"Review result: {type(review_result)} - {review_result}")
        
        if isinstance(review_result, str):
            review_result = json.loads(review_result)
        
        approved = isinstance(review_result, dict) and review_result.get("approved") == True
        
        # Handle result inside a step
        context.step(handle_approval_result(payment_id, approved))
        
        if not approved:
            return {"payment_id": payment_id, "status": "rejected", "reason": "approval_denied_or_timeout"}
    
    # Step 4: Charge payment
    charge_result = context.step(charge_payment(payment_id, validated["amount"]))
    context.logger.info(f"Payment charged: {charge_result}")
    
    # Step 5: Send notification and finalize (COMPLETED status set inside)
    context.step(send_notification(payment_id, charge_result["transaction_id"]))
    
    context.logger.info(f"Payment processing complete: {payment_id}")
    
    return {
        "payment_id": payment_id,
        "transaction_id": charge_result["transaction_id"],
        "status": "completed",
        "amount": validated["amount"]
    }
