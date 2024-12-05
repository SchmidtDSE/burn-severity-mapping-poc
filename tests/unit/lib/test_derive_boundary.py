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

## TODO(!test): Add test for derive_boundary logic, including restriction polygon
#Issue URL: https://github.com/SchmidtDSE/burn-severity-mapping-poc/issues/66


def test_derive_boundary_success(
    test_intermediate_burn_metrics_tiny_dome, test_seed_points_tiny_dome
):
    # Load test_points_gpd
    seed_locations_gpd = gpd.GeoDataFrame.from_features(
        test_seed_points_tiny_dome["features"]
    )

    # To match how this runs in the pipeline, select just rbr
    metrics_stack = test_intermediate_burn_metrics_tiny_dome.sel(burn_metric="rbr")

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
    result = derive_boundary(metrics_stack, pipeline)

    # Check that the result is as expected
    assert result is not None
    assert isinstance(result, gpd.GeoDataFrame)
    assert not result.empty


def test_derive_boundary_failure(test_geojson, test_3d_invalid_xarray):

    # Initialize the necessary inputs
    geojson_boundary = test_geojson
    metrics_stack = test_3d_invalid_xarray.rename({"band": "burn_metric"})
    metrics_stack["burn_metric"] = ["rbr", "dnbr"]

    # Call the derive_boundary function and expect it to fail
    with pytest.raises(ValueError):
        derive_boundary_function(geojson_boundary, metrics_stack, metric_name="rbr")
