
cd /workspace/.deployment/tofu
tofu init
tofu refresh

export gcp_cloud_run_endpoint="$(tofu output gcp_cloud_run_endpoint)"
export s3_from_gcp_arn="$(tofu output s3_from_gcp_arn)"
export gcp_service_account_s3_email=$(tofu output gcp_service_account_s3_email)

echo "# TOFU ENV VARS" >> /workspace/.devcontainer/.env
echo "ENV=LOCAL" >> /workspace/.devcontainer/.env
echo "S3_FROM_GCP_ARN=$s3_from_gcp_arn" >> /workspace/.devcontainer/.env
echo "GCP_CLOUD_RUN_ENDPOINT=$gcp_cloud_run_endpoint" >> /workspace/.devcontainer/.env
echo "GCP_SERVICE_ACCOUNT_S3_EMAIL=$gcp_service_account_s3_email" >> /workspace/.devcontainer/.env

# Set gcloud config to allow local development to behave as if it were running in the cloud
gcloud auth application-default login --impersonate-service-account $gcp_service_account_s3_email
echo "GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json" >> /workspace/.devcontainer/.env