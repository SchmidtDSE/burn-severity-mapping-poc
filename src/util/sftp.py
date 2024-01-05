import paramiko
from urllib.parse import urlparse
import io
import os
import tempfile
import logging
from google.cloud import logging as cloud_logging

class SFTPClient:
    def __init__(self, hostname, username, private_key, port=22):
        """Constructor Method"""
        self.connection = None
        self.hostname = hostname
        self.username = username
        self.port = port

        private_key_file = io.StringIO(private_key)
        self.private_key = paramiko.RSAKey.from_private_key(private_key_file)

        self.available_cogs = None

        # Set up logging
        logging_client = cloud_logging.Client()
        log_name = "burn-backend"
        self.logger = logging_client.logger(log_name)

        # Route Paramiko logs to Google Cloud Logging
        paramiko_logger = logging.getLogger("paramiko")
        paramiko_logger.setLevel(logging.DEBUG)
        paramiko_logger.addHandler(cloud_logging.handlers.CloudLoggingHandler(logging_client, name=log_name))

        self.logger.log_text(f"Initialized SFTPClient for {self.hostname} as {self.username}")

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
                pkey=self.private_key,
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

    def upload_cogs(self, metrics_stack, fire_event_name):
        # Save our stack to a COG, in a tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            for band_name in metrics_stack.burn_metric.to_index():
                local_cog_path = os.path.join(tmpdir, f"{band_name}.tif")
                band_cog = metrics_stack.sel(burn_metric = band_name).rio
                band_cog.to_raster(local_cog_path)
                # Upload the metrics to our SFTP server
                self.upload(
                    source_local_path=local_cog_path,
                    remote_path=f"{fire_event_name}/{band_name}.tif",
                )

    def get_available_cogs(self):
        """Lists all available COGs on the SFTP server"""
        available_cogs = {}
        for top_level_folder in self.connection.listdir():
            if not top_level_folder.endswith(".json"):
                s3_file_path = f"{top_level_folder}/metrics.tif"
                available_cogs[top_level_folder] = s3_file_path

        return available_cogs

    def update_available_cogs(self):
        self.connect()
        self.available_cogs = self.get_available_cogs()
        self.disconnect()
