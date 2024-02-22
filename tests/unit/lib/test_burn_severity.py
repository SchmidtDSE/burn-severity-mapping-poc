import pytest
import src.lib.burn_severity as burn_severity
import xarray as xr


def test_calc_nbr(
    test_4d_valid_xarray_epsg_4326,
    test_4d_nan_xarray_epsg_4326,
    test_4d_zero_xarray_epsg_4326,
):
    """Test calc_nbr function."""

    # Rename `band1` and `band2` to `B8A` and `B12` respectively
    test_4d_valid_xarray_epsg_4326["band"] = [
        "B8A",
        "B12",
    ]
    test_4d_nan_xarray_epsg_4326["band"] = ["B8A", "B12"]
    test_4d_zero_xarray_epsg_4326["band"] = [
        "B8A",
        "B12",
    ]

    # Test valid input
    xr_nir = test_4d_valid_xarray_epsg_4326.sel(band="B8A")
    xr_swir = test_4d_valid_xarray_epsg_4326.sel(band="B12")
    result = burn_severity.calc_nbr(xr_nir, xr_swir)
    assert result is not None
    assert result.shape == xr_swir.shape == xr_nir.shape

    # Test zero input - should work, but not meaningful
    xr_nir = test_4d_zero_xarray_epsg_4326.sel(band="B8A")
    xr_swir = test_4d_zero_xarray_epsg_4326.sel(band="B12")
    result = burn_severity.calc_nbr(xr_nir, xr_swir)
    assert result is not None
    assert result.shape == xr_swir.shape == xr_nir.shape

    # Test NaN input - also should work, but not meaningful
    xr_nir = test_4d_nan_xarray_epsg_4326.sel(band="B8A")
    xr_swir = test_4d_nan_xarray_epsg_4326.sel(band="B12")
    result = burn_severity.calc_nbr(xr_nir, xr_swir)
    assert result is not None
    assert result.shape == xr_swir.shape == xr_nir.shape
    assert result.isnull().all()


def test_calc_dnbr(test_3d_xarray):
    test_nbr_prefire = test_3d_xarray
    test_nbr_postfire = test_3d_xarray + 0.15
    result = burn_severity.calc_dnbr(test_nbr_prefire, test_nbr_postfire)
    assert result is not None
    assert result.shape == test_nbr_prefire.shape == test_nbr_postfire.shape


def test_calc_rdnbr(test_3d_xarray):
    test_nbr_prefire = test_3d_xarray
    test_dnbr = xr.full_like(test_3d_xarray, 0.15)
    result = burn_severity.calc_rdnbr(test_dnbr, test_nbr_prefire)
    assert result is not None
    assert result.shape == test_dnbr.shape == test_nbr_prefire.shape


def test_calc_rbr(test_3d_xarray):
    test_nbr_prefire = test_3d_xarray
    test_dnbr = xr.full_like(test_3d_xarray, 0.15)
    result = burn_severity.calc_rbr(test_dnbr, test_nbr_prefire)
    assert result is not None
    assert result.shape == test_nbr_prefire.shape == test_nbr_prefire.shape
