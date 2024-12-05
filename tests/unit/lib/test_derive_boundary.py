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


def test_derive_boundary_success(test_3d_gradient_circle_xarray_epsg_4326):
    # Initialize the necessary inputs
    metrics_stack = test_3d_gradient_circle_xarray_epsg_4326.rename(
        {"band": "burn_metric"}
    )
    metrics_stack["burn_metric"] = ["rbr", "dnbr"]

    # To match how this runs in the pipeline, select just rbr
    metrics_stack = metrics_stack.sel(burn_metric="rbr")

    # valid indices - choose the exact center of the circle, which should be 1
    metrics_stack_width, metrics_stack_height = metrics_stack.shape
    valid_seed_indices = [(metrics_stack_width // 2, metrics_stack_height // 2)]

    # Create a GeoDataFrame with the valid seed location, using real coordinates from the metrics_stack
    seed_index_cell = metrics_stack.isel(
        x=valid_seed_indices[0][0], y=valid_seed_indices[0][1]
    )
    valid_seed_location_gpd = gpd.GeoDataFrame(
        {"geometry": [Point(seed_index_cell["x"].values, seed_index_cell["y"].values)]},
        crs="EPSG:4326",
    )

    pipeline = Pipeline(
        thresholding_strategy=OtsuThreshold(),
        segmentation_strategy=FloodFillSegmentation(seed_indices=valid_seed_indices),
        smoothing_strategies=[GaussianSmoothing(sigma=1)],
        postprocessing_strategies=[FillHoles(), BinaryDilation(iterations=2)],
        polygon_cleanup_strategies=[
            RestrictToSeedPoints(seed_locations_gpd=valid_seed_location_gpd)
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
