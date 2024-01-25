from rasterio import features
import geopandas as gpd
from shapely.geometry import shape
import numpy as np
import json


def raster_mask_to_geojson(binary_mask):
    mask = binary_mask.values
    transform = binary_mask.rio.transform()

    # Convert the binary mask to shapes
    results = (
        {"properties": {"raster_val": v}, "geometry": s}
        for i, (s, v) in enumerate(
            features.shapes(mask.astype(np.uint8), transform=transform)
        )
        if v == 1
    )

    # Convert the shapes to a GeoDataFrame to get GeoJSON
    geoms = list(results)
    gdf = gpd.GeoDataFrame.from_features(geoms)

    # weirdly to_dict doesn't create a geojson - need to convert to json then back to dict
    boundary_geojson = gdf.to_json()
    boundary_geojson = json.loads(boundary_geojson)

    return boundary_geojson
