import requests
import geopandas as gpd
from pystac_client import Client as PystacClient
from datetime import datetime
import planetary_computer
import rioxarray as rxr
import xarray as xr
import numpy as np
import stackstac
import tempfile
import os
from .burn_severity import calc_burn_metrics, reclassify
from src.util.sftp import SFTPClient
from src.util.aws_secrets import get_ssh_secret

SENTINEL2_PATH = "https://planetarycomputer.microsoft.com/api/stac/v1"
SFTP_HOSTNAME = "s-90987336df8a4faca.server.transfer.us-east-2.amazonaws.com"
SFTP_USERNAME = "sftp-admin"

class Sentinel2Client:
    def __init__(self, geojson_bounds, barc_classifications = None, buffer = .1, crs = "EPSG:4326", band_nir = "B8A", band_swir = "B12"):
        self.path = SENTINEL2_PATH
        self.pystac_client = PystacClient.open(
            self.path,
            modifier = planetary_computer.sign_inplace
        )

        self.sftp_client = SFTPClient(
            hostname= SFTP_HOSTNAME,
            username = SFTP_USERNAME,
            private_key = get_ssh_secret()
        )

        self.band_nir = band_nir
        self.band_swir = band_swir
        self.crs = crs

        self.buffer = buffer

        geojson_bounds = gpd.GeoDataFrame.from_features(geojson_bounds)
        # TODO: This is hard-coded to assume 4326 - when we draw an AOI, we will change this logic depending on what makes frontend sense
        if not geojson_bounds.crs:
            geojson_bounds = geojson_bounds.set_crs("EPSG:4326")
        self.geojson_bounds = geojson_bounds.to_crs(crs)

        geojson_bbox = geojson_bounds.bounds.to_numpy()[0]
        self.bbox = [
            geojson_bbox[0].round(decimals=2) - buffer,
            geojson_bbox[1].round(decimals=2) - buffer,
            geojson_bbox[2].round(decimals=2) + buffer,
            geojson_bbox[3].round(decimals=2) + buffer
        ]

        if barc_classifications:
            self.barc_classifications = self.ingest_barc_classifications(barc_classifications)

        self.derived_classifications = None
        print(
            "Initialized Sentinel2Client with bounds: {}".format(
                self.bbox
            )
        )

    def get_items(self, date_range, cloud_cover = 100, from_bbox = True, max_items = None):
        
        date_range_fmt = "{}/{}".format(date_range[0], date_range[1])

        # Note - we might want to mess around with cloud cover eventually, but since we are aiming for 
        # expediance in extreme events, we probably will want to make those determinations ourselves - 
        # for now lets' look at everything

        query = {
            "collections": ["sentinel-2-l2a"],
            "datetime": date_range_fmt,
            # "query": {"eo:cloud_cover": {"lt": cloud_cover}}
        }

        if from_bbox:
            query["bbox"] = self.bbox
        else:
            query["intersects"] = self.geojson_bounds

        if max_items:
            query["max_items"] = max_items

        items = self.pystac_client.search(**query).item_collection()

        return items

    def ingest_barc_classifications(self, barc_classifications_xarray):
        barc_classifications = barc_classifications_xarray.rio.reproject(
            dst_crs = self.crs,
            nodata = 0
        )
        barc_classifications = barc_classifications.astype(int)
        barc_classifications = barc_classifications.rio.clip(
            self.geojson_bounds.geometry.values,
            self.geojson_bounds.crs
        )
        # Set everything outside the geojson_bounds to np.nan
        barc_classifications = barc_classifications.where(barc_classifications != 0, np.nan)
        return barc_classifications

    def arrange_stack(self, items, resolution = 20):

        # Get CRS from first item (this isn't inferred by stackstac, for some reason)
        stac_endpoint_crs = items[0].properties["proj:epsg"]

        # Filter to our relevant bands and stack (again forcing the above crs, from the endpoint itself)
        stack = stackstac.stack(
            items,
            epsg=stac_endpoint_crs,
            resolution=resolution,
            assets=[self.band_nir, self.band_swir]
        )
        stack.rio.write_crs(stac_endpoint_crs, inplace=True)

        # Reduce over the time dimension
        stack = self.reduce_time_range(stack)

        # Buffer the bounds to ensure we get all the data we need, plus a
        # little extra for visualization outside burn area
        bounds_stac_crs = self.geojson_bounds\
            .to_crs(stac_endpoint_crs)\
            .geometry\
            .values

        # Clip to our bounds (need to temporarily convert to the endpoint crs, since we can't reproject til we have <= 3 dims) 
        stack = stack.rio.clip(
            bounds_stac_crs,
            bounds_stac_crs.crs
        )

        # Reproject to our desired CRS
        stack = stack.rio.reproject(
            dst_crs = self.crs,
            nodata = np.nan
        )

        return stack

    def reduce_time_range(self, range_stack):

        # This will probably get a bit more sophisticated, but for now, just take the median
        # We will probably run into issues of cloud occlusion, and for really long fire events,
        # we might want to look into time-series effects of greenup, drying, etc, in the adjacent
        # non-burned areas so attempt to isolate fire effects vs exogenous seasonal stuff. Ultimately,
        # we just want a decent reducer to squash the time dim, so median works for now. 

        return range_stack.median(dim = "time")
         
    def query_fire_event(self, prefire_date_range, postfire_date_range, from_bbox = True, max_items = None):

        # Get items for pre and post fire range
        prefire_items = self.get_items(prefire_date_range, from_bbox = from_bbox, max_items = max_items)
        postfire_items = self.get_items(postfire_date_range, from_bbox = from_bbox, max_items = max_items)

        self.prefire_stack = self.arrange_stack(prefire_items)
        self.postfire_stack = self.arrange_stack(postfire_items)

    def calc_burn_metrics(self):
        self.metrics_stack = calc_burn_metrics(
                prefire_nir = self.prefire_stack.sel(band = self.band_nir),
                prefire_swir = self.prefire_stack.sel(band = self.band_swir),
                postfire_nir = self.postfire_stack.sel(band = self.band_nir),
                postfire_swir = self.postfire_stack.sel(band = self.band_swir),
            )

    def classify(self, thresholds, threshold_source, burn_metric = "dnbr"):
        new_classification = reclassify(
            self.metrics_stack.sel(burn_metric = burn_metric),
            thresholds = thresholds
        )
        new_classification = new_classification.expand_dims(
                dim = "classification_source"
            )
        new_classification["classification_source"] = [threshold_source]

        if self.derived_classifications is None:
            self.derived_classifications = new_classification
        elif threshold_source in self.derived_classifications.classification_source.values:
            self.derived_classifications = self.derived_classifications.where(
                self.derived_classifications.classification_source != threshold_source,
                new_classification
            )
        else:
            self.derived_classifications = xr.concat(
                [self.derived_classifications, new_classification],
                dim = "classification_source"
            )

    def upload_cog(self, fire_event_name):

        if not self.sftp_client.connection:
            self.sftp_client.connect()

        # Save our stack to a COG, in a tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            cog_path = os.path.join(tmpdir, "tmp_cog.tif")
            self.metrics_stack.rio.to_raster(cog_path)

            # Upload the metrics to our SFTP server
            self.sftp_client.upload(
                source_local_path = cog_path,
                remote_path = f"{fire_event_name}/metrics.tif".format(fire_event_name)
            )