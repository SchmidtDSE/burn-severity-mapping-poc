import paramiko
from urllib.parse import urlparse
import io
import os

class SFTPClient:
    def __init__(self, hostname, username, private_key, port=22):
        """Constructor Method"""
        self.connection = None
        self.hostname = hostname
        self.username = username
        self.port = port

        private_key_file = io.StringIO(private_key.replace("\\n", "\n"))
        self.private_key = paramiko.RSAKey.from_private_key(private_key_file)

        print(f"Initialized SFTPClient for {self.hostname} as {self.username}")

    def connect(self):
        """Connects to the sftp server and returns the sftp connection object"""
        try:
            # Create SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Connect to the server
            ssh_client.connect(
                self.hostname,
                port=self.port,
                username=self.username,
                pkey=self.private_key
            )

            # Create SFTP client from SSH client
            self.connection = ssh_client.open_sftp()

        except Exception as err:
            raise Exception(err)
        finally:
            print(f"Connected to {self.hostname} as {self.username}.")

    def disconnect(self):
        """Closes the sftp connection"""
        self.connection.close()
        print(f"Disconnected from host {self.hostname}")

    def listdir(self, remote_path):
        """lists all the files and directories in the specified path and returns them"""
        for obj in self.connection.listdir(remote_path):
            yield obj

    def listdir_attr(self, remote_path):
        """lists all the files and directories (with their attributes) in the specified path and returns them"""
        for attr in self.connection.listdir_attr(remote_path):
            yield attr

    def download(self, remote_path, target_local_path):
        """
        Downloads the file from remote sftp server to local.
        Also, by default extracts the file to the specified target_local_path
        """

        try:
            print(
                f"downloading from {self.hostname} as {self.username} [(remote path : {remote_path});(local path: {target_local_path})]"
            )

            # Create the target directory if it does not exist
            path, _ = os.path.split(target_local_path)
            if not os.path.isdir(path):
                try:
                    os.makedirs(path)
                except Exception as err:
                    raise Exception(err)

            # Download from remote sftp server to local
            self.connection.get(remote_path, target_local_path)
            print("download completed")

        except Exception as err:
            raise Exception(err)

    def upload(self, source_local_path, remote_path):
        """
        Uploads the source files from local to the sftp server.
        """

        try:
            print(
                f"uploading to {self.hostname} as {self.username} [(remote path: {remote_path});(source local path: {source_local_path})]"
            )

            # Upload file from local to SFTP
            self.connection.put(source_local_path, remote_path)
            print("upload completed")

        except Exception as err:
            raise Exception(err)
