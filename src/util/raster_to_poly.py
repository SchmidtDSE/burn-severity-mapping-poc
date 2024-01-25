from rasterio import features
from shapely.ops import unary_union, shape
from shapely.geometry import MultiPolygon, mapping
import numpy as np
from rasterio import features
from shapely.ops import unary_union, shape
from shapely.geometry import MultiPolygon, mapping
import numpy as np


def raster_mask_to_geojson(binary_mask):
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

    # Merge polygons and create a convex hull if necessary
    merged = unary_union(results)
    if isinstance(merged, MultiPolygon):
        merged = merged.convex_hull

    # Convert the geometry to GeoJSON
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
