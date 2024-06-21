cd /workspace/.deployment/tofu
tofu init
tofu refresh

export s3_from_gcp_role_arn="$(tofu output s3_from_gcp_role_arn)"

# Remove quotes from the email to avoid issue with the impersonation below
export gcp_service_account_s3_email=$(tofu output gcp_service_account_s3_email | tr -d '"')
export s3_bucket_name=$(tofu output s3_bucket_name)

echo "# TOFU ENV VARS" >> /workspace/.devcontainer/.env
echo "ENV=LOCAL" >> /workspace/.devcontainer/.env
echo "DEPLOYMENT=DEV" >> /workspace/.devcontainer/.env
echo "S3_FROM_GCP_ROLE_ARN=$s3_from_gcp_role_arn" >> /workspace/.devcontainer/.env
echo "S3_BUCKET_NAME=$s3_bucket_name" >> /workspace/.devcontainer/.env
echo "GCP_SERVICE_ACCOUNT_S3_EMAIL=$gcp_service_account_s3_email" >> /workspace/.devcontainer/.env

# Backend
export gcp_cloud_run_endpoint_burn_backend="$(tofu output gcp_cloud_run_endpoint_burn_backend)"
echo "GCP_CLOUD_RUN_ENDPOINT_BURN_BACKEND=$gcp_cloud_run_endpoint_burn_backend" >> /workspace/.devcontainer/.env

# Titiler
export gcp_cloud_run_endpoint_titiler="$(tofu output gcp_cloud_run_endpoint_titiler)"
echo "GCP_CLOUD_RUN_ENDPOINT_TITILER=$gcp_cloud_run_endpoint_titiler" >> /workspace/.devcontainer/.env

