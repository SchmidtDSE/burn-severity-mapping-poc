### AWS ###

# Get the AWS region for the current workspace
data "aws_region" "current" {}

# Create the CloudWatch logs policy
data "aws_iam_policy_document" "cloudwatch_logs_policy" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]

    resources = ["arn:aws:logs:*:*:*"]
  }
}

data "aws_iam_policy_document" "cloudwatch_logs_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["transfer.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "cloudwatch_logs_policy" {
  name        = "cloudwatch_logs_policy"
  description = "CloudWatch Logs policy for AWS Transfer logging"
  policy      = data.aws_iam_policy_document.cloudwatch_logs_policy.json
}

# Create the IAM role for CloudWatch logging
resource "aws_iam_role" "cloudwatch_logs_role" {
  name = "cloudwatch_logs_role"
  assume_role_policy = data.aws_iam_policy_document.cloudwatch_logs_role.json
}

# Attach the CloudWatch logs policy to the new role
resource "aws_iam_role_policy_attachment" "cloudwatch_logs_policy_attachment" {
  role       = aws_iam_role.cloudwatch_logs_role.name
  policy_arn = aws_iam_policy.cloudwatch_logs_policy.arn
}

resource "aws_cloudwatch_log_group" "transfer_log_group" {
  name = "/aws/transfer/${aws_transfer_server.tf-sftp-burn-severity.id}"
  retention_in_days = 14
}

# # Create a security group for the Transfer Family server, to allow inbound traffic from GCP
# resource "aws_security_group" "sftp_sg" {
#   name        = "sftp_sg"
#   description = "Allow inbound traffic from GCP Cloud Run service"
#   vpc_id      = aws_vpc.sftp_vpc.id

#   ingress {
#     from_port   = 22 # SFTP uses port 22
#     to_port     = 22
#     protocol    = "tcp"
#     cidr_blocks = ["10.3.0.0/28"] # CIDR range of the GCP Cloud Run instance
#   }

#   egress {
#     from_port   = 0
#     to_port     = 0
#     protocol    = "-1"
#     cidr_blocks = ["0.0.0.0/0"]
#   }
# }

# Create a VPC endpoint for the Transfer Family server

# resource "aws_vpc" "sftp_vpc" {
#   cidr_block = "10.0.0.0/16"
# }

# resource "aws_subnet" "sftp_subnet" {
#   vpc_id     = aws_vpc.sftp_vpc.id
#   cidr_block = "10.0.1.0/24"
# }

# resource "aws_vpc_endpoint" "sftp_endpoint" {
#   vpc_id            = aws_vpc.sftp_vpc.id 
#   service_name      = "com.amazonaws.${data.aws_region.current.name}.transfer.server"
#   vpc_endpoint_type = "Interface"
#   subnet_ids        = [aws_subnet.sftp_subnet.id]
#   security_group_ids = [aws_security_group.sftp_sg.id]
# }


# First the server itself
resource "aws_transfer_server" "tf-sftp-burn-severity" {
  identity_provider_type = "SERVICE_MANAGED"
  protocols = ["SFTP"]
  domain = "S3"
  endpoint_type = "PUBLIC"
  logging_role = aws_iam_role.cloudwatch_logs_role.arn
}

# Then, the s3 bucket for the server
resource "aws_s3_bucket" "burn-severity-backend" {
  bucket = "burn-severity-backend" # replace with your bucket name
}

data "aws_iam_policy_document" "burn-severity-backend-policy" {
  statement {
    sid       = "PublicReadGetObject"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.burn-severity-backend.arn}/*"]

    principals {
      type        = "*"
      identifiers = ["*"]
    }
  }
}

resource "aws_s3_bucket_policy" "burn-severity-backend-policy" {
  bucket = aws_s3_bucket.burn-severity-backend.id
  policy = data.aws_iam_policy_document.burn-severity-backend-policy.json
}

resource "aws_s3_bucket_ownership_controls" "burn-severity-backend" {
  bucket = aws_s3_bucket.burn-severity-backend.id
  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_public_access_block" "burn-severity-backend" {
  bucket = aws_s3_bucket.burn-severity-backend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_acl" "burn-severity-backend" {
  depends_on = [
    aws_s3_bucket_ownership_controls.burn-severity-backend,
    aws_s3_bucket_public_access_block.burn-severity-backend,
  ]

  bucket = aws_s3_bucket.burn-severity-backend.id
  acl    = "public-read"
}

resource "aws_s3_bucket_website_configuration" "burn-severity-backend" {
  bucket = aws_s3_bucket.burn-severity-backend.id
  index_document {
    suffix = "index.html"
  }
  error_document {
    key = "error.html"
  }
}

// Add the contents of ../assets to the bucket
resource "aws_s3_bucket_object" "assets" {
  for_each = fileset("../assets", "**/*")

  bucket = aws_s3_bucket.burn-severity-backend.id
  key    = each.value
  source = "../assets/${each.value}"
}

