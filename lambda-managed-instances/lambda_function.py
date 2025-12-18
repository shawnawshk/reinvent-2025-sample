import json
import time

def lambda_handler(event, context):
    """
    Simple Lambda function demonstrating Managed Instances.
    This function can handle multiple concurrent invocations.
    """
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f"Hello from Lambda Managed Instances, {event.get('name', 'Guest')}!",
            'timestamp': time.time(),
            'aws_request_id': context.aws_request_id,
            'function_version': context.function_version,
            'memory_limit': context.memory_limit_in_mb
        })
    }
