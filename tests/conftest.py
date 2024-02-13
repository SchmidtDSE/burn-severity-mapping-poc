import pytest
import pystac
import rioxarray as rxr
import numpy as np
import xarray as xr

### PyStac ItemCollection


@pytest.fixture
def test_stac_items():
    with open("tests/assets/test_stac_items.json") as f:
        test_stac_items = pystac.read_file(f.read())
    return test_stac_items


### Stacked xarray (time, band, y, x)


@pytest.fixture
def test_valid_xarray():
    test_xarray_nir = rxr.open_rasterio("tests/assets/test_nir.tif")
    test_xarray_swir = rxr.open_rasterio("tests/assets/test_swir.tif")

    return xr.concat(
        [test_xarray_nir, test_xarray_swir],
        dim="band",
    )


@pytest.fixture
def test_nan_xarray():
    test_xarray_nir = rxr.open_rasterio("tests/assets/test_nir.tif")
    nan_array = xr.full_like(test_xarray_nir, np.nan)
    test_nan_xarray = xr.concat(
        [nan_array.rename(band="B8A"), nan_array.rename(band="B12")], dim="band"
    )
    return test_nan_xarray


@pytest.fixture
def test_zero_xarray():
    test_xarray_nir = rxr.open_rasterio("tests/assets/test_nir.tif")
    zero_array = xr.full_like(test_xarray_nir, 0)
    test_zero_xarray = xr.concat(
        [zero_array.rename(band="B8A"), zero_array.rename(band="B12")], dim="band"
    )
    return test_zero_xarray


### Reduced across time window (only spatial dims + band remain)


@pytest.fixture
def test_reduced_xarray():
    test_xarray_nir = rxr.open_rasterio("tests/assets/test_nir_reduced.tif")
    test_xarray_swir = rxr.open_rasterio("tests/assets/test_swir_reduced.tif")
    test_reduced_xarray = xr.concat([test_xarray_nir, test_xarray_swir], dim="band")
    return test_reduced_xarray


@pytest.fixture
def test_reduced_nan_xarray():
    test_xarray_nir = rxr.open_rasterio("tests/assets/test_nir_reduced.tif")
    nan_array = xr.full_like(test_xarray_nir, np.nan)
    test_reduced_nan_xarray = xr.concat(
        [nan_array.rename(band="B8A"), nan_array.rename(band="B12")], dim="band"
    )
    return test_reduced_nan_xarray


@pytest.fixture
def test_reduced_zero_xarray():
    test_xarray_nir = rxr.open_rasterio("tests/assets/test_nir_reduced.tif")
    zero_array = xr.full_like(test_xarray_nir, 0)
    test_reduced_zero_xarray = xr.concat(
        [zero_array.rename(band="B8A"), zero_array.rename(band="B12")], dim="band"
    )
    return test_reduced_zero_xarray
