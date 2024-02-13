import pytest
import pystac
import rasterio as rio
import xarray as xr
import numpy as np

### PyStac ItemCollection

@pytest.fixture
def test_stac_items():
    with open('assets/test_stac_items.json') as f:
        test_stac_items = pystac.read_file(f.read())
    return test_stac_items

### Stacked xarray (time, band, y, x)

@pytest.fixture
def test_valid_xarray():
    with open('assets/test_nir.tif') as f:
        test_xarray_nir = rio.open(f)
    with open('assets/test_swir.tif') as f:
        test_xarray_swir = rio.open(f)
    return xr.concat([test_xarray_nir, test_xarray_swir], dim='band')

@pytest.fixture
def test_nan_xarray():
    with open('assets/test_nir.tif') as f:
        test_xarray_nir = rio.open(f)
    nan_array = xr.full_like(test_xarray_nir, np.nan)
    test_nan_xarray = xr.concat([nan_array.rename(band="B8A"), nan_array.rename(band="B12")], dim='band')
    return test_nan_xarray

@pytest.fixture
def test_zero_xarray():
    with open('assets/test_nir.tif') as f:
        test_xarray_nir = rio.open(f)
    zero_array = xr.full_like(test_xarray_nir, 0)
    test_zero_xarray = xr.concat([zero_array.rename(band="B8A"), zero_array.rename(band="B12")], dim='band')
    return test_zero_xarray

### Reduced across time window (only spatial dims + band remain)

@pytest.fixture
def test_reduced_xarray():
    with open('assets/test_nir_reduced.tif') as f:
        test_xarray_nir = rio.open(f)
    with open('assets/test_swir_reduced.tif') as f:
        test_xarray_swir = rio.open(f)
    test_reduced_xarray = xr.concat([test_xarray_nir, test_xarray_swir], dim='band')
    return test_reduced_xarray

@pytest.fixture
def test_reduced_nan_xarray():
    with open('assets/test_nir_reduced.tif') as f:
        test_xarray_nir = rio.open(f)
    nan_array = xr.full_like(test_xarray_nir, np.nan)
    test_reduced_nan_xarray = xr.concat([nan_array.rename(band="B8A"), nan_array.rename(band="B12")], dim='band')
    return test_reduced_nan_xarray

@pytest.fixture
def test_reduced_zero_xarray():
    with open('assets/test_nir_reduced.tif') as f:
        test_xarray_nir = rio.open(f)
    zero_array = xr.full_like(test_xarray_nir, 0)
    test_reduced_zero_xarray = xr.concat([zero_array.rename(band="B8A"), zero_array.rename(band="B12")], dim='band')
    return test_reduced_zero_xarray
