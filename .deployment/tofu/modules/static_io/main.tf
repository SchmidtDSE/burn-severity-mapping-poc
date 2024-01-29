### AWS ###

# Then, the s3 bucket for the server
resource "aws_s3_bucket" "burn-severity-backend" {
  bucket = "burn-severity-backend" 
}

resource "aws_s3_bucket_versioning" "burn-severity-backend" {
  bucket = aws_s3_bucket.burn-severity-backend.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_cors_configuration" "burn_severity_backend_cors" {
  bucket = aws_s3_bucket.burn-severity-backend.bucket

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET"]
    allowed_origins = ["*"]
    max_age_seconds = 3000
  }
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

# data "aws_iam_policy_document" "assume_role" {
#   statement {
#     effect = "Allow"

#     principals {
#       type        = "Service"
#       identifiers = ["transfer.amazonaws.com"]
#     }

#     actions = ["sts:AssumeRole"]
#   }
# }

# resource "aws_iam_role" "admin" {
#   name               = "tf-sftp-admin-iam-role"
#   assume_role_policy = data.aws_iam_policy_document.assume_role.json
# }

# data "aws_iam_policy_document" "s3_policy" {
#   statement {
#     sid    = "ReadWriteS3"
#     effect = "Allow"
#     actions = [
#       "s3:ListBucket",
#     ]
#     resources = [
#       "arn:aws:s3:::burn-severity-backend",
#     ]
#   }

#   statement {
#     effect = "Allow"
#     actions = [
#       "s3:PutObject",
#       "s3:GetObject",
#       "s3:GetObjectTagging",
#       "s3:DeleteObject",
#       "s3:DeleteObjectVersion",
#       "s3:GetObjectVersion",
#       "s3:GetObjectVersionTagging",
#       "s3:GetObjectACL",
#       "s3:PutObjectACL",
#     ]
#     resources = [
#       "arn:aws:s3:::burn-severity-backend/*",
#     ]
#   }
# }

# # Create the s3_policy
# resource "aws_iam_policy" "s3_admin_policy" {
#   name        = "s3_admin_policy"
#   description = "S3 policy for admin user"
#   policy      = data.aws_iam_policy_document.s3_policy.json
# }

# # Attach the policy to the role
# resource "aws_iam_role_policy_attachment" "s3_policy_attachment" {
#   role       = aws_iam_role.admin.name
#   policy_arn = aws_iam_policy.s3_admin_policy.arn
# }

# # Add the necessary session policy to the user
# data "aws_iam_policy_document" "session_policy" {
#   statement {
#     sid    = "AllowListingOfUserFolder"
#     effect = "Allow"
#     actions = [
#       "s3:ListBucket",
#     ]
#     resources = [
#       "arn:aws:s3:::burn-severity-backend",
#     ]
#     condition {
#       test     = "StringLike"
#       variable = "s3:prefix"
#       values = [
#         "/public/*",
#         "/public",
#         "/"
#       ]
#     }
#   }

#   statement {
#     sid    = "HomeDirObjectAccess"
#     effect = "Allow"
#     actions = [
#       "s3:PutObject",
#       "s3:GetObject",
#       "s3:DeleteObject",
#       "s3:GetObjectVersion",
#     ]
#     resources = [
#       "arn:aws:s3:::burn-severity-backend/*",
#     ]
#   }
# }

# # Finally, create the user within Transfer Family
# resource "aws_transfer_user" "tf-sftp-burn-severity" {
#   server_id = aws_transfer_server.tf-sftp-burn-severity.id
#   user_name = "admin"
#   role      = aws_iam_role.admin.arn
#   home_directory_mappings {
#     entry = "/"
#     target = "/burn-severity-backend/public"
#   }
#   home_directory_type = "LOGICAL"
#   policy = data.aws_iam_policy_document.session_policy.json
# }

# resource "aws_transfer_ssh_key" "sftp_ssh_key_public" {
#   depends_on = [aws_transfer_user.tf-sftp-burn-severity]
#   server_id = aws_transfer_server.tf-sftp-burn-severity.id
#   user_name = "admin"
#   body      = var.ssh_pairs["SSH_KEY_ADMIN_PUBLIC"]
# }


## TODO [#4]: This is OIDC stuff, which is not yet working
# Set up STS to allow the GCP server to assume a role for AWS secrets

# Defines who can assume the role.
# Confusing string mapping for the OIDC provider URL (https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_iam-condition-keys.html#ck_aud)
# example paylod of our token looks like:/
  # {
  #   "aud": "sts.amazonaws.com",
  #   "azp": "117526146749746854545",
  #   "email": "burn-backend-service@dse-nps.iam.gserviceaccount.com",
  #   "email_verified": true,
  #   "exp": 1706551963,
  #   "iat": 1706548363,
  #   "iss": "https://accounts.google.com",
  #   "sub": "117526146749746854545"
  # }
# AWS says: aud -> azp, oaud -> aud, sub -> sub

data "aws_iam_policy_document" "oidc_assume_role_policy" {
  statement {
    actions = [
      "sts:AssumeRoleWithWebIdentity"
    ]
    effect  = "Allow"

    principals {
      type        = "Federated"
      # identifiers = ["arn:aws:iam::${var.aws_account_id}:oidc-provider/${var.oidc_provider_domain_url}"]
      identifiers = ["accounts.google.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_domain_url}:sub"

      values = [
        "${var.gcp_cloud_run_client_id}"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_domain_url}:aud"

      values = [
        "${var.gcp_cloud_run_client_id}"
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "${var.oidc_provider_domain_url}:oaud"

      values = [
        "sts.amazonaws.com"
      ]
    }
  }
}

# Defines what actions can be done once the role is assumed.
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

# Create the IAM role with both the assume-role and the session policy.
resource "aws_iam_role" "aws_s3_from_gcp" {
  name               = "aws_s3_from_gcp"
  assume_role_policy = data.aws_iam_policy_document.oidc_assume_role_policy.json
  
  # Inline policy for session 
  inline_policy {
      name = "session_policy"
      policy = data.aws_iam_policy_document.session_policy.json
  }

  tags = {
    project = "burn-severity-backend"
  }
}
