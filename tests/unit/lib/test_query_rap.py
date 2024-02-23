import pytest
from src.lib.query_rap import rap_get_biomass
from unittest.mock import patch
from rioxarray.raster_array import RasterArray
import xarray as xr
import geopandas as gpd
from shapely.geometry import Polygon


def test_rap_get_biomass_success(test_3d_valid_xarray_epsg_4326):
    # Define the arguments for upload_fire_event
    rap_estimates = test_3d_valid_xarray_epsg_4326

    # Duplicate the xarray to add two new bands (just to have four, like RAP)
    rap_estimates = xr.concat([rap_estimates, rap_estimates], dim="band")
    rap_estimates["band"] = [1, 2, 3, 4]

    # Get the bounds
    minx, miny, maxx, maxy = rap_estimates.rio.bounds()

    # Create a square polygon using the bounds
    square_polygon = Polygon(
        [
            (minx, miny),
            (minx, maxy),
            (maxx, maxy),
            (maxx, miny),
            (minx, miny),
        ]
    )

    # Convert the polygon to a GeoJSON
    square_geojson = gpd.GeoSeries([square_polygon]).__geo_interface__

    result = rap_get_biomass(
        "2020-01-01",
        square_geojson,
        buffer_distance=1,
        rap_url_year_fstring="tests/assets/test_rap_small_{year}.tif",
    )
    # Add assertions to check the result

    assert isinstance(result, xr.DataArray)

    result_minx, result_miny, result_maxx, result_maxy = result.rio.bounds()
    assert result_minx <= minx
    assert result_miny <= miny
    assert result_maxx >= maxx
    assert result_maxy >= maxy
