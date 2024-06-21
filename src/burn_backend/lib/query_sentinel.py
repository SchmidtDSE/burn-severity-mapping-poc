import requests
import geopandas as gpd
import rasterio.features
from shapely.geometry import shape, MultiPolygon, Point
from shapely.ops import unary_union
from pystac_client import Client as PystacClient
from datetime import datetime
import planetary_computer
import rioxarray as rxr
import xarray as xr
import numpy as np
import stackstac
import tempfile
from scipy.ndimage import gaussian_filter, binary_fill_holes, binary_dilation
import os
from .burn_severity import calc_burn_metrics, classify_burn
from ..util.raster_to_poly import raster_mask_to_geojson
from src.util.cloud_static_io import CloudStaticIOClient
from src.lib.derive_boundary import (
    derive_boundary,
    OtsuThreshold,
    SimpleThreshold,
    FloodFillSegmentation,
)
from pyproj import CRS
import dask

dask.config.set(  ## Make super conservative memory settings to see if we can do huge areas serially, essentially
    {
        "distributed.worker.memory.target": 0.3,  # target fraction to stay below
        "distributed.worker.memory.spill": 0.5,  # fraction at which we spill to disk
        "distributed.worker.memory.pause": 0.6,  # fraction at which we pause worker threads
        "distributed.worker.memory.terminate": 0.7,  # fraction at which we terminate the worker
    }
)

SENTINEL2_PATH = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEBUG = True

if DEBUG:
    from dask.distributed import Client  ## This wont exist on prod instance

    dask_client = Client()
    print(f"Dask client started at {dask_client.dashboard_link}")


class NoFireBoundaryDetectedError(BaseException):
    pass


