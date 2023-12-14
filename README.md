### Deploying to Cloud 

If you want to deploy to the cloud, you can use OpenTofu to do so - but you need to auth with both `AWS` and `GCP` to do so. 
```
aws configure sso
gcloud auth application-default login

```

Both will provide you a URL to login via SSO. Once this is done, run:

```
tofu init
tofu plan -out .terraform/tfplan
tofu apply ".terraform/tfplan"
```