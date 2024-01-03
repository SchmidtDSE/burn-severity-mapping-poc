from google.cloud import secretmanager
import json

def get_ssh_secret():
    # GCP project and secret details
    project_id = "dse-nps"
    secret_id = "burn_sftp_ssh_keys"

    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version.
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"

    # Access the secret version.
    response = client.access_secret_version(request={"name": name})

    # Parse the secret value as a string.
    ssh_private_key = json.loads(response.payload.data.decode("UTF-8"))['SSH_KEY_ADMIN_PRIVATE']

    return ssh_private_key.replace("\\n", "\n")