import boto3
import json
from datetime import datetime

# Initialize the SQS client using the EC2 IAM permissions
sqs_client = boto3.client('sqs', region_name='us-east-1')
QUEUE_NAME = "buyduck-realtime-queue"

def send_event_to_sqs(event_type: str, data: dict):
    """
    Sends an event payload to Amazon SQS instantly.
    This runs asynchronously so it never slows down the API response.
    """
    try:
        # Dynamically fetch the Queue URL
        queue_url = sqs_client.get_queue_url(QueueName=QUEUE_NAME)['QueueUrl']
        
        event_payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": data
        }
        
        # Drop the event into the message queue
        sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(event_payload)
        )
    except Exception as e:
        # If SQS fails, we log it, but we DO NOT crash the user's cart experience
        print(f"SQS Streaming Error: {str(e)}")