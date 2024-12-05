import pytest
from src.burn_backend.lib.derive_boundary import (
    derive_boundary,
    Pipeline,
    FloodFillSegmentation,
    OtsuThreshold,
    GaussianSmoothing,
    FillHoles,
    BinaryDilation,
    RestrictToSeedPoints,
)
import geopandas as gpd
from shapely.geometry import Point
import xarray as xr
import numpy as np
from shapely import MultiPolygon, Polygon

## TODO(!test): Add test for derive_boundary logic, including restriction polygon


def test_derive_boundary_success_multiple_seeds(
    test_intermediate_burn_metrics_tiny_dome,
    test_multiple_seed_points_tiny_dome,
):
    # Load test_points_gpd
    seed_locations_gpd = gpd.GeoDataFrame.from_features(
        test_multiple_seed_points_tiny_dome["features"]
    )

    # To match how this runs in the pipeline, select just rbr
    metric_layer = test_intermediate_burn_metrics_tiny_dome.sel(burn_metric="rbr")

    # Add a dim called 'seed' to denote whether the pixel is a seed point
    metric_layer = metric_layer.expand_dims(dim="seed")
    metric_layer["seed"] = xr.full_like(metric_layer, False, dtype=bool)

    for point in seed_locations_gpd.geometry:
        # Find the nearest pixel to the seed point, we want the index, not the value
        nearest_pixel = metric_layer.sel(x=point.x, y=point.y, method="nearest")
        metric_layer["seed"].loc[
            dict(x=nearest_pixel.x.values, y=nearest_pixel.y.values)
        ] = True

    seed_indices = list(zip(*np.where(metric_layer["seed"].values[0, :, :])))

    # Define the pipeline
    pipeline = Pipeline(
        thresholding_strategy=OtsuThreshold(),
        segmentation_strategy=FloodFillSegmentation(seed_indices=seed_indices),
        smoothing_strategies=[GaussianSmoothing(sigma=1)],
        postprocessing_strategies=[FillHoles(), BinaryDilation(iterations=2)],
        polygon_cleanup_strategies=[
            RestrictToSeedPoints(seed_locations_gpd=seed_locations_gpd)
        ],
    )

    # Call the derive_boundary function
    result = derive_boundary(metric_layer, pipeline)

    # Check that the result is as expected
    assert isinstance(result, gpd.GeoSeries)
    assert isinstance(result[0], MultiPolygon)
