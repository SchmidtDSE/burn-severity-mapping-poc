# FILEPATH: /workspace/tests/unit/lib/test_query_sentinel.py

import pytest
from unittest.mock import MagicMock, patch, call
from src.lib.query_sentinel import Sentinel2Client
import geopandas as gpd
from shapely.geometry import Polygon
import xarray as xr
import numpy as np


def test_set_boundary(test_geojson):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    # Check that the boundary and bbox were set correctly
    assert client.geojson_boundary is not None
    assert client.bbox is not None


def test_get_items(test_geojson, test_stac_item_collection):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    # Mock the pystac_client.search method to return a test item collection
    client.pystac_client.search = MagicMock()
    client.pystac_client.search.item_collection.return_value = test_stac_item_collection

    # Call get_items and check that the search method was called with the correct arguments
    date_range = ("2020-01-01", "2020-02-01")
    __stac_item_collection = client.get_items(date_range)
    client.pystac_client.search.assert_called_with(
        collections=["sentinel-2-l2a"],
        datetime="{}/{}".format(*date_range),
        bbox=client.bbox,
    )


def test_arrange_stack(test_geojson, test_stac_item_collection):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    # Stack the test item collection
    stack = client.arrange_stack(test_stac_item_collection)

    assert all(stack.band.values == ["B8A", "B12"])
    assert stack.dims == ("band", "y", "x")

    test_bounds = gpd.GeoDataFrame.from_features(test_geojson["features"]).bounds
    test_minx, test_miny, test_maxx, test_maxy = (
        test_bounds.minx[0],
        test_bounds.miny[0],
        test_bounds.maxx[0],
        test_bounds.maxy[0],
    )

    stack_minx, stack_miny, stack_maxx, stack_maxy = stack.rio.bounds()

    assert np.isclose(stack_minx, test_minx, rtol=1e-5)
    assert np.isclose(stack_miny, test_miny, rtol=1e-5)
    assert np.isclose(stack_maxx, test_maxx, rtol=1e-5)
    assert np.isclose(stack_maxy, test_maxy, rtol=1e-5)


def test_reduce_time_range(test_geojson, test_4d_valid_xarray_epsg_4326):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    assert "time" in test_4d_valid_xarray_epsg_4326.time.dims

    reduced = client.reduce_time_range(test_4d_valid_xarray_epsg_4326)
    assert not "time" in reduced.dims


def test_query_fire_event(test_geojson, test_stac_item_collection):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    # Mock the client.get_items() method to return a test item collection
    client.get_items = MagicMock()
    client.get_items.return_value = test_stac_item_collection

    # Mock arrange stack method
    client.arrange_stack = MagicMock()

    # Call the query_fire_event method
    client.query_fire_event(
        prefire_date_range=("2020-01-01", "2020-02-01"),
        postfire_date_range=("2020-03-01", "2020-04-01"),
    )

    # Check that the get_items method was called with the correct arguments
    client.get_items.assert_has_calls(
        [
            call(("2020-01-01", "2020-02-01"), from_bbox=True, max_items=None),
            call(("2020-03-01", "2020-04-01"), from_bbox=True, max_items=None),
        ]
    )

    assert client.prefire_stack is not None
    assert client.postfire_stack is not None
