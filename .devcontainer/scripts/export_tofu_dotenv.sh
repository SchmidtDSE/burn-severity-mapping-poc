cd /workspace/.deployment/tofu
tofu workspace select dev
tofu init
tofu refresh


# .env will always be LOCAL which uses localhost and various non-cloud infrastructure for development
echo "# TOFU ENV VARS" >> /workspace/.devcontainer/.env
echo "ENV=LOCAL" >> /workspace/.devcontainer/.env
echo "DEPLOYMENT=DEV" >> /workspace/.devcontainer/.env

# Change this to 'titiler' to attach to the titiler backend
echo "DEBUG_SERVICE=BURN_BACKEND" >> /workspace/.devcontainer/.env

# ARN to allow GCP to read from S3
export s3_from_gcp_role_arn="$(tofu output s3_from_gcp_role_arn)"
echo "S3_FROM_GCP_ROLE_ARN=$s3_from_gcp_role_arn" >> /workspace/.devcontainer/.env

# S3 bucket name for burn analysis outputs
export s3_bucket_name=$(tofu output s3_bucket_name)
echo "S3_BUCKET_NAME=$s3_bucket_name" >> /workspace/.devcontainer/.env

# SA for GCP to read from S3 (Remove quotes from the email to avoid issue with the impersonation below)
export gcp_service_account_s3_email=$(tofu output gcp_service_account_s3_email | tr -d '"')
echo "GCP_SERVICE_ACCOUNT_S3_EMAIL=$gcp_service_account_s3_email" >> /workspace/.devcontainer/.env

# Burn backend endpoint
export gcp_cloud_run_endpoint_burn_backend="$(tofu output gcp_cloud_run_endpoint_burn_backend)"
echo "GCP_CLOUD_RUN_ENDPOINT_BURN_BACKEND=$gcp_cloud_run_endpoint_burn_backend" >> /workspace/.devcontainer/.env

# Titiler endpoint
export gcp_cloud_run_endpoint_titiler="$(tofu output gcp_cloud_run_endpoint_titiler)"
echo "GCP_CLOUD_RUN_ENDPOINT_TITILER=$gcp_cloud_run_endpoint_titiler" >> /workspace/.devcontainer/.env

# Titiler possible origins
export gcp_cloud_run_endpoint_titiler_possible_origins="$(tofu output gcp_cloud_run_endpoint_titiler_possible_origins)"
echo "GCP_CLOUD_RUN_ENDPOINT_TITILER_POSSIBLE_ORIGINS=$gcp_cloud_run_endpoint_titiler_possible_origins" >> /workspace/.devcontainer/.env
