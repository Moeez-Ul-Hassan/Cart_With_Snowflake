import pandas as pd
import sqlalchemy
import boto3
import pyarrow as pa
import pyarrow.parquet as pq
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Connecting via localhost SSH Tunnel (Port 5433)
DB_URL = "postgresql://postgres:enterprise_password@127.0.0.1:5432/cart_db"
S3_BUCKET = "buyduck-bronze"
AWS_REGION = "us-east-1"

# The master list of all tables in your database
TABLE_NAMES = ["users", "products", "carts", "cart_items"] 
DATE_COLUMN = "created_at" 

START_DATE = datetime(2023, 1, 1) 
END_DATE = datetime.now()

# ==========================================
# 2. INITIALIZATION
# ==========================================
engine = sqlalchemy.create_engine(DB_URL)
s3_client = boto3.client('s3', region_name=AWS_REGION)

def upload_to_s3(df, table_name, year, month):
    if df.empty:
        return

    # NEW S3 PATH: Drops data into the new historical baseline folder!
    # Removed the nested date folders. Snowflake will read all files in this directory.
    s3_key = f"historical/{table_name}/bootstrap_{year}_{month:02d}.parquet"
    
    table = pa.Table.from_pandas(df)
    out_buffer = io.BytesIO()
    pq.write_table(table, out_buffer, compression='snappy')
    
    s3_client.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=out_buffer.getvalue()
    )
    print(f"  -> Uploaded: s3://{S3_BUCKET}/{s3_key} | Rows: {len(df)}")

# ==========================================
# 3. THE MULTI-TABLE EXTRACTION ENGINE
# ==========================================
def run_historical_backfill():
    print("🚀 Starting Enterprise Historical Baseline Export...")
    
    for table_name in TABLE_NAMES:
        print("\n==========================================")
        print(f"Processing Table: {table_name.upper()}")
        
        current_start = START_DATE

        while current_start < END_DATE:
            current_end = current_start + relativedelta(months=1)
            if current_end > END_DATE:
                current_end = END_DATE
                
            print(f"Extracting {table_name}: {current_start.date()} to {current_end.date()}")
            
            query = f"""
                SELECT * FROM {table_name} 
                WHERE {DATE_COLUMN} >= '{current_start.strftime('%Y-%m-%d %H:%M:%S')}' 
                AND {DATE_COLUMN} < '{current_end.strftime('%Y-%m-%d %H:%M:%S')}'
                ORDER BY {DATE_COLUMN} ASC
            """
            
            try:
                chunk_df = pd.read_sql(query, engine)
            except Exception as e:
                print(f"❌ Error reading {table_name}. Skipping. Error: {e}")
                break
            
            if not chunk_df.empty:
                chunk_df[DATE_COLUMN] = pd.to_datetime(chunk_df[DATE_COLUMN])
                
                # Upload the monthly chunk directly to the historical folder
                upload_to_s3(chunk_df, table_name, current_start.year, current_start.month)

            current_start = current_end

    print("\n=== 🏁 FULL HISTORICAL BASELINE COMPLETE ===")
    print("Note: No watermarks saved. The realtime SQS streaming pipeline will handle all future data.")
    
if __name__ == "__main__":
    run_historical_backfill()