import geopandas as gpd
import time
import rasterio
import rioxarray as rxr
import numpy as np
import json


def rap_get_biomass(ignition_date, boundary_geojson, buffer_distance=0.01):
    """
    Retrieves biomass estimates from the Rangeland Analysis Platform for a given ignition year and boundary location.
    RAP provides estimates of biomass for four categories: annual forb and grass, perennial forb and grass, shrub, and tree.
    http://rangeland.ntsg.umt.edu/data/rap/rap-vegetation-biomass/v3/README
    Data are available from 1986 to 2022, if a pre-1986 date is provided, a ValueError is raised., if a post-2022 date is provided,
    the 2022 data is used.

    Parameters:
        ignition_date (str): The ignition date in the format 'YYYY-MM-DD'.
        boundary_geojson (dict): The boundary geometry in GeoJSON format.
        buffer_distance (float, optional): The buffer distance around the boundary. Defaults to 0.01.

    Returns:
        xr.DataArray: Biomass estimates from the RAP dataset.

    Raises:
        ValueError: If the ignition date is before 1986, where RAP data is not available.

    """
    boundary_gdf = gpd.GeoDataFrame.from_features(boundary_geojson)

    # Load boundary geometry (in GeoJSON format)
    minx, miny, maxx, maxy = boundary_gdf.total_bounds

    # Get the RAP URL
    rap_year = time.strptime(ignition_date, "%Y-%m-%d").tm_year
    if rap_year > 2022:
        print("RAP data is only available up to 2022 - falling back to 2022 RAP data")
        rap_year = 2022
    elif rap_year < 1986:
        raise ValueError("RAP data is only available from 1986")

    rap_url = f"http://rangeland.ntsg.umt.edu/data/rap/rap-vegetation-npp/v3/vegetation-npp-v3-{rap_year}.tif"

    # Create a buffer around the boundary
    boundary_gdf_buffer = boundary_gdf.buffer(buffer_distance)

    # Create a window from the buffered boundary
    with rasterio.open(rap_url) as src:
        window = rasterio.windows.from_bounds(minx, miny, maxx, maxy, src.transform)

    # Open the GeoTIFF file as a rioxarray with the window and out_shape parameters
    rap_estimates = rxr.open_rasterio(rap_url, masked=True).rio.isel_window(window)

    # Rename for RAP bands based on README:
    # - Band 1 - annual forb and grass
    # - Band 2 - perennial forb and grass
    # - Band 3 - shrub
    # - Band 4 - tree
    rap_estimates = rap_estimates.assign_coords(
        band=(
            "band",
            ["annual_forb_and_grass", "perennial_forb_and_grass", "shrub", "tree"],
        )
    )
    rap_estimates = rap_estimates.rio.clip(
        boundary_gdf_buffer.geometry.values, "EPSG:4326"
    )

    # add np.nan where 65535, also based on readme
    rap_estimates = rap_estimates.where(rap_estimates != 65535, np.nan)

    return rap_estimates
