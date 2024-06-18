# FILEPATH: /workspace/tests/unit/lib/test_query_sentinel.py

import pytest
from unittest.mock import MagicMock, patch, call
from src.lib.query_sentinel import Sentinel2Client
from src.lib.burn_severity import calc_burn_metrics
import geopandas as gpd
from shapely.geometry import Polygon
import xarray as xr
import numpy as np
from rioxarray.raster_array import RasterArray


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


## TODO Why does rio.reproject call the original stac assets from planetary computer, even when reprojecting a local computed RasterArray?:
## rio.reproject fails with picked item collection because it is calling the original stac assets from planetary computer
## This makes very little sense since the thing being reprojected has already had some computation done on it, so we aren't
## reprojecting the original stac assets at all.

# @patch.object(RasterArray, "reproject", MagicMock())
# def test_arrange_stack(test_geojson, test_stac_item_collection):
#     # Initialize Sentinel2Client
#     client = Sentinel2Client(test_geojson)

#     # Stack the test item collection
#     stack = client.arrange_stack(test_stac_item_collection)

#     assert all(stack.band.values == ["B8A", "B12"])
#     assert stack.dims == ("band", "y", "x")

#     test_bounds = gpd.GeoDataFrame.from_features(test_geojson["features"]).bounds
#     test_minx, test_miny, test_maxx, test_maxy = (
#         test_bounds.minx[0],
#         test_bounds.miny[0],
#         test_bounds.maxx[0],
#         test_bounds.maxy[0],
#     )

#     stack_minx, stack_miny, stack_maxx, stack_maxy = stack.rio.bounds()

#     assert np.isclose(stack_minx, test_minx, rtol=1e-5)
#     assert np.isclose(stack_miny, test_miny, rtol=1e-5)
#     assert np.isclose(stack_maxx, test_maxx, rtol=1e-5)
#     assert np.isclose(stack_maxy, test_maxy, rtol=1e-5)


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

    # Check that the arrange_stack method was called with the correct arguments
    client.arrange_stack.assert_called_with(test_stac_item_collection)
    assert client.prefire_stack is not None
    assert client.postfire_stack is not None


def test_calc_burn_metrics(test_geojson, test_3d_valid_xarray_epsg_4326):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    # Initialize prefire and postfire stacks
    client.band_nir = "B8A"
    client.band_swir = "B12"

    # Init prefire stack
    test_3d_valid_xarray_epsg_4326["band"] = ["B8A", "B12"]
    prefire_stack = test_3d_valid_xarray_epsg_4326
    client.prefire_stack = prefire_stack

    # Init postfire stack
    postfire_stack = test_3d_valid_xarray_epsg_4326.copy(deep=True)
    postfire_stack.loc[dict(band=client.band_swir)] += 0.25
    postfire_stack.loc[dict(band=client.band_nir)] -= 0.25
    client.postfire_stack = postfire_stack

    # Call the calc_burn_metrics method
    client.calc_burn_metrics()

    # Check that the metrics stack was created and that it contains the correct metrics
    assert client.metrics_stack is not None
    assert all(
        [
            metric in client.metrics_stack.burn_metric
            for metric in ["nbr_prefire", "nbr_postfire", "dnbr", "rdnbr", "rbr"]
        ]
    )


## TODO: Needs a rework for the new derived boundary approach w/ seeds

# def test_derive_boundary(test_geojson, test_3d_valid_xarray_epsg_4326):
#     # Initialize Sentinel2Client
#     client = Sentinel2Client(test_geojson)

#     # Initialize metrics stack
#     metrics_stack = test_3d_valid_xarray_epsg_4326.rename({"band": "burn_metric"})
#     metrics_stack["burn_metric"] = ["rbr", "dnbr"]
#     client.metrics_stack = metrics_stack

#     # Save the initial boundary
#     initial_boundary = client.geojson_boundary

#     # Call the derive_boundary method
#     client.derive_boundary(metric_name="rbr")

#     # Check that the boundary was updated
#     assert all(
#         (initial_boundary.bounds != client.geojson_boundary.bounds).values[0].tolist()
#     )


def test_ingest_metrics_stack(test_geojson, test_3d_valid_xarray_epsg_4326):
    # Initialize Sentinel2Client
    client = Sentinel2Client(test_geojson)

    # Initialize metrics stack
    metrics_stack = xr.concat(
        [
            test_3d_valid_xarray_epsg_4326[0, :, :].rename({"band": "burn_metric"}),
            test_3d_valid_xarray_epsg_4326[0, :, :].rename({"band": "burn_metric"}),
            test_3d_valid_xarray_epsg_4326[0, :, :].rename({"band": "burn_metric"}),
            test_3d_valid_xarray_epsg_4326[0, :, :].rename({"band": "burn_metric"}),
            test_3d_valid_xarray_epsg_4326[0, :, :].rename({"band": "burn_metric"}),
        ],
        dim="burn_metric",
    )

    metrics_stack["burn_metric"] = [
        "nbr_prefire",
        "nbr_postfire",
        "dnbr",
        "rdnbr",
        "rbr",
    ]

    # Call the ingest_metrics_stack method
    client.ingest_metrics_stack(metrics_stack)

    # Check that the metrics stack was ingested correctly
    assert client.metrics_stack is not None
    assert all(
        [
            metric in client.metrics_stack.burn_metric
            for metric in ["nbr_prefire", "nbr_postfire", "dnbr", "rdnbr", "rbr"]
        ]
    )

    # Test with missing metric
    missing_metric_metrics_stack = metrics_stack[:3, :, :]
    with pytest.raises(ValueError):
        client.ingest_metrics_stack(missing_metric_metrics_stack)
