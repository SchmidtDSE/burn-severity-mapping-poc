output "s3_from_gcp_arn" {
  value       = aws_iam_role.aws_s3_from_gcp.arn
  description = "The ARN of the IAM role for S3 Access from GCP"
}
