from google.cloud import secretmanager


# TODO: Non-reproducible/manual mapbox secret
# Issue URL: https://github.com/SchmidtDSE/burn-severity-mapping-poc/issues/68
# This mapbox API key was initially stored in Google Cloud Secret Manager using the web GUI, as
# opposed to the rest being declared in the terraform configuration. This was originally considered
# pretty temporary, so we will re-evaluate after frontend v1 is in progress.
def get_mapbox_secret():
    """
    Retrieves the Mapbox API key from Google Cloud Secret Manager. This assumes you are
    authenticated locally with `gcloud auth application-default login`.

    Returns:
        str: The Mapbox API key.
    """
    # GCP project and secret details
    project_id = "dse-nps"
    secret_id = "mapbox_api_key"

    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version.
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"

    # Access the secret version.
    response = client.access_secret_version(request={"name": name})

    # Parse the secret value as a string.
    mapbox_api_key = response.payload.data.decode("UTF-8")

    return mapbox_api_key
