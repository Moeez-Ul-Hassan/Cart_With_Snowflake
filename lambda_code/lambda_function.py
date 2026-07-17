import pandas as pd
import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import io
import pg8000.dbapi
import warnings

warnings.filterwarnings('ignore', '.*pandas only supports SQLAlchemy.*')

def lambda_handler(event, context):
    ssm = boto3.client('ssm', region_name='us-east-1')
    s3_client = boto3.client('s3', region_name='us-east-1')
    
    print("Waking up for Daily Incremental Batch...")
    
    # 1. Connect natively using the PUBLIC IP so Lambda doesn't need a VPC
    conn = pg8000.dbapi.connect(
        user="postgres",
        password="enterprise_password",
        host="98.90.30.252", # <--- UPDATED TO PUBLIC IP
        port=5433,
        database="cart_db"
    )
    
    S3_BUCKET = "buyduck-bronze"
    TABLES = ["users", "products", "carts", "cart_items"]
    DATE_COLUMN = "created_at"
    
    try:
        for table in TABLES:
            param_name = f"/buyduck/watermark/{table}"
            try:
                response = ssm.get_parameter(Name=param_name)
                last_extracted = response['Parameter']['Value']
                print(f"[{table.upper()}] Extracting records newer than {last_extracted}")
                
                query = f"SELECT * FROM {table} WHERE {DATE_COLUMN} > '{last_extracted}' ORDER BY {DATE_COLUMN} ASC"
                df = pd.read_sql(query, conn)
                
                if df.empty:
                    print(f"[{table.upper()}] No new records. Skipping.")
                    continue
                
                df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
                highest_timestamp = df[DATE_COLUMN].max().isoformat()
                
                grouped = df.groupby([df[DATE_COLUMN].dt.year, df[DATE_COLUMN].dt.month, df[DATE_COLUMN].dt.day])
                
                for (year, month, day), group_df in grouped:
                    s3_key = f"batch-data/table={table}/year={year}/month={month:02d}/day={day:02d}/daily_incremental.parquet"
                    
                    table_pa = pa.Table.from_pandas(group_df)
                    out_buffer = io.BytesIO()
                    pq.write_table(table_pa, out_buffer, compression='snappy')
                    
                    s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=out_buffer.getvalue())
                    print(f"[{table.upper()}] Uploaded {len(group_df)} rows to s3://{S3_BUCKET}/{s3_key}")
                
                ssm.put_parameter(Name=param_name, Value=highest_timestamp, Type='String', Overwrite=True)
                print(f"[{table.upper()}] Updated SSM Watermark to {highest_timestamp}")
                
            except Exception as e:
                print(f"[{table.upper()}] Error: {str(e)}")
    finally:
        conn.close()
        
    return {"statusCode": 200, "body": "Daily Batch Pipeline Completed Successfully"}