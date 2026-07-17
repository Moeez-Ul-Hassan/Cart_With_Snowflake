provider "aws" { 
  region = "us-east-1" 
} 

# ==========================================
# 1. The Firewall (Security Group)
# ==========================================
resource "aws_security_group" "enterprise_cart_sg" { 
  name        = "enterprise-cart-security-group" 
  description = "Allow SSH, FastAPI, and PostgreSQL inbound traffic" 

  ingress { 
    description = "SSH Access" 
    from_port   = 22 
    to_port     = 22 
    protocol    = "tcp" 
    cidr_blocks = ["0.0.0.0/0"] 
  } 

  ingress { 
    description = "HTTP Traffic for Lets Encrypt and Web" 
    from_port   = 80 
    to_port     = 80 
    protocol    = "tcp" 
    cidr_blocks = ["0.0.0.0/0"] 
  } 

  ingress { 
    description = "HTTPS Traffic (Secure NGINX API)" 
    from_port   = 443 
    to_port     = 443 
    protocol    = "tcp" 
    cidr_blocks = ["0.0.0.0/0"] 
  } 

  ingress { 
    description = "PostgreSQL Database (Legacy Port)" 
    from_port   = 5432 
    to_port     = 5432 
    protocol    = "tcp" 
    cidr_blocks = ["0.0.0.0/0"] 
  } 

  ingress {
    description = "Lambda to Postgres Port (Public)"
    from_port   = 5433
    to_port     = 5433
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] 
  }

  egress { 
    description = "Allow all outbound internet access" 
    from_port   = 0 
    to_port     = 0 
    protocol    = "-1" 
    cidr_blocks = ["0.0.0.0/0"] 
  } 
} 

# ==========================================
# 2. The EC2 Server & Elastic IP
# ==========================================
resource "aws_instance" "cart_server" { 
  ami           = "ami-04b70fa74e45c3917" 
  instance_type = "t3.micro"              
  key_name      = "cart-key"              
  
  vpc_security_group_ids = [aws_security_group.enterprise_cart_sg.id] 

  # NEW: Grants FastAPI permission to send messages to SQS
  iam_instance_profile = aws_iam_instance_profile.ec2_sqs_profile.name
  
  root_block_device { 
    volume_size = 30 
    volume_type = "gp2"                   
  } 

  user_data = <<-EOF
              #!/bin/bash 
              apt-get update -y 
              apt-get install -y docker.io docker-compose git python3-pip python3-venv 
              systemctl start docker 
              systemctl enable docker 
              NEW_USER="cartadmin" 
              useradd -m -s /bin/bash $NEW_USER 
              usermod -aG sudo $NEW_USER 
              usermod -aG docker $NEW_USER 
              echo "$NEW_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/$NEW_USER 
              mkdir -p /home/$NEW_USER/.ssh 
              cp /home/ubuntu/.ssh/authorized_keys /home/$NEW_USER/.ssh/ 
              chown -R $NEW_USER:$NEW_USER /home/$NEW_USER/.ssh 
              chmod 700 /home/$NEW_USER/.ssh 
              chmod 600 /home/$NEW_USER/.ssh/authorized_keys 
              EOF

  tags = { 
    Name = "Enterprise-Cart-Server" 
  } 
} 

resource "aws_eip" "cart_server_eip" {
  instance = aws_instance.cart_server.id
  domain   = "vpc"
  tags = { Name = "Enterprise-Cart-Static-IP" }
}

output "server_public_ip" { 
  description = "The PERMANENT public IP address of your server" 
  value       = aws_eip.cart_server_eip.public_ip 
}

# ==========================================
# 3. The S3 Bronze Layer Storage Bucket
# ==========================================
resource "aws_s3_bucket" "buyduck_bronze" {
  bucket        = "buyduck-bronze"
  force_destroy = true 
}

# ==========================================
# 4. PHASE 1: SERVERLESS BATCH PIPELINE
# ==========================================
resource "aws_iam_role" "lambda_batch_role" {
  name = "lambda_daily_batch_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "lambda_s3_ssm_policy" {
  name = "lambda_s3_ssm_policy"
  role = aws_iam_role.lambda_batch_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Action = ["s3:PutObject", "s3:GetObject"], Effect = "Allow", Resource = "arn:aws:s3:::buyduck-bronze/*" },
      { Action = ["ssm:GetParameter", "ssm:PutParameter"], Effect = "Allow", Resource = "arn:aws:ssm:us-east-1:*:parameter/buyduck/watermark/*" }
    ]
  })
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda_code/lambda_function.py"
  output_path = "${path.module}/lambda_function.zip"
}

resource "aws_lambda_function" "daily_batch" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "buyduck_daily_incremental_batch"
  role             = aws_iam_role.lambda_batch_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 300  
  memory_size      = 256  
  layers           = ["arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python312:18"]
}

resource "aws_cloudwatch_event_rule" "midnight_trigger" {
  name                = "trigger_daily_batch_midnight"
  schedule_expression = "cron(0 0 * * ? *)" 
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.midnight_trigger.name
  target_id = "TriggerLambda"
  arn       = aws_lambda_function.daily_batch.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.daily_batch.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.midnight_trigger.arn
}

# ==========================================
# 5. PHASE 2: REAL-TIME STREAMING (SQS)
# ==========================================
resource "aws_sqs_queue" "realtime_queue" {
  name                      = "buyduck-realtime-queue"
  message_retention_seconds = 86400 
}

resource "aws_iam_role" "ec2_sqs_role" {
  name = "ec2_sqs_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "ec2_sqs_policy" {
  name = "ec2_sqs_policy"
  role = aws_iam_role.ec2_sqs_role.id
  policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = ["sqs:SendMessage", "sqs:GetQueueUrl"], Effect = "Allow", Resource = aws_sqs_queue.realtime_queue.arn }]
  })
}

resource "aws_iam_instance_profile" "ec2_sqs_profile" {
  name = "ec2_sqs_profile"
  role = aws_iam_role.ec2_sqs_role.name
}

resource "aws_iam_role" "streaming_lambda_role" {
  name = "streaming_lambda_worker_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17", Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "streaming_lambda_policy" {
  name = "streaming_lambda_policy"
  role = aws_iam_role.streaming_lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Action = ["s3:PutObject"], Effect = "Allow", Resource = "arn:aws:s3:::buyduck-bronze/realtime-data/*" },
      { Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Effect = "Allow", Resource = aws_sqs_queue.realtime_queue.arn },
      { Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Effect = "Allow", Resource = "arn:aws:logs:*:*:*" }
    ]
  })
}

data "archive_file" "streaming_lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../lambda_streaming/lambda_function.py"
  output_path = "${path.module}/streaming_lambda.zip"
}

resource "aws_lambda_function" "streaming_worker" {
  filename         = data.archive_file.streaming_lambda_zip.output_path
  source_code_hash = data.archive_file.streaming_lambda_zip.output_base64sha256
  function_name    = "buyduck_realtime_sqs_worker"
  role             = aws_iam_role.streaming_lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.12"
  timeout          = 10  
}

resource "aws_lambda_event_source_mapping" "sqs_to_lambda" {
  event_source_arn = aws_sqs_queue.realtime_queue.arn
  function_name    = aws_lambda_function.streaming_worker.arn
  batch_size       = 10 
}