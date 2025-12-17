import json
import boto3
import os
import urllib.parse
import time
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

PAYMENTS_TABLE = os.environ.get('PAYMENTS_TABLE', 'payments-dev')
REGION = os.environ.get('AWS_REGION', 'us-east-1')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(PAYMENTS_TABLE)


def lambda_handler(event, context):
    """Admin API for payment management."""
    http_method = event.get('httpMethod', event.get('requestContext', {}).get('http', {}).get('method'))
    path = event.get('path', event.get('rawPath', ''))
    
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    
    if http_method == 'OPTIONS':
        return {'statusCode': 200, 'headers': headers, 'body': ''}
    
    query_params = event.get('queryStringParameters') or {}
    
    if path.endswith('/pending') and http_method == 'GET':
        return get_pending_approvals(headers)
    elif path.endswith('/payments') and http_method == 'GET':
        return get_all_payments(headers, query_params)
    elif path.endswith('/approve') and http_method == 'POST':
        return handle_approval(event, headers, approved=True)
    elif path.endswith('/reject') and http_method == 'POST':
        return handle_approval(event, headers, approved=False)
    elif path.endswith('/clear') and http_method == 'POST':
        return clear_all_payments(headers)
    
    return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Not found'})}


def clear_all_payments(headers):
    """Delete all payment records from DynamoDB."""
    try:
        response = table.scan(ProjectionExpression='payment_id')
        items = response.get('Items', [])
        deleted = 0
        for item in items:
            table.delete_item(Key={'payment_id': item['payment_id']})
            deleted += 1
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'deleted': deleted})}
    except Exception as e:
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': str(e)})}


def get_pending_approvals(headers):
    """Get payments awaiting approval from DynamoDB."""
    try:
        response = table.query(
            IndexName='status-index',
            KeyConditionExpression='#status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'AWAITING_APPROVAL'}
        )
        
        pending = [{
            'payment_id': item['payment_id'],
            'amount': item.get('amount', '0'),
            'risk_score': float(item.get('risk_score', '0')),
            'callback_id': item.get('callback_id', ''),
            'created_at': int(item.get('created_at', 0)),
            'updated_at': int(item.get('updated_at', 0))
        } for item in response.get('Items', [])]
        
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'pending': pending})}
    except Exception as e:
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': str(e)})}


def get_all_payments(headers, query_params=None):
    """Get payments from DynamoDB, optionally filtered by status."""
    try:
        status = query_params.get('status') if query_params else None
        
        if status:
            response = table.query(
                IndexName='status-index',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={':status': status},
                Limit=100
            )
        else:
            response = table.scan(Limit=100)
        
        payments = [{
            'payment_id': item['payment_id'],
            'amount': item.get('amount', '0'),
            'status': item.get('status', 'UNKNOWN'),
            'risk_score': item.get('risk_score', '0'),
            'created_at': int(item.get('created_at', 0)),
            'updated_at': int(item.get('updated_at', 0)),
            'transaction_id': item.get('transaction_id', ''),
            'reason': item.get('reason', '')
        } for item in response.get('Items', [])]
        
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'payments': payments})}
    except Exception as e:
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': str(e)})}


def handle_approval(event, headers, approved):
    """Process approval/rejection and send callback."""
    import urllib.request
    import urllib.error
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.session import Session
    
    try:
        body = json.loads(event.get('body', '{}'))
        payment_id = body.get('payment_id')
        
        if not payment_id:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'payment_id required'})}
        
        # Get payment from DynamoDB
        response = table.get_item(Key={'payment_id': payment_id})
        item = response.get('Item')
        
        if not item:
            return {'statusCode': 404, 'headers': headers, 'body': json.dumps({'error': 'Payment not found'})}
        
        if item.get('status') != 'AWAITING_APPROVAL':
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': f"Payment status is {item.get('status')}, not AWAITING_APPROVAL"})}
        
        callback_id = item.get('callback_id')
        if not callback_id:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'No callback_id found'})}
        
        # Send callback to Lambda
        encoded_callback_id = urllib.parse.quote(callback_id, safe='')
        
        if approved:
            url = f'https://lambda.{REGION}.amazonaws.com/2025-12-01/durable-execution-callbacks/{encoded_callback_id}/succeed'
            payload = json.dumps({'approved': True, 'reviewer': 'admin'})
            new_status = 'APPROVED'
        else:
            url = f'https://lambda.{REGION}.amazonaws.com/2025-12-01/durable-execution-callbacks/{encoded_callback_id}/fail'
            payload = json.dumps({'error': 'Rejected by admin'})
            new_status = 'REJECTED'
        
        session = Session()
        credentials = session.get_credentials()
        request = AWSRequest(method='POST', url=url, data=payload, headers={'Content-Type': 'application/json'})
        SigV4Auth(credentials, 'lambda', REGION).add_auth(request)
        
        req = urllib.request.Request(url, data=payload.encode(), headers=dict(request.headers), method='POST')
        logger.info(f"Sending callback to: {url}")
        logger.info(f"Callback payload: {payload}")
        
        try:
            with urllib.request.urlopen(req) as response:
                resp_body = response.read().decode()
                logger.info(f"Callback response: {response.status} - {resp_body}")
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ''
            logger.error(f"Callback error: {e.code} - {error_body}")
            if e.code != 400:
                raise
        
        # Update payment status in DynamoDB
        table.update_item(
            Key={'payment_id': payment_id},
            UpdateExpression='SET #status = :status, updated_at = :updated_at, reviewer = :reviewer',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': new_status,
                ':updated_at': int(time.time() * 1000),
                ':reviewer': 'admin'
            }
        )
        
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'success': True, 'approved': approved, 'payment_id': payment_id})}
    except Exception as e:
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': str(e)})}
