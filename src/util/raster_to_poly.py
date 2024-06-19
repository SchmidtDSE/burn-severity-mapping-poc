from rasterio import features
from shapely.ops import unary_union, shape
from shapely.geometry import MultiPolygon, Polygon, mapping
import numpy as np


def raster_mask_to_geojson(binary_mask):
    """
    Converts a binary raster mask to a GeoJSON representation.

    Args:
        binary_mask (xr.DataArray): Binary mask representing the raster.

    Returns:
        dict: GeoJSON representation of the mask boundary.
    """
    mask = binary_mask.values
    transform = binary_mask.rio.transform()

    # Convert the binary mask to shapes
    results = [
        shape(s)
        for i, (s, v) in enumerate(
            features.shapes(mask.astype(np.uint8), transform=transform)
        )
        if v == 1
    ]

    if len(results) == 0:
        return None

    # Merge polygons and create a convex hull if necessary
    merged = unary_union(results)

    boundary_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": mapping(merged),
            }
        ],
    }

    return boundary_geojson
