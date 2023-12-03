import requests
import geopandas as gpd
from pystac_client import Client
from datetime import datetime
import planetary_computer
import rioxarray as rxr
import xarray as xr
import numpy as np
import stackstac
from .burn_severity import calc_burn_metrics

SENTINEL2_PATH = "https://planetarycomputer.microsoft.com/api/stac/v1"


class Sentinel2Client:
    def __init__(self, geojson_bounds, buffer = .1, crs = "EPSG:4326", band_nir = "B8A", band_swir = "B12"):
        self.path = SENTINEL2_PATH
        self.client = Client.open(
            self.path,
            modifier = planetary_computer.sign_inplace
        )

        self.band_nir = band_nir
        self.band_swir = band_swir
        self.crs = crs

        self.buffer = buffer
        self.geojson_bounds = geojson_bounds.to_crs(crs)

        geojson_bbox = geojson_bounds.bounds.to_numpy()[0]
        self.bbox = [
            geojson_bbox[0].round(decimals=2) - buffer,
            geojson_bbox[1].round(decimals=2) - buffer,
            geojson_bbox[2].round(decimals=2) + buffer,
            geojson_bbox[3].round(decimals=2) + buffer
        ]

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

        items = self.client.search(**query).item_collection()

        return items

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
        self.debug_reduced_stack = stack
        self.debug_missingness = stack.isnull()

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

        self.debug_clpped_stack = stack

        # print("after clip")
        # print(stack.isel(x=slice(0, 5), y=slice(0, 5)).values)

        # Reproject to our desired CRS
        stack = stack.rio.reproject(
            dst_crs = self.crs,
            nodata = np.nan
        )


        self.debug_reprojected_stack = stack
        # print("after reproject")
        # print(stack.isel(x=slice(0, 5), y=slice(0, 5)).values)

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
