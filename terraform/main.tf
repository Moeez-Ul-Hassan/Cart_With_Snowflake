provider "aws" { 
  region = "us-east-1" 
} 

# 1. The Firewall (Security Group) 
resource "aws_security_group" "enterprise_cart_sg" { 
  name        = "enterprise-cart-security-group" 
  
  # CRITICAL: This exact text prevents AWS from destroying your live firewall
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
    description = "PostgreSQL Database (For Snowflake Bronze Layer Extraction)" 
    from_port   = 5432 
    to_port     = 5432 
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

# 2. The EC2 Server & Automation Script 
resource "aws_instance" "cart_server" { 
  ami           = "ami-04b70fa74e45c3917" # Ubuntu 24.04 LTS for us-east-1 
  instance_type = "t3.micro"              # Optimized for strict AWS Free Tier accounts 
  key_name      = "cart-key"              # Ensure this matches your downloaded .pem key name exactly 
  
  vpc_security_group_ids = [aws_security_group.enterprise_cart_sg.id] 
  
  root_block_device { 
    volume_size = 30 
    volume_type = "gp2"                   # Downgraded from gp3 to satisfy strict Free Tier limits 
  } 

  # The Bash Script executed instantly upon server creation 
  user_data = <<-EOF
              #!/bin/bash 
              # Update OS and Install Dependencies 
              apt-get update -y 
              apt-get install -y docker.io docker-compose git python3-pip python3-venv 
              
              # Start and Enable Docker 
              systemctl start docker 
              systemctl enable docker 
              
              # Create the dedicated user 'cartadmin' 
              NEW_USER="cartadmin" 
              useradd -m -s /bin/bash $NEW_USER 
              usermod -aG sudo $NEW_USER 
              usermod -aG docker $NEW_USER 
              
              # Allow passwordless sudo for smooth CI/CD deployments later 
              echo "$NEW_USER ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/$NEW_USER 
              
              # Securely copy SSH keys to the new user so you can log in 
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

# 3. The Output 
output "server_public_ip" { 
  description = "The public IP address of your new API server" 
  value       = aws_instance.cart_server.public_ip 
}