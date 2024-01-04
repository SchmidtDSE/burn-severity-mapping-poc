# Upload seed files to S3
aws s3 cp /workspace/.deployment/tofu/assets/index.html s3://burn-severity-backend/index.html --profile UCB-FederatedAdmins-557418946771
aws s3 cp /workspace/.deployment/tofu/assets/error.html s3://burn-severity-backend/error.html --profile UCB-FederatedAdmins-557418946771

# create the /public folder on S3 bucket implicitly with manifest.json
aws s3 cp /workspace/.deployment/tofu/assets/manifest.json s3://burn-severity-backend/public/manifest.json --profile UCB-FederatedAdmins-557418946771
