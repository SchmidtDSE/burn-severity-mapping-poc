import smart_open
import time
import os
import json
import datetime
import rasterio
from rasterio.enums import Resampling
import geopandas as gpd
from google.cloud import logging as cloud_logging
import tempfile
import subprocess
import os
import boto3
import google.auth
import requests
from google.auth.transport import requests as gcp_requests
from google.auth import impersonated_credentials, exceptions

class CloudStaticIOClient:
    def __init__(self, bucket_name, provider):

        self.env = os.environ.get("ENV")
        self.role_arn = os.environ.get("S3_FROM_GCP_ARN")
        self.service_account_email = os.environ.get("GCP_SERVICE_ACCOUNT_S3_EMAIL")
        self.role_session_name = "burn-backend-session"

        self.bucket_name = bucket_name

        # Set up logging
        logging_client = cloud_logging.Client(project="dse-nps")
        log_name = "burn-backend"
        self.logger = logging_client.logger(log_name)

        self.sts_client = boto3.client('sts')

        if provider == "s3":
            self.prefix = f"s3://{self.bucket_name}"
        else:
            raise Exception(f"Provider {provider} not supported")

        self.iam_credentials = None
        self.role_assumed_credentials = None
        self.s3_session = None
        self.validate_credentials()

        self.logger.log_text(f"Initialized CloudStaticIOClient for {self.bucket_name} with provider {provider}")

    def impersonate_service_account(self):
        # Load the credentials of the user
        source_credentials, project = google.auth.default()

        # Define the scopes of the impersonated credentials
        target_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

        # Create the IAM credentials client for the impersonated service account
        iam_credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=self.service_account_email,
            target_scopes=target_scopes,
            lifetime=3600
        )

        # Refresh the client
        self.iam_credentials = iam_credentials

    def fetch_id_token(self, audience):
        if not self.iam_credentials.valid:
            # Refresh the credentials
            self.iam_credentials.refresh(Request())

        # Make an authenticated HTTP request to the Google OAuth2 v1/token endpoint
        url = f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{self.service_account_email}:generateIdToken"
        headers = {"Authorization": f"Bearer {self.iam_credentials.token}"}
        body = {"audience": audience, "includeEmail": True}
        response = requests.post(url, headers=headers, json=body)

        # Check the response
        if response.status_code != 200:
            raise exceptions.DefaultCredentialsError(
                "Failed to fetch ID token: " + response.text
            )

        # Return the ID token
        return response.json()["token"]

    def validate_credentials(self):

        if not self.role_assumed_credentials or (self.role_assumed_credentials['Expiration'].timestamp() - time.time() < 300):
            oidc_token = None
            request = gcp_requests.Request()

            if self.env == 'LOCAL':
                if not self.iam_credentials or self.iam_credentials.expired:
                    self.impersonate_service_account()
                self.iam_credentials.refresh(request)

            oidc_token = self.fetch_id_token(audience="sts.amazonaws.com")
            if not oidc_token:
                raise ValueError("Failed to retrieve OIDC token")

            sts_response = self.sts_client.assume_role_with_web_identity(
                RoleArn=self.role_arn,
                RoleSessionName=self.role_session_name,
                WebIdentityToken=oidc_token
            )

            self.role_assumed_credentials = sts_response['Credentials']

            self.boto_session = boto3.Session(
                aws_access_key_id=self.role_assumed_credentials['AccessKeyId'],
                aws_secret_access_key=self.role_assumed_credentials['SecretAccessKey'],
                aws_session_token=self.role_assumed_credentials['SessionToken'],
                region_name='us-east-2'
            )

    def download(self, remote_path, target_local_path):
        """
        Downloads the file from remote s3 server to local.
        Also, by default extracts the file to the specified target_local_path
        """
        self.validate_credentials()
        try:
            # Create the target directory if it does not exist
            path, _ = os.path.split(target_local_path)
            if not os.path.isdir(path):
                try:
                    os.makedirs(path)
                except Exception as err:
                    raise Exception(err)

            # Download from remote s3 server to local
            with smart_open.open(
                f"{self.prefix}/{remote_path}",
                "rb",
                transport_params={"client": self.boto_session.client('s3')},
            ) as remote_file:
                with open(target_local_path, "wb") as local_file:
                    local_file.write(remote_file.read())

        except Exception as err:
            raise Exception(err)

    def upload(self, source_local_path, remote_path):
        """
        Uploads the source files from local to the s3 server.
        """
        self.validate_credentials()
        try:
            print(
                f"uploading to {self.bucket_name} [(remote path: {remote_path});(source local path: {source_local_path})]"
            )

            # Upload file from local to S3
            with open(source_local_path, "rb") as local_file:
                with smart_open.open(
                    f"{self.prefix}/{remote_path}",
                    "wb",
                    transport_params={"client": self.boto_session.client('s3')},
                ) as remote_file:
                    remote_file.write(local_file.read())
            print("upload completed")

        except Exception as err:
            raise Exception(err)

    def upload_cogs(
        self,
        metrics_stack,
        fire_event_name,
        affiliation,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            for band_name in metrics_stack.burn_metric.to_index():
                # Save the band as a local COG
                local_cog_path = os.path.join(tmpdir, f"{band_name}.tif")
                band_cog = metrics_stack.sel(burn_metric=band_name).rio
                band_cog.to_raster(local_cog_path, driver="GTiff")

                # Update the COG with overviews, for faster loading at lower zoom levels
                self.logger.log_text(f"Updating {band_name} with overviews")
                with rasterio.open(local_cog_path, "r+") as ds:
                    ds.build_overviews([2, 4, 8, 16, 32], Resampling.nearest)
                    ds.update_tags(ns="rio_overview", resampling="nearest")

                self.upload(
                    source_local_path=local_cog_path,
                    remote_path=f"public/{affiliation}/{fire_event_name}/{band_name}.tif",
                )

            # Upload the difference between dNBR and RBR
            local_cog_path = os.path.join(tmpdir, f"pct_change_dnbr_rbr.tif")
            pct_change = (
                (
                    metrics_stack.sel(burn_metric="rbr")
                    - metrics_stack.sel(burn_metric="dnbr")
                )
                / metrics_stack.sel(burn_metric="dnbr")
                * 100
            )
            pct_change.rio.to_raster(local_cog_path, driver="GTiff")
            self.upload(
                source_local_path=local_cog_path,
                remote_path=f"public/{affiliation}/{fire_event_name}/pct_change_dnbr_rbr.tif",
            )

    def upload_rap_estimates(
        self,
        rap_estimates,
        fire_event_name,
        affiliation
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_cog_path = os.path.join(tmpdir, f"rap_estimates.tif")
            rap_estimates.rio.to_raster(local_cog_path, driver="GTiff")
            self.upload(
                source_local_path=local_cog_path,
                remote_path=f"public/{affiliation}/{fire_event_name}/rap_estimates.tif",
            )
            # Update the COG with overviews, for faster loading at lower zoom levels
            self.logger.log_text(f"Updating rap_esimates with overviews")
            with rasterio.open(local_cog_path, "r+") as ds:
                ds.build_overviews([2, 4, 8, 16, 32], Resampling.nearest)
                ds.update_tags(ns="rio_overview", resampling="nearest")

    def update_manifest(
        self,
        fire_event_name,
        bounds,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self.get_manifest()

            if fire_event_name in manifest:
                self.logger.log_text(
                    f"Fire event {fire_event_name} already exists in manifest. Overwriting."
                )
                del manifest[fire_event_name]

            manifest[fire_event_name] = {
                "bounds": bounds,
                "prefire_date_range": prefire_date_range,
                "postfire_date_range": postfire_date_range,
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "requester_affiliation": affiliation,
                "derive_boundary": derive_boundary,
            }

            # Upload the manifest to our SFTP server
            tmp_manifest_path = os.path.join(tmpdir, "manifest_updated.json")
            with open(tmp_manifest_path, "w") as f:
                json.dump(manifest, f)
            self.upload(
                source_local_path=tmp_manifest_path, remote_path="manifest.json"
            )
            self.logger.log_text(f"Uploaded/updated manifest.json")

    def upload_fire_event(
        self,
        metrics_stack,
        fire_event_name,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
    ):
        self.logger.log_text(f"Uploading fire event {fire_event_name}")

        self.upload_cogs(
            metrics_stack=metrics_stack,
            fire_event_name=fire_event_name,
            prefire_date_range=prefire_date_range,
            postfire_date_range=postfire_date_range,
            affiliation=affiliation,
        )

        bounds = [round(pos, 4) for pos in metrics_stack.rio.bounds()]

        self.update_manifest(
            fire_event_name=fire_event_name,
            bounds=bounds,
            prefire_date_range=prefire_date_range,
            postfire_date_range=postfire_date_range,
            affiliation=affiliation,
            derive_boundary=derive_boundary,
        )

    def get_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.download("manifest.json", tmpdir + "tmp_manifest.json")
            self.logger.log_text(f"Got manifest.json")
            manifest = json.load(open(tmpdir + "tmp_manifest.json", "r"))
            return manifest
