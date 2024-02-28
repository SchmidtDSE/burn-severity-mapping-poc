output "s3_from_gcp_role_arn" {
  value       = aws_iam_role.aws_s3_from_gcp.arn
  description = "The ARN of the IAM role for S3 Access from GCP"
}

output "s3_bucket_name" {
  value       = aws_s3_bucket.burn-severity-backend.id
  description = "The name of the burn-backend bucket (with dev or prod suffix)"
}