import requests
import geopandas as gpd
import rasterio.features
from shapely.geometry import shape, MultiPolygon
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

SENTINEL2_PATH = "https://planetarycomputer.microsoft.com/api/stac/v1"


class Sentinel2Client:
    def __init__(
        self,
        geojson_boundary,
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
        self.set_boundary(geojson_boundary)

        if barc_classifications is not None:
            self.barc_classifications = self.ingest_barc_classifications(
                barc_classifications
            )

        self.derived_classifications = None
        print("Initialized Sentinel2Client with bounds: {}".format(self.bbox))

    def set_boundary(self, geojson_boundary):
        boundary_gpd = gpd.GeoDataFrame.from_features(geojson_boundary)
        # TODO [#7]: Generalize Sentinel2Client to accept any CRS
        # This is hard-coded to assume 4326 - when we draw an AOI, we will change this logic depending on what makes frontend sense
        if not boundary_gpd.crs:
            geojson_boundary = boundary_gpd.set_crs("EPSG:4326")
        self.geojson_boundary = geojson_boundary.to_crs(self.crs)

        geojson_bbox = geojson_boundary.bounds.to_numpy()[0]
        self.bbox = [
            geojson_bbox[0].round(decimals=2) - self.buffer,
            geojson_bbox[1].round(decimals=2) - self.buffer,
            geojson_bbox[2].round(decimals=2) + self.buffer,
            geojson_bbox[3].round(decimals=2) + self.buffer,
        ]

    def get_items(self, date_range, from_bbox=True, max_items=None):
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
        # TODO [#13]: More appropriate error handling - seperate legit from expected
        # Right now, many of the requests to STAC are wrapped in try/excepts at the top level, to
        # ensure no problems with timeouts and whatnot, which was an artifact of early development,
        # but this is problematic now that we use form submission

        # Get CRS from first item (this isn't inferred by stackstac, for some reason)
        stac_endpoint_crs = items[0].properties["proj:epsg"]

        # Filter to our relevant bands and stack (again forcing the above crs, from the endpoint itself)
        stack = stackstac.stack(
            items,
            epsg=stac_endpoint_crs,
            resolution=resolution,
            assets=[self.band_nir, self.band_swir],
        )
        stack.rio.write_crs(stac_endpoint_crs, inplace=True)

        # Reduce over the time dimension
        stack = self.reduce_time_range(stack)

        # Buffer the bounds to ensure we get all the data we need, plus a
        # little extra for visualization outside burn area

        bounds_stac_crs = self.geojson_boundary.to_crs(
            stac_endpoint_crs
        ).geometry.values

        # Clip to our bounds (need to temporarily convert to the endpoint crs, since we can't reproject til we have <= 3 dims)
        stack = stack.rio.clip(bounds_stac_crs, bounds_stac_crs.crs)

        # Reproject to our desired CRS
        stack = stack.rio.reproject(dst_crs=self.crs, nodata=np.nan)

        return stack

    def reduce_time_range(self, range_stack):
        # This will probably get a bit more sophisticated, but for now, just take the median
        # We will probably run into issues of cloud occlusion, and for really long fire events,
        # we might want to look into time-series effects of greenup, drying, etc, in the adjacent
        # non-burned areas so attempt to isolate fire effects vs exogenous seasonal stuff. Ultimately,
        # we just want a decent reducer to squash the time dim, so median works for now.

        return range_stack.median(dim="time")

    def query_fire_event(
        self, prefire_date_range, postfire_date_range, from_bbox=True, max_items=None
    ):
        # Get items for pre and post fire range
        prefire_items = self.get_items(
            prefire_date_range, from_bbox=from_bbox, max_items=max_items
        )
        postfire_items = self.get_items(
            postfire_date_range, from_bbox=from_bbox, max_items=max_items
        )

        if len(prefire_items) == 0 or len(postfire_items) == 0:
            raise ValueError('Date ranges insufficient for enough imagery to calculate burn metrics')

        self.prefire_stack = self.arrange_stack(prefire_items)
        self.postfire_stack = self.arrange_stack(postfire_items)

    def calc_burn_metrics(self):
        self.metrics_stack = calc_burn_metrics(
            prefire_nir=self.prefire_stack.sel(band=self.band_nir),
            prefire_swir=self.prefire_stack.sel(band=self.band_swir),
            postfire_nir=self.postfire_stack.sel(band=self.band_nir),
            postfire_swir=self.postfire_stack.sel(band=self.band_swir),
        )

    def classify(self, thresholds, threshold_source, burn_metric="dnbr"):
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

    def derive_boundary(self, metric_name="rbr", threshold=0.025):
        metric_layer = self.metrics_stack.sel(burn_metric=metric_name)

        # Threshold the metric layer to get a binary boundary
        binary_mask = metric_layer.where(metric_layer >= threshold, 0)
        binary_mask = binary_mask.where(binary_mask == 0, 1)

        # Smooth the boundary, removing small artifacts
        filled_mask = binary_fill_holes(binary_mask)
        smoothed_mask = gaussian_filter(filled_mask, sigma=1)
        buffered_mask = binary_dilation(smoothed_mask, iterations=1)
        int_mask = buffered_mask.astype(int)

        # Convert back to a DataArray
        boundary_xr = xr.DataArray(
            int_mask,
            coords=metric_layer.coords,
            dims=metric_layer.dims,
            attrs=metric_layer.attrs,
        )
        boundary_xr.rio.write_crs(metric_layer.rio.crs, inplace=True)

        # Convert to geojson
        # TODO [#18]: More robust conversion from raster to poly
        # This seems overcomplicated for what a simple polygonize should do, but near as I can tell
        # there is no out of the box solution in xarray/rioxarray for this. This seems like something we
        # will do regularly, so we should probably make a util function for it and understand why it's
        # not a built-in method... must have more complications than I realize currently.

        boundary_geojson = raster_mask_to_geojson(boundary_xr)

        self.set_boundary(boundary_geojson)
        self.clip_metrics_stack_to_boundary()

    def clip_metrics_stack_to_boundary(self):
        self.metrics_stack = self.metrics_stack.rio.clip(
            self.geojson_boundary.geometry.values, self.geojson_boundary.crs
        )

        self.metrics_stack = self.metrics_stack.where(self.metrics_stack != 0, np.nan)
