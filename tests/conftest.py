import pytest
import pystac
import rioxarray as rxr
import numpy as np
import xarray as xr
import pickle
import random

### PyStac ItemCollection


@pytest.fixture
def test_stac_items():
    with open("tests/assets/test_stac_items.json") as f:
        test_stac_items = pystac.read_file(f.read())
    return test_stac_items


### Stacked xarray (time, band, y, x)


@pytest.fixture
def test_valid_xarray():
    with open("tests/assets/test_imagery_with_time_xarray.pkl", "rb") as f:
        test_valid_xarray = pickle.load(f)
    return test_valid_xarray


@pytest.fixture
def test_nan_xarray(test_valid_xarray):
    test_nan_xarray = xr.full_like(test_valid_xarray, np.nan)
    return test_nan_xarray


@pytest.fixture
def test_zero_xarray(test_valid_xarray):
    test_zero_xarray = xr.full_like(test_valid_xarray, 0)
    return test_zero_xarray


### Reduced across time window (only spatial dims + band remain)


@pytest.fixture
def test_reduced_xarray():
    with open("tests/assets/test_imagery_time_reduced_xarray.pkl", "rb") as f:
        test_reduced_xarray = pickle.load(f)
    return test_reduced_xarray


@pytest.fixture
def test_reduced_nan_xarray(test_reduced_xarray):
    test_nan_array = xr.full_like(test_reduced_xarray, np.nan)
    return test_nan_array


@pytest.fixture
def test_reduced_zero_xarray(test_reduced_xarray):
    test_reduced_zero_xarray = xr.full_like(test_reduced_xarray, 0)
    return test_reduced_zero_xarray


### Dummy NBR xarray


@pytest.fixture
def test_nbr_xarrays(test_reduced_xarray):
    nbr_shape = test_reduced_xarray.sel(band="B12").shape
    prefire_test_nbr_xarray = xr.DataArray(
        np.random.rand(*nbr_shape), dims=test_reduced_xarray.sel(band="B12").dims
    )
    postfire_test_nbr_xarray = (
        xr.DataArray(
            np.random.rand(*nbr_shape), dims=test_reduced_xarray.sel(band="B12").dims
        )
        - 0.25  # to simulate a postfire NBR, which is lower than prefire
    )
    test_dnbr_xarray = prefire_test_nbr_xarray - postfire_test_nbr_xarray
    return prefire_test_nbr_xarray, postfire_test_nbr_xarray, test_dnbr_xarray
