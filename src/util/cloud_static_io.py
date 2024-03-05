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
from google.oauth2 import id_token
from google.auth import impersonated_credentials, exceptions

BUCKET_HTTPS_PREFIX = "https://{s3_bucket_name}.s3.us-east-2.amazonaws.com"


class CloudStaticIOClient:
    """
    A client class for interacting with cloud storage services like S3, GCS, etc.
    This uses the `smart_open` library to interact with cloud storage services, in a
    relatively provider-agnostic way. It also uses the `boto3` library to interact with
    AWS services, specifically so that we can assume a role in AWS and then use the
    assumed role credentials to interact with S3.

    Args:
        bucket_name (str): The name of the bucket in the cloud storage service.
        provider (str): The provider of the cloud storage service (currently only supports "s3").
        logger (logging.Logger): The logger for logging messages.

    Attributes:
        env (str): The environment variable for the environment (e.g. "LOCAL", "PROD").
        role_arn (str): The role ARN for assuming the role with AWS.
        service_account_email (str): The email address of the service account for GCP,
            authorized to impersonate the role in AWS.
        role_session_name (str): The name of the role session. Arbitrary.
        sts_client (botocore.client.STS): The STS client for assuming the AWS role using GCP credentials.
        prefix (str): The prefix for the bucket URL. We get this from tofu, once the bucket is created.
        iam_credentials (google.auth.impersonated_credentials.Credentials): The impersonated IAM credentials.
        role_assumed_credentials (dict): The assumed role credentials, once we assume the AWS role.
        boto_session (boto3.Session): The Boto3 session, using the assumed role credentials, which
            at long last allows us to interact with S3.

    Raises:
        Exception: If the provider is not supported.

    """

    def __init__(self, s3_bucket_name, provider, logger):

        self.env = os.environ.get("ENV")
        self.role_arn = os.environ.get("S3_FROM_GCP_ROLE_ARN")
        self.service_account_email = os.environ.get("GCP_SERVICE_ACCOUNT_S3_EMAIL")
        self.role_session_name = "burn-backend-session"

        self.s3_bucket_name = s3_bucket_name
        self.https_prefix = BUCKET_HTTPS_PREFIX.format(s3_bucket_name=s3_bucket_name)
        self.logger = logger

        self.sts_client = boto3.client("sts")

        if provider == "s3":
            self.s3_prefix = f"s3://{self.s3_bucket_name}"
        else:
            raise Exception(f"Provider {provider} not supported")

        self.iam_credentials = None
        self.role_assumed_credentials = None
        self.validate_credentials()

        self.logger.info(
            f"Initialized CloudStaticIOClient for {self.s3_bucket_name} with provider {provider}"
        )

    def impersonate_service_account(self):
        """
        Impersonates a service account by creating impersonated credentials, using the
        service account email provided in initialization.

        Returns:
            None
        """
        # Load the credentials of the user
        source_credentials, __project = google.auth.default()

        # Define the scopes of the impersonated credentials
        target_scopes = ["https://www.googleapis.com/auth/cloud-platform"]

        # Create the IAM credentials client for the impersonated service account
        iam_credentials = impersonated_credentials.Credentials(
            source_credentials=source_credentials,
            target_principal=self.service_account_email,
            target_scopes=target_scopes,
            lifetime=3600,
        )

        # Refresh the client
        self.iam_credentials = iam_credentials

    def local_fetch_id_token(self, audience):
        """
        Fetches an ID token from the Google IAM service. This is used to authenticate
        with AWS STS, when we are running in the local environment. On GCP, we use the
        `google.auth` library to fetch the ID token since we are already authenticated
        with the service account we need.

        Args:
            audience (str): The audience for the ID token.

        Returns:
            str: The fetched ID token.

        Raises:
            exceptions.DefaultCredentialsError: If the ID token fetch fails.
        """
        if not self.iam_credentials or not self.iam_credentials.valid:
            # Refresh the credentials
            self.iam_credentials.refresh(gcp_requests.Request())

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
        """
        Validates the credentials by checking if the role assumed credentials are expired or not.
        If expired or not available, it retrieves the OIDC token and assumes the role with web identity.
        Sets the assumed credentials in the boto3 session for further use. If the environment is local,
        it also impersonates the service account to get the credentials, otherwise we assume google.auth
        will handle the credentials for us if we're on GCP.

        Raises:
            ValueError: If failed to retrieve OIDC token.

        Returns:
            None
        """
        if not self.role_assumed_credentials or (
            self.role_assumed_credentials["Expiration"].timestamp() - time.time() < 300
        ):
            oidc_token = None
            request = gcp_requests.Request()

            if self.env == "LOCAL":
                if not self.iam_credentials or self.iam_credentials.expired:
                    self.impersonate_service_account()
                self.iam_credentials.refresh(request)
                oidc_token = self.local_fetch_id_token(audience="sts.amazonaws.com")
            else:
                oidc_token = id_token.fetch_id_token(request, "sts.amazonaws.com")

            if not oidc_token:
                raise ValueError("Failed to retrieve OIDC token")

            sts_response = self.sts_client.assume_role_with_web_identity(
                RoleArn=self.role_arn,
                RoleSessionName=self.role_session_name,
                WebIdentityToken=oidc_token,
            )

            self.role_assumed_credentials = sts_response["Credentials"]

            self.boto_session = boto3.Session(
                aws_access_key_id=self.role_assumed_credentials["AccessKeyId"],
                aws_secret_access_key=self.role_assumed_credentials["SecretAccessKey"],
                aws_session_token=self.role_assumed_credentials["SessionToken"],
                region_name="us-east-2",
            )

    def download(self, remote_path, target_local_path):
        """
        Downloads the file from remote s3 server to local.

        Args:
            remote_path (str): The path of the file on the remote server.
            target_local_path (str): The path where the file will be downloaded to.

        Raises:
            Exception: If there is an error during the download process.

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
                f"{self.s3_prefix}/{remote_path}",
                "rb",
                transport_params={"client": self.boto_session.client("s3")},
            ) as remote_file:
                with open(target_local_path, "wb") as local_file:
                    local_file.write(remote_file.read())

        except Exception as err:
            raise Exception(err)

    def upload(self, source_local_path, remote_path):
        """
        Uploads the source files from local to the s3 server.

        Args:
            source_local_path (str): The local path of the source file to be uploaded.
            remote_path (str): The remote path where the file will be uploaded to.

        Raises:
            Exception: If there is an error during the upload process.
        """
        self.validate_credentials()
        try:
            print(
                f"uploading to {self.s3_bucket_name} [(remote path: {remote_path});(source local path: {source_local_path})]"
            )

            # Upload file from local to S3
            with open(source_local_path, "rb") as local_file:
                with smart_open.open(
                    f"{self.s3_prefix}/{remote_path}",
                    "wb",
                    transport_params={"client": self.boto_session.client("s3")},
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
        """
        Uploads COGs (Cloud-Optimized GeoTIFFs) to a remote location, according to
        `public/{affiliation}/{fire_event_name}/{band_name}.tif`. Also adds
        overviews to the COGs for faster loading at lower zoom levels.

        Args:
            metrics_stack (xarray.DataArray): Stack of metrics data.
            fire_event_name (str): Name of the fire event.
            affiliation (str): Affiliation of the data.

        Returns:
            None
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            for band_name in metrics_stack.burn_metric.to_index():
                # Save the band as a local COG
                local_cog_path = os.path.join(tmpdir, f"{band_name}.tif")
                band_cog = metrics_stack.sel(burn_metric=band_name).rio
                band_cog.to_raster(local_cog_path, driver="GTiff")

                # Update the COG with overviews, for faster loading at lower zoom levels
                self.logger.info(f"Updating {band_name} with overviews")
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

    def upload_rap_estimates(self, rap_estimates, fire_event_name, affiliation):
        """
        Uploads RAP estimates to a remote location, according to
        f"public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_{band_name}.tif".
        Also adds overviews to the COGs for faster loading at lower zoom levels.

        Args:
            rap_estimates (xarray.DataArray): RAP estimates data.
            fire_event_name (str): Name of the fire event.
            affiliation (str): Affiliation of the data.

        Returns:
            None
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            for band_name in rap_estimates.band.to_index():
                # TODO [#23]: This is the same logic as in upload_cogs. Refactor to avoid duplication
                # Save the band as a local COG
                local_cog_path = os.path.join(tmpdir, f"{band_name}.tif")
                band_cog = rap_estimates.sel(band=band_name).rio
                band_cog.to_raster(local_cog_path, driver="GTiff")

                # Update the COG with overviews, for faster loading at lower zoom levels
                self.logger.info(f"Updating {band_name} with overviews")
                with rasterio.open(local_cog_path, "r+") as ds:
                    ds.build_overviews([2, 4, 8, 16, 32], Resampling.nearest)
                    ds.update_tags(ns="rio_overview", resampling="nearest")

                self.upload(
                    source_local_path=local_cog_path,
                    remote_path=f"public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_{band_name}.tif",
                )

    def update_manifest(
        self,
        fire_event_name,
        bounds,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
    ):
        """
        Updates the manifest with the given fire event information for the specified affiliation. If the fire event
        already exists in the manifest, it will be overwritten.

        Args:
            fire_event_name (str): The name of the fire event.
            bounds (tuple): The bounds of the fire event.
            prefire_date_range (tuple): The prefire date range of the fire event.
            postfire_date_range (tuple): The postfire date range of the fire event.
            affiliation (str): The affiliation for which the manifest is being updated.
            derive_boundary (bool): Flag indicating whether to derive the boundary.

        Returns:
            None
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self.get_manifest()

            if affiliation in manifest and fire_event_name in manifest[affiliation]:
                self.logger.info(
                    f"Fire event {fire_event_name} already exists in manifest for affiliation {affiliation}. Overwriting."
                )
                del manifest[affiliation][fire_event_name]

            if affiliation not in manifest:
                manifest[affiliation] = {}

            manifest[affiliation][fire_event_name] = {
                "bounds": bounds,
                "prefire_date_range": prefire_date_range,
                "postfire_date_range": postfire_date_range,
                "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "derive_boundary": derive_boundary,
            }

            # Upload the manifest to our SFTP server
            tmp_manifest_path = os.path.join(tmpdir, "manifest_updated.json")
            with open(tmp_manifest_path, "w") as f:
                json.dump(manifest, f)
            self.upload(
                source_local_path=tmp_manifest_path, remote_path="manifest.json"
            )
            self.logger.info(f"Uploaded/updated manifest.json")

    def upload_fire_event(
        self,
        metrics_stack,
        fire_event_name,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
    ):
        """
        Uploads a fire event to the cloud storage location (uploads COGs and updates the manifest.json file).

        Args:
            metrics_stack (xr.DataArray): The metrics stack containing the fire event data.
            fire_event_name (str): The name of the fire event.
            prefire_date_range (tuple): The date range before the fire event.
            postfire_date_range (tuple): The date range after the fire event.
            affiliation (str): The affiliation of the fire event.
            derive_boundary (bool): Whether to derive the boundary of the fire event.

        Returns:
            None
        """
        self.logger.info(f"Uploading fire event {fire_event_name}")

        self.upload_cogs(
            metrics_stack=metrics_stack,
            fire_event_name=fire_event_name,
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
        """
        Retrieves the manifest file from the cloud storage.

        Returns:
            dict: The contents of the manifest file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            self.download("manifest.json", tmpdir + "tmp_manifest.json")
            self.logger.info(f"Got manifest.json")
            manifest = json.load(open(tmpdir + "tmp_manifest.json", "r"))
            return manifest

    def get_derived_products(self, affiliation, fire_event_name):
        """
        Retrieves the derived products associated with a specific affiliation and fire event. We basically
        assume anything within the folder for a given affiliation and fire event is a derived product. Valyes
        returned are public HTTPS URLs.

        Args:
            affiliation (str): The affiliation of the derived products.
            fire_event_name (str): The name of the fire event.

        Returns:
            dict: A dictionary containing the filenames as keys and the corresponding full HTTPS URLs as values.
        """
        s3_client = self.boto_session.client("s3")
        paginator = s3_client.get_paginator("list_objects_v2")
        derived_products = {}
        intra_bucket_prefix = f"public/{affiliation}/{fire_event_name}/"
        for page in paginator.paginate(
            Bucket=self.s3_bucket_name, Prefix=intra_bucket_prefix
        ):
            for obj in page["Contents"]:
                full_https_url = self.https_prefix + "/" + obj["Key"]
                filename = os.path.basename(obj["Key"])
                derived_products[filename] = full_https_url
        return derived_products
