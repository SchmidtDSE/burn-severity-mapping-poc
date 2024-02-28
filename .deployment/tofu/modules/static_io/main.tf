### AWS ###

# Then, the s3 bucket for the server
resource "aws_s3_bucket" "burn-severity-backend" {
  bucket = "burn-severity-backend-${terraform.workspace}" 
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
    sid    = "HomeDirObjectAccess"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:PutObject",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:GetObjectVersion",
    ]
    resources = [
      "arn:aws:s3:::${aws_s3_bucket.burn-severity-backend.id}/*",
    ]
  }
}

# Create the IAM role with both the assume-role and the session policy.
resource "aws_iam_role" "aws_s3_from_gcp" {
  name               = "aws_s3_from_gcp_${terraform.workspace}"
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
