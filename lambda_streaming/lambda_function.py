import json
import uuid
from datetime import datetime
import boto3

s3_client = boto3.client('s3')
S3_BUCKET = "buyduck-bronze"

def lambda_handler(event, context):
    # Safely handle manual tests or non-SQS test payloads
    if 'Records' not in event:
        print("⚠️ Received non-SQS test event payload:", json.dumps(event))
        return {
            "statusCode": 200,
            "body": "Test event received successfully (No SQS Records found)."
        }

    for record in event['Records']:
        try:
            raw_body = record.get('body', '')
            
            # Catch plain-text AWS test messages and skip them
            if raw_body == "Test message.":
                print("⚠️ Ignored default AWS SQS plain-text test message.")
                continue

            # Safely attempt to parse the JSON
            try:
                message_body = json.loads(raw_body)
            except json.JSONDecodeError:
                print(f"⚠️ Warning: Record body is not valid JSON. Skipping. Body: {raw_body}")
                continue
            
            # Extract domain and event_type with backward-compatible defaults
            domain = message_body.get('domain', 'cart').lower()
            event_type = message_body.get('event_type', 'UNKNOWN_EVENT').upper()
            
            now = datetime.utcnow()
            event_id = str(uuid.uuid4())
            
            # Dynamic S3 Key according to new architecture specification
            s3_key = (
                f"events/{domain}/{event_type}/"
                f"year={now.year}/month={now.month:02d}/day={now.day:02d}/"
                f"{event_type}_{event_id}.json"
            )
            
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=json.dumps(message_body),
                ContentType="application/json"
            )
            print(f"Successfully landed event in S3: s3://{S3_BUCKET}/{s3_key}")
            
        except Exception as e:
            print(f"❌ Error processing streaming event: {str(e)}")
            raise e
            
    return {"statusCode": 200, "body": "Streaming Events Ingested Successfully"}