# Then, the user for the server, allowing it access to Transfer Family

data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["transfer.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "admin" {
  name               = "tf-sftp-admin-iam-role"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
}

# Then, allow it to actually access the S3 assets themselves
# Define the policy

data "aws_iam_policy_document" "s3_policy" {
  statement {
    sid    = "ReadWriteS3"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::burn-severity-backend",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:GetObjectTagging",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
      "s3:GetObjectVersion",
      "s3:GetObjectVersionTagging",
      "s3:GetObjectACL",
      "s3:PutObjectACL",
    ]
    resources = [
      "arn:aws:s3:::burn-severity-backend/*",
    ]
  }
}

# Create the s3_policy
resource "aws_iam_policy" "s3_admin_policy" {
  name        = "s3_admin_policy"
  description = "S3 policy for admin user"
  policy      = data.aws_iam_policy_document.s3_policy.json
}

# Attach the policy to the role
resource "aws_iam_role_policy_attachment" "s3_policy_attachment" {
  role       = aws_iam_role.admin.name
  policy_arn = aws_iam_policy.s3_admin_policy.arn
}

# Add the necessary session policy to the user
data "aws_iam_policy_document" "session_policy" {
  statement {
    sid    = "AllowListingOfUserFolder"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
    ]
    resources = [
      "arn:aws:s3:::burn-severity-backend",
    ]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values = [
        "/public/*",
        "/public",
        "/"
      ]
    }
  }

  statement {
    sid    = "HomeDirObjectAccess"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:GetObjectVersion",
    ]
    resources = [
      "arn:aws:s3:::burn-severity-backend/*",
    ]
  }
}

# Finally, create the user within Transfer Family
resource "aws_transfer_user" "tf-sftp-burn-severity" {
  server_id = aws_transfer_server.tf-sftp-burn-severity.id
  user_name = "admin"
  role      = aws_iam_role.admin.arn
  home_directory_mappings {
    entry = "/"
    target = "/burn-severity-backend/public"
  }
  home_directory_type = "LOGICAL"
  policy = data.aws_iam_policy_document.session_policy.json
}

resource "aws_transfer_ssh_key" "sftp_ssh_key_public" {
  depends_on = [aws_transfer_user.tf-sftp-burn-severity]
  server_id = aws_transfer_server.tf-sftp-burn-severity.id
  user_name = "admin"
  body      = var.ssh_pairs["SSH_KEY_ADMIN_PUBLIC"]
}


## TODO: This is OIDC stuff, which is not yet working
# Set up STS to allow the GCP server to assume a role for AWS secrets

# data "aws_iam_policy_document" "assume_role_policy" {
#   statement {
#     actions = ["sts:AssumeRoleWithWebIdentity"]
#     effect  = "Allow"

#     principals {
#       type        = "Federated"
#       identifiers = ["arn:aws:iam::557418946771:oidc-provider/https://${var.google_project_number}"]
#     }

#     condition {
#       test     = "StringEquals"
#       variable = "https://${var.google_project_number}.svc.id.goog:sub"

#       values = [
#         "system:serviceaccount:${var.google_project_number}.svc.id.goog[default/${google_service_account.burn-backend-service.account_id}]"
#       ]
#     }
#   }
# }

# resource "aws_iam_role" "role" {
#   name               = "aws_secrets_access_role"
#   assume_role_policy = data.aws_iam_policy_document.assume_role_policy.json
# }

