import boto3
import json

def get_ssh_secret():

    secret_name = "sftp-admin-private-key"
    region_name = "us-east-2"

    # Create a Secrets Manager client
    session = boto3.session.Session(
        profile_name='UCB-FederatedAdmins-557418946771',
        region_name=region_name,
    )
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name,
    )

    # Use the client to retrieve the secret
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    
    # The secret value is a JSON string
    ssh_private_key = json.loads(get_secret_value_response['SecretString'])['SFTP_ADMIN_PRIVATE_KEY']

    return ssh_private_key

if __name__ == "__main__":
    print(get_ssh_secret())