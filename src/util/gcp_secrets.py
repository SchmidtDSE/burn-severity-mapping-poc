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