class Sentinel2Client:
    def __init__(
        self,
        geojson_boundary=None,
        barc_classifications=None,
        buffer=0.1,
        crs="EPSG:4326",
        band_nir="B8A",
        band_swir="B12",
    ):
        self.path = SENTINEL2_PATH
        self.pystac_client = PystacClient.open(
            self.path, modifier=planetary_computer.sign_inplace
        )
        self.band_nir = band_nir
        self.band_swir = band_swir
        self.crs = crs
        self.buffer = buffer

        # TODO [#17]: Settle on standards for storing polygons
        # Oscillating between geojsons and geopandas dataframes, which is a bit messy. Should pick one and stick with it.
        self.geojson_boundary = None
        self.bbox = None
        if geojson_boundary is not None:
            self.set_boundary(geojson_boundary)

        if barc_classifications is not None:
            self.barc_classifications = self.ingest_barc_classifications(
                barc_classifications
            )

        self.derived_classifications = None
        print("Initialized Sentinel2Client with bounds: {}".format(self.bbox))

    def set_boundary(self, geojson_boundary):
        """
        Sets the boundary for later query to STAC API.

        Args:
            geojson_boundary (GeoJSON): The boundary of the query area.

        Returns:
            None
        """
        boundary_gpd = gpd.GeoDataFrame.from_features(geojson_boundary)
        # TODO [#7]: Generalize Sentinel2Client to accept any CRS
        # This is hard-coded to assume 4326 - when we draw an AOI, we will change this logic depending on what makes frontend sense
        if not boundary_gpd.crs:
            geojson_boundary = boundary_gpd.set_crs("EPSG:4326")
        self.geojson_boundary = geojson_boundary.to_crs(self.crs)

        geojson_bbox = geojson_boundary.bounds.to_numpy()[0]
        self.bbox = [
            geojson_bbox[0].round(decimals=8) - self.buffer,
            geojson_bbox[1].round(decimals=8) - self.buffer,
            geojson_bbox[2].round(decimals=8) + self.buffer,
            geojson_bbox[3].round(decimals=8) + self.buffer,
        ]

    def ingest_metrics_stack(self, metrics_stack):
        """
        Ingests the metrics stack and checks for the required metrics.

        Args:
            metrics_stack (dict): The metrics stack.

        Raises:
            ValueError: If a required metric is missing from the metrics stack.
        """
        required_metrics = ["nbr_prefire", "nbr_postfire", "dnbr", "rdnbr", "rbr"]

        for metric in required_metrics:
            if metric not in metrics_stack.burn_metric:
                raise ValueError(
                    f"Required metric '{metric}' is missing from the metrics stack."
                )

        self.metrics_stack = metrics_stack

    def get_items(self, date_range, from_bbox=True, max_items=None):
        """
        Retrieves items from the Sentinel-2-L2A collection based on the specified date range and optional parameters.

        Args:
            date_range (tuple): A tuple containing the start and end dates of the desired date range in the format (start_date, end_date).
            from_bbox (bool, optional): Specifies whether to search for items within the bounding box defined by the `bbox` attribute. Defaults to True.
            max_items (int, optional): The maximum number of items to retrieve. Defaults to None, which retrieves all available items.

        Returns:
            pystac.ItemCollection: A collection of items matching the specified criteria.
        """
        date_range_fmt = "{}/{}".format(date_range[0], date_range[1])

        # TODO [#14]: Cloud cover response to smoke
        # Right now we don't give any mind to smoke occlusion, but we should considering we will have bias if smoke occludes our imagery

        query = {
            "collections": ["sentinel-2-l2a"],
            "datetime": date_range_fmt,
            # "query": {"eo:cloud_cover": {"lt": cloud_cover}}
        }

        if from_bbox:
            query["bbox"] = self.bbox
        else:
            query["intersects"] = self.geojson_boundary

        if max_items:
            query["max_items"] = max_items

        items = self.pystac_client.search(**query).item_collection()

        return items

    def ingest_barc_classifications(self, barc_classifications_xarray):
        """
        Ingests and processes BARC (Burned Area Reflectance Classification) classifications, such that
        they conform to our desired CRS and boundary, same as our derived classifications.

        Args:
            barc_classifications_xarray (xarray.DataArray): The BARC classifications as an xarray DataArray.

        Returns:
            xarray.DataArray: The processed barc classifications.
        """
        barc_classifications = barc_classifications_xarray.rio.reproject(
            dst_crs=self.crs, nodata=0
        )
        barc_classifications = barc_classifications.astype(int)
        barc_classifications = barc_classifications.rio.clip(
            self.geojson_boundary.geometry.values, self.geojson_boundary.crs
        )
        # Set everything outside the geojson_boundary to np.nan
        barc_classifications = barc_classifications.where(
            barc_classifications != 0, np.nan
        )
        return barc_classifications

    def arrange_stack(self, items, resolution=20):
        """
        Arrange and process (reduce the time dimension, according to `reduce_time_range`) a stack of Sentinel items.

        Args:
            items (list): List of Sentinel items to stack.
            resolution (int): Resolution of the stacked data.

        Returns:
            stack (xarray.DataArray): Stacked and processed Sentinel data, in our desired CRS, clipped to the boundary.

        Raises:
            None

        """
        # Get CRS from first item (this isn't inferred by stackstac, for some reason)
        stac_endpoint_crs = items[0].properties["proj:epsg"]

        # Filter to our relevant bands and stack (again forcing the above crs, from the endpoint itself)
        print("About to stack ^")
        stack = stackstac.stack(
            items,
            epsg=stac_endpoint_crs,
            resolution=resolution,
            assets=[self.band_nir, self.band_swir],
            chunksize=(
                -1,
                1,
                512,
                512,
            ),  # Recommended by stackstac docs if we're immediately reducing time
        )
        stack.rio.write_crs(stac_endpoint_crs, inplace=True)

        # Reduce over the time dimension
        print("About to reduce stack")
        stack = self.reduce_time_range(stack)

        # Buffer the bounds to ensure we get all the data we need, plus a
        # little extra for visualization outside burn area

        bounds_stac_crs = self.geojson_boundary.to_crs(
            stac_endpoint_crs
        ).geometry.values

        # Clip to our bounds (need to temporarily convert to the endpoint crs, since we can't reproject til we have <= 3 dims)
        stack = stack.rio.clip(bounds_stac_crs, bounds_stac_crs.crs)

        # Reproject to our desired CRS
        print("About to reproject")
        stack = stack.rio.reproject(dst_crs=self.crs, nodata=np.nan)

        if (
            np.isnan(stack.sel(band="B8A").values).all()
            or np.isnan(stack.sel(band="B12").values).all()
        ):
            raise ValueError("No data in the stack")

        return stack

    def reduce_time_range(self, range_stack):
        """
        Reduces the time range of the given range stack by taking the median along the time dimension.

        Args:
            range_stack (xarray.DataArray): The range stack to be reduced.

        Returns:
            xarray.DataArray: The reduced range stack.
        """

        # TODO [#30]: Think about best practice for reducing time dimension pre/post fire
        # This will probably get a bit more sophisticated, but for now, just take the median
        # We will probably run into issues of cloud occlusion, and for really long fire events,
        # we might want to look into time-series effects of greenup, drying, etc, in the adjacent
        # non-burned areas so attempt to isolate fire effects vs exogenous seasonal stuff. Ultimately,
        # we just want a decent reducer to squash the time dim, so median works for now.
        return range_stack.median(dim="time")

    def query_fire_event(
        self, prefire_date_range, postfire_date_range, from_bbox=True, max_items=None
    ):
        """
        Queries the fire event by retrieving prefire and postfire items based on the given date ranges.

        Args:
            prefire_date_range (tuple): A tuple representing the date range for prefire items.
            postfire_date_range (tuple): A tuple representing the date range for postfire items.
            from_bbox (bool, optional): Flag indicating whether to retrieve items from bounding box. Defaults to True.
            max_items (int, optional): Maximum number of items to retrieve. Defaults to None.

        Raises:
            ValueError: If there are insufficient imagery in the date ranges to calculate burn metrics. Note that
                this might also happen if there are no items in the date range, so it's not necessarily a problem with
                the date ranges themselves (but it will definitely be an issue if the date range is too narrow for any imagery)

        """
        # Get items for pre and post fire range
        print("About to get prefire items")
        prefire_items = self.get_items(
            prefire_date_range, from_bbox=from_bbox, max_items=max_items
        )
        print("About to get postfire items")
        postfire_items = self.get_items(
            postfire_date_range, from_bbox=from_bbox, max_items=max_items
        )

        if len(prefire_items) == 0 or len(postfire_items) == 0:
            raise ValueError(
                "Date ranges insufficient for enough imagery to calculate burn metrics"
            )

        print("About to arrange prefire stack")
        self.prefire_stack = self.arrange_stack(prefire_items)
        print("About to arrange postfire stack")
        self.postfire_stack = self.arrange_stack(postfire_items)

        n_unique_datetimes_prefire = len(
            np.unique([item.datetime for item in prefire_items])
        )
        n_unique_datetimes_postfire = len(
            np.unique([item.datetime for item in postfire_items])
        )

        return {
            "n_prefire_passes": n_unique_datetimes_prefire,
            "n_postfire_passes": n_unique_datetimes_postfire,
            "latest_pass": max([item.datetime for item in postfire_items]).strftime(
                format="%Y-%m-%d"
            ),
        }

    def calc_burn_metrics(self):
        """
        Calculates burn metrics using prefire and postfire Sentinel satellite data.

        Returns:
            metrics_stack (xarray.DataArray): Stack of burn metrics, wiht bands of nir and swir,
                named according to self.band_nir and self.band_swir.
        """
        self.metrics_stack = calc_burn_metrics(
            prefire_nir=self.prefire_stack.sel(band=self.band_nir),
            prefire_swir=self.prefire_stack.sel(band=self.band_swir),
            postfire_nir=self.postfire_stack.sel(band=self.band_nir),
            postfire_swir=self.postfire_stack.sel(band=self.band_swir),
        )

    def classify(self, thresholds, threshold_source, burn_metric="dnbr"):
        """
        Classify the metrics stack based on the given thresholds and threshold source. Note that,
        in v0, we are not actually calling this classify method, we are classifing at runtime using
        titiler's algorithms (`src.lib.titiler_algorithms`). After classification, we save the
        classification to the `derived_classifications` attribute of the Sentinel2Client.

        Parameters:
            thresholds (list): List of threshold values.
            threshold_source (str): Source of the thresholds.
            burn_metric (str): Metric to be used for classification (default: "dnbr").

        Returns:
            None
        """
        new_classification = classify_burn(
            self.metrics_stack.sel(burn_metric=burn_metric), thresholds=thresholds
        )
        new_classification = new_classification.expand_dims(dim="classification_source")
        new_classification["classification_source"] = [threshold_source]

        if self.derived_classifications is None:
            self.derived_classifications = new_classification
        elif (
            threshold_source
            in self.derived_classifications.classification_source.values
        ):
            self.derived_classifications = self.derived_classifications.where(
                self.derived_classifications.classification_source != threshold_source,
                new_classification,
            )
        else:
            self.derived_classifications = xr.concat(
                [self.derived_classifications, new_classification],
                dim="classification_source",
            )

    def derive_boundary_flood_fill(self, seed_points, metric_name="rbr", inplace=True):
        """
        Derive a boundary from the given metric layer based on the specified threshold, and set it as the boundary of the Sentinel2Client.
        This means that, when we derive boundary, we use the derived boundary for visualization (and this boundary is saved as `boundary.geojson`
        within the s3 bucket), and we clip the metrics stack to this boundary.

        Args:
            metric_name (str): Name of the metric layer.
            threshold (float): Threshold value for the metric layer.

        Returns:
            None
        """
        print("Deriving boundary using metric: {}".format(metric_name))

        seed_points_gpd = gpd.GeoDataFrame.from_features(seed_points["features"])

        metric_layer = self.metrics_stack.sel(burn_metric=metric_name)

        if seed_points_gpd is not None:
            # Add a dim called 'seed' to denote whether the pixel is a seed point
            metric_layer = metric_layer.expand_dims(dim="seed")
            metric_layer["seed"] = xr.full_like(metric_layer, False, dtype=bool)

            for point in seed_points_gpd.geometry:
                nearest_pixel = metric_layer.sel(x=point.x, y=point.y, method="nearest")
                nearest_pixel_x = nearest_pixel.x.values
                nearest_pixel_y = nearest_pixel.y.values
                metric_layer["seed"].loc[dict(x=nearest_pixel_x, y=nearest_pixel_y)] = (
                    True
                )

        geojson_boundary = derive_boundary(
            metric_layer=metric_layer,
            thresholding_strategy=OtsuThreshold(),
            segmentation_strategy=FloodFillSegmentation(),
        )
        geojson_boundary_gpd = gpd.GeoDataFrame.from_features(geojson_boundary)

        if not geojson_boundary:
            raise NoFireBoundaryDetectedError(
                "No fire boundary detected for the given threshold {threshold} and metric {metric_name}"
            )

        if inplace:

            self.set_boundary(geojson_boundary)
            self.metrics_stack = self.metrics_stack.rio.clip(
                geojson_boundary_gpd.geometry.values, geojson_boundary_gpd.crs
            )
            self.metrics_stack = self.metrics_stack.where(
                self.metrics_stack != 0, np.nan
            )

        else:
            return geojson_boundary_gpd
