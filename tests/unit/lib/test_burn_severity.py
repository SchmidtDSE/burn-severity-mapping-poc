import pytest
import src.lib.burn_severity as burn_severity


def test_calc_nbr(test_valid_xarray, test_zero_xarray, test_nan_xarray):
    """Test calc_nbr function."""
    # Test valid input
    xr_nir = test_valid_xarray.sel(band="B8A")
    xr_swir = test_valid_xarray.sel(band="B12")
    result = burn_severity.calc_nbr(xr_nir, xr_swir)
    assert result is not None
    assert result.shape == xr_swir.shape == xr_nir.shape

    # Test zero input - should work, but not meaningful
    xr_nir = test_zero_xarray.sel(band="B8A")
    xr_swir = test_zero_xarray.sel(band="B12")
    result = burn_severity.calc_nbr(xr_nir, xr_swir)
    assert result is not None
    assert result.shape == xr_swir.shape == xr_nir.shape

    # Test NaN input - also should work, but not meaningful
    xr_nir = test_nan_xarray.sel(band="B8A")
    xr_swir = test_nan_xarray.sel(band="B12")
    result = burn_severity.calc_nbr(xr_nir, xr_swir)
    assert result is not None
    assert result.shape == xr_swir.shape == xr_nir.shape
    assert result.isnull().all()


def test_calc_dnbr(test_nbr_xarrays):
    test_nbr_prefire, test_nbr_postfire, __test_dnbr = test_nbr_xarrays
    result = burn_severity.calc_dnbr(test_nbr_prefire, test_nbr_postfire)
    assert result is not None
    assert result.shape == test_nbr_prefire.shape == test_nbr_postfire.shape


def test_calc_rdnbr(test_nbr_xarrays):
    test_nbr_prefire, __test_nbr_postfire, test_dnbr = test_nbr_xarrays
    result = burn_severity.calc_rdnbr(test_dnbr, test_nbr_prefire)
    assert result is not None
    assert result.shape == test_dnbr.shape == test_nbr_prefire.shape


def test_calc_rbr(test_nbr_xarrays):
    test_nbr_prefire, __test_nbr_postfire, test_dnbr = test_nbr_xarrays
    result = burn_severity.calc_rbr(test_dnbr, test_nbr_prefire)
    assert result is not None
    assert result.shape == test_nbr_prefire.shape == test_nbr_prefire.shape
