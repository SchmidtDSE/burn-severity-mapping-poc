import boto3
import json

AWS_PROFILE = "UCB-FederatedAdmins-557418946771"


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


def get_signed_s3_url(s3_file_path, bucket_name):
    session = boto3.session.Session(
        profile_name=AWS_PROFILE,
        region_name="us-east-2",
    )
    s3_client = session.client(
        service_name="s3",
        region_name="us-east-2",
    )
    return s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": s3_file_path},
        ExpiresIn=604800,  # Set the expiration time to 1 week (maximum)
    )


if __name__ == "__main__":
    print(get_ssh_secret())
