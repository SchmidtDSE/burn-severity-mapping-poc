
cd /workspace/.deployment/tofu
tofu init
tofu refresh
export gcp_cloud_run_endpoint="$(tofu output gcp_cloud_run_endpoint)"
export s3_from_gcp_arn="$(tofu output s3_from_gcp_arn)"

echo "# TOFU ENV VARS" >> /workspace/.devcontainer/.env
echo "ENV=LOCAL" >> /workspace/.devcontainer/.env
echo "S3_FROM_GCP_ARN=$s3_from_gcp_arn" >> /workspace/.devcontainer/.env
echo "GCP_CLOUD_RUN_ENDPOINT=$gcp_cloud_run_endpoint" >> /workspace/.devcontainer/.env