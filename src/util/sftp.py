import smart_open
import os
import json
import datetime
import rasterio
from rasterio.enums import Resampling
import geopandas as gpd
from google.cloud import logging as cloud_logging


# TODO [#9]: Convert to agnostic Boto client
# Use the slick smart-open library to handle S3 connections. This maintains the agnostic nature
# of sftp, not tied to any specific cloud provider, but is way more efficient than paramiko/sftp in terms of $$


class S3Client:
    def __init__(self, bucket_name):
        """Constructor Method"""
        self.bucket_name = bucket_name

        # Set up logging
        logging_client = cloud_logging.Client(project="dse-nps")
        log_name = "burn-backend"
        self.logger = logging_client.logger(log_name)

        self.logger.log_text(f"Initialized S3Client for {self.bucket_name}")

    def download(self, remote_path, target_local_path):
        """
        Downloads the file from remote s3 server to local.
        Also, by default extracts the file to the specified target_local_path
        """
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
                f"s3://{self.bucket_name}/{remote_path}"
            ) as remote_file:
                with open(target_local_path, "wb") as local_file:
                    local_file.write(remote_file.read())

        except Exception as err:
            raise Exception(err)

    def upload(self, source_local_path, remote_path):
        """
        Uploads the source files from local to the s3 server.
        """
        try:
            print(
                f"uploading to {self.bucket_name} [(remote path: {remote_path});(source local path: {source_local_path})]"
            )

            # Upload file from local to S3
            with open(source_local_path, "rb") as local_file:
                with smart_open.open(
                    f"s3://{self.bucket_name}/{remote_path}", "wb"
                ) as remote_file:
                    remote_file.write(local_file.read())
            print("upload completed")

        except Exception as err:
            raise Exception(err)

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
            # Create the target directory if it does not exist
            path, _ = os.path.split(target_local_path)
            if not os.path.isdir(path):
                try:
                    os.makedirs(path)
                except Exception as err:
                    raise Exception(err)

            # Download from remote sftp server to local
            self.connection.get(remote_path, target_local_path)

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

    def upload_cogs(
        self,
        metrics_stack,
        fire_event_name,
        prefire_date_range,
        postfire_date_range,
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
                    remote_path=f"{affiliation}/{fire_event_name}/{band_name}.tif",
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
                remote_path=f"{affiliation}/{fire_event_name}/pct_change_dnbr_rbr.tif",
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
