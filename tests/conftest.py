import pytest
import pystac
import rioxarray as rxr
import numpy as np
import xarray as xr
import pickle
import random
import json
import unittest.mock as mock


### Helpers
def extract_metadata_and_other_coords(data_array):
    metadata = {"attrs": {}, "coords": {}}
    for attr in data_array.attrs:
        metadata["attrs"][attr] = data_array.attrs[attr]
    for coord in data_array.coords:
        if coord not in ["band", "time", "y", "x", "epsg"] and not coord.startswith(
            "proj"
        ):
            metadata["coords"][coord] = data_array.coords[coord]
    return metadata


def construct_dataarray(metadata, values, bands, x, y, epsg, time=None):
    coords = metadata["coords"]
    coords.update({"x": x, "y": y, "epsg": epsg, "band": bands})
    if time is not None:
        coords.update({"time": time})
        new_data_array = xr.DataArray(
            data=values, coords=coords, dims=["time", "band", "y", "x"]
        )
    else:
        new_data_array = xr.DataArray(
            data=values, coords=coords, dims=["band", "y", "x"]
        )
    for attr, value in metadata["attrs"].items():
        new_data_array.attrs[attr] = value
    return new_data_array


### PyStac ItemCollection


@pytest.fixture
def test_stac_items():
    with open("tests/assets/test_stac_items.json") as f:
        test_stac_items = pystac.read_file(f.read())
    return test_stac_items


### Coords and time windows


@pytest.fixture
def test_spatial_coords_epsg_4326():
    x = np.array(
        [
            -116.04612911,
            -116.04594111,
            -116.04575312,
            -116.04556512,
            -116.04537713,
            -116.04518913,
            -116.04500113,
            -116.04481314,
            -116.04462514,
            -116.04443714,
        ]
    )

    y = np.array(
        [
            33.90347264,
            33.90328464,
            33.90309664,
            33.90290865,
            33.90272065,
            33.90253265,
            33.90234466,
            33.90215666,
            33.90196867,
            33.90178067,
        ]
    )

    return x, y


@pytest.fixture
def test_spatial_coords_epsg_32611():
    x = np.array(
        [
            500980.0,
            501000.0,
            501020.0,
            501040.0,
            501060.0,
            501080.0,
            501100.0,
            501120.0,
            501140.0,
            501160.0,
        ]
    )

    y = np.array(
        [
            3798040.0,
            3798020.0,
            3798000.0,
            3797980.0,
            3797960.0,
            3797940.0,
            3797920.0,
            3797900.0,
            3797880.0,
            3797860.0,
        ]
    )

    return x, y


@pytest.fixture
def test_time_coords():
    prefire = np.array(
        [
            "2023-05-10T18:19:21.024000000",
            "2023-05-15T18:19:19.024000000",
            "2023-05-20T18:19:21.024000000",
            "2023-05-25T18:19:19.024000000",
            "2023-05-30T18:19:21.024000000",
            "2023-06-04T18:19:19.024000000",
            "2023-06-09T18:19:21.024000000",
        ],
        dtype="datetime64[ns]",
    )

    postfire = np.array(
        [
            "2023-06-19T18:19:21.024000000",
            "2023-06-24T18:19:19.024000000",
            "2023-06-29T18:19:21.024000000",
            "2023-07-04T18:19:19.024000000",
            "2023-07-09T18:19:21.024000000",
            "2023-07-14T18:19:19.024000000",
        ],
        dtype="datetime64[ns]",
    )

    return prefire, postfire


@pytest.fixture
def test_metadata_and_other_coords():
    with open("tests/assets/test_metadata_and_other_coords.pkl", "rb") as f:
        test_metadata_and_other_coords = pickle.load(f)
    return test_metadata_and_other_coords


### Stacked xarray (time, band, y, x)


@pytest.fixture
def test_4d_valid_xarray_epsg_4326(
    test_spatial_coords_epsg_4326, test_time_coords, test_metadata_and_other_coords
):
    x, y = test_spatial_coords_epsg_4326
    prefire, postfire = test_time_coords
    metadata = test_metadata_and_other_coords
    bands = ["band1", "band2"]
    values = np.random.rand(len(prefire) + len(postfire), len(bands), len(y), len(x))
    test_valid_xarray = construct_dataarray(
        metadata=metadata,
        values=values,
        bands=bands,
        x=x,
        y=y,
        epsg=4326,
        time=np.concatenate((prefire, postfire)),
    )
    return test_valid_xarray


@pytest.fixture
def test_4d_nan_xarray_epsg_4326(test_4d_valid_xarray_epsg_4326):
    test_nan_xarray = xr.full_like(test_4d_valid_xarray_epsg_4326, np.nan)
    return test_nan_xarray


@pytest.fixture
def test_4d_zero_xarray_epsg_4326(test_4d_valid_xarray_epsg_4326):
    test_zero_xarray = xr.full_like(test_4d_valid_xarray_epsg_4326, 0)
    return test_zero_xarray


### Reduced across time window (only spatial dims + band remain)


@pytest.fixture
def test_3d_valid_xarray_epsg_4326(
    test_spatial_coords_epsg_4326, test_metadata_and_other_coords
):
    x, y = test_spatial_coords_epsg_4326
    metadata = test_metadata_and_other_coords
    bands = ["band1", "band2"]
    values = np.random.rand(len(bands), len(y), len(x))
    test_3d_xarray = construct_dataarray(
        metadata=metadata, values=values, bands=bands, x=x, y=y, epsg=4326
    )
    return test_3d_xarray


@pytest.fixture
def test_3d_nan_xarray(test_3d_xarray):
    test_nan_array = xr.full_like(test_3d_xarray, np.nan)
    return test_nan_array


@pytest.fixture
def test_3d_zero_xarray(test_3d_xarray):
    test_reduced_zero_xarray = xr.full_like(test_3d_xarray, 0)
    return test_reduced_zero_xarray


### GeoJSON


@pytest.fixture
def test_geojson():
    with open("tests/assets/test_boundary_geology.geojson") as f:
        test_geojson = json.load(f)
    return test_geojson


@pytest.fixture
def test_geojson_split():
    with open("tests/assets/test_boundary_geology_split.geojson") as f:
        test_geojson = json.load(f)
    return test_geojson


### Responses


@pytest.fixture
def test_sdm_get_esa_mapunitid_poly_response():
    with open("tests/assets/test_sdm_get_esa_mapunitid_poly_response.pkl", "rb") as f:
        test_sdm_get_esa_mapunitid_poly_response = pickle.load(f)
    return test_sdm_get_esa_mapunitid_poly_response
