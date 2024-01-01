import os
import boto3
import json
import google.auth
import google.auth.transport.requests

AWS_PROFILE = "UCB-FederatedAdmins-557418946771"
IAM_ROLE_ARN = "arn:aws:iam::557418946771:role/aws_secrets_access_role"
ROLE_SESSION_NAME = "burn"

def get_ssh_secret():
    secret_name = "sftp-admin-private-key-pem"
    region_name = "us-east-2"

    if os.getenv('ENV') == 'CLOUD':
        # Obtain an OIDC token for the GCP service account
        creds, _ = google.auth.default()
        auth_request = google.auth.transport.requests.Request()
        oidc_token = creds.fetch_id_token(auth_request)

        # Assume the IAM role using the OIDC token
        sts_client = boto3.client('sts')
        response = sts_client.assume_role_with_web_identity(
            RoleArn=IAM_ROLE_ARN,
            RoleSessionName=ROLE_SESSION_NAME,
            WebIdentityToken=oidc_token
        )

        # Use the temporary security credentials to access the SSH private key
        aws_access_key_id = response['Credentials']['AccessKeyId']
        aws_secret_access_key = response['Credentials']['SecretAccessKey']
        aws_session_token = response['Credentials']['SessionToken']

        # Create a Secrets Manager client
        session = boto3.session.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=region_name,
        )
    else:  # ENV=LOCAL
        # Create a Secrets Manager client
        session = boto3.session.Session(
            profile_name=AWS_PROFILE,
            region_name=region_name,
        )

    client = session.client(
        service_name="secretsmanager",
        region_name=region_name,
    )

    # Use the client to retrieve the secret
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)

    # The secret value is a JSON string
    ssh_private_key = json.loads(get_secret_value_response["SecretString"])[
        "SFTP_ADMIN_PRIVATE_KEY_PEM"
    ]

    return ssh_private_key