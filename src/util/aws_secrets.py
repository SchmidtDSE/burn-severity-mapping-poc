import boto3
import json

def get_ssh_secret():

    secret_name = "sftp-admin-private-key"
    region_name = "us-east-2"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    # Use the client to retrieve the secret
    get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    
    # The secret value is a JSON string
    secret_value = json.loads(get_secret_value_response['SecretString'])

    return secret_value

if __name__ == "__main__":
    print(get_ssh_secret())