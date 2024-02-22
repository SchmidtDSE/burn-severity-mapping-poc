import pytest
from src.lib.query_rap import rap_get_biomass
import unittest.mock as mock
import xarray as xr
import geopandas as gpd
from shapely.geometry import Polygon


@mock.patch("rioxarray.open_rasterio")
def test_rap_get_biomass(mock_open, test_3d_valid_xarray_epsg_4326):
    # Define the arguments for upload_fire_event
    rap_estimates = test_3d_valid_xarray_epsg_4326

    # Duplicate the xarray to add two new bands (just to have four, like RAP)
    rap_estimates = xr.concat([rap_estimates, rap_estimates], dim="band")
    rap_estimates["band"] = [1, 2, 3, 4]

    # Get the bounds
    bounds = rap_estimates.rio.bounds()

    # Create a square polygon using the bounds
    square_polygon = Polygon(
        [
            (bounds[0], bounds[1]),
            (bounds[0], bounds[3]),
            (bounds[2], bounds[3]),
            (bounds[2], bounds[1]),
        ]
    )

    # Convert the polygon to a GeoJSON
    square_geojson = gpd.GeoSeries([square_polygon]).__geo_interface__

    mock_open.return_value = rap_estimates
    result = rap_get_biomass("2020-01-01", square_geojson, buffer_distance=1)
    # Add assertions to check the result

    assert isinstance(result, xr.DataArray)
