import json
import boto3
from datetime import datetime
import uuid

s3_client = boto3.client('s3')
S3_BUCKET = "buyduck-bronze"

def lambda_handler(event, context):
    for record in event['Records']:
        try:
            message_body = json.loads(record['body'])
            event_type = message_body.get('event_type', 'unknown_event')
            now = datetime.utcnow()
            event_id = str(uuid.uuid4())
            
            s3_key = f"realtime-data/events/year={now.year}/month={now.month:02d}/day={now.day:02d}/{event_type}_{event_id}.json"
            
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(message_body),
                ContentType="application/json"
            )
            print(f"Processed event: {event_id}")
        except Exception as e:
            print(f"Error: {str(e)}")
            raise e
            
    return {"statusCode": 200, "body": "Success"}