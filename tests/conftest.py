import pytest
import pystac
import rioxarray as rxr
import numpy as np
import xarray as xr
import pickle
import random
import json

### PyStac ItemCollection


@pytest.fixture
def test_stac_items():
    with open("tests/assets/test_stac_items.json") as f:
        test_stac_items = pystac.read_file(f.read())
    return test_stac_items


### Stacked xarray (time, band, y, x)


@pytest.fixture
def test_4d_xarray():
    with open("tests/assets/test_imagery_with_time_xarray.pkl", "rb") as f:
        test_valid_xarray = pickle.load(f)
    return test_valid_xarray


@pytest.fixture
def test_4d_nan_xarray(test_4d_xarray):
    test_nan_xarray = xr.full_like(test_4d_xarray, np.nan)
    return test_nan_xarray


@pytest.fixture
def test_4d_zero_xarray(test_4d_xarray):
    test_zero_xarray = xr.full_like(test_4d_xarray, 0)
    return test_zero_xarray


### Reduced across time window (only spatial dims + band remain)


@pytest.fixture
def test_3d_xarray():
    with open("tests/assets/test_imagery_time_reduced_xarray.pkl", "rb") as f:
        test_reduced_xarray = pickle.load(f)
    return test_reduced_xarray


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
