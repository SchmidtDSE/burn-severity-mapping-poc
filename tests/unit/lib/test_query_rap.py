import pytest
from src.lib.query_rap import rap_get_biomass
import unittest.mock as mock
import xarray as xr


@mock.patch("rioxarray.open_rasterio")
def test_rap_get_biomass(mock_get, test_geojson, test_3d_xarray):
    # Define the arguments for upload_fire_event
    rap_estimates = test_3d_xarray

    # Duplicate the xarray to add two new bands
    rap_estimates = xr.concat([rap_estimates, rap_estimates], dim="band")
    rap_estimates["band"] = [
        "annual_forb_and_grass",
        "perennial_forb_and_grass",
        "shrub",
        "tree",
    ]

    mock_get.return_value.content = rap_estimates
    result = rap_get_biomass("2020-01-01", test_geojson)
    # Add assertions to check the result

    assert isinstance(result, xr.DataArray)
