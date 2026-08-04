import boto3
import json
from datetime import datetime
import structlog

logger = structlog.get_logger()

# Initialize SQS client using EC2 IAM Role
sqs_client = boto3.client('sqs', region_name='us-east-1')
QUEUE_NAME = "buyduck-realtime-queue"

def send_event_to_sqs(event_type: str, data: dict, domain: str = "cart"):
    """
    Sends structured business event payloads to Amazon SQS.
    Runs asynchronously and safely without blocking HTTP responses.
    """
    try:
        queue_url = sqs_client.get_queue_url(QueueName=QUEUE_NAME)['QueueUrl']
        
        event_payload = {
            "domain": domain,              # e.g., 'user', 'product', 'cart', 'order'
            "event_type": event_type,        # e.g., 'CHECKOUT', 'ITEM_ADDED', 'USER_CREATED'
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data
        }
        
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(event_payload)
        )
        logger.info("sqs_event_published", event_type=event_type, domain=domain)
    except Exception as e:
        # Non-blocking failure logging
        print(f"SQS Streaming Error: {str(e)}")
        logger.error("sqs_publish_failed", error=str(e), event_type=event_type)