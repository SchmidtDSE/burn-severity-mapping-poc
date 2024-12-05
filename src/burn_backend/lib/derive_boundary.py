import xarray as xr
from scipy.ndimage import binary_fill_holes, gaussian_filter, binary_dilation
from skimage.filters import threshold_otsu, median
from skimage.segmentation import flood_fill, clear_border
from src.burn_backend.util.raster_to_poly import raster_mask_to_geojson
from abc import ABC, abstractmethod
from shapely.ops import unary_union
from shapely.geometry import MultiPolygon
import numpy as np
import geopandas as gpd

## DEBUG
import matplotlib.pyplot as plt


## THRESHOLDING STRATEGIES


class ThresholdingStrategy(ABC):
    @abstractmethod
    def apply(self, metric_layer):
        pass


class OtsuThreshold(ThresholdingStrategy):

    def apply(self, metric_layer):
        threshold = threshold_otsu(metric_layer.values)

        # This might already exist if the user has tried this fire event before
        if "disturbed" in metric_layer.coords:
            metric_layer = metric_layer.drop("disturbed")

        metric_layer.expand_dims(dim="disturbed")
        metric_layer["disturbed"] = xr.DataArray(
            np.where(metric_layer.values > threshold, True, False),
            dims=metric_layer.dims,
            coords=metric_layer.coords,
        )

        return metric_layer


class SimpleThreshold(ThresholdingStrategy):
    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def apply(self, metric_layer):
        metric_layer.expand_dims(dim="disturbed")
        metric_layer["disturbed"] = xr.DataArray(
            np.where(metric_layer.values > self.threshold, True, False),
            dims=metric_layer.dims,
            coords=metric_layer.coords,
        )

        return metric_layer


## POSTPROCESSING STRATEGIES


class PostprocessingStrategy(ABC):
    @abstractmethod
    def apply(self, burn_boundary_raster):
        pass


class FillHoles(PostprocessingStrategy):
    def apply(self, disturbed_layer_int):
        filled_holes = binary_fill_holes(disturbed_layer_int)
        return filled_holes


class BinaryDilation(PostprocessingStrategy):
    def __init__(self, iterations=1):
        self.iterations = iterations

    def apply(self, disturbed_layer_int):
        dilated_boundary = binary_dilation(
            disturbed_layer_int, iterations=self.iterations
        )
        return dilated_boundary


## SEGMENTATION STRATEGIES


class SegmentationStrategy(ABC):
    @abstractmethod
    def apply(self, burn_boundary_raster):
        pass


class FloodFillSegmentation(SegmentationStrategy):

    def __init__(self, seed_indices=None):
        self.seed_indices = seed_indices

    def apply(self, disturbed_layer_int):

        segmented_burns = np.full_like(disturbed_layer_int, fill_value=False)

        for seed_index in self.seed_indices:

            # Skimage needs the seed point as a tuple, for some reason
            print(f"Processing seed point at indices: {seed_index}")

            # Skip if the seed point is not in the burn boundary, so we don't
            # get the negative space of the burn boundary
            if disturbed_layer_int[seed_index] == 0:
                continue

            # Flood fill the burn boundary from the seed point, and combine with
            # the existing segmented burns from other seed points
            burn_boundary_segmented = flood_fill(
                image=disturbed_layer_int,
                seed_point=seed_index,
                new_value=True,
            )
            segmented_burns = np.logical_or(segmented_burns, burn_boundary_segmented)

        return segmented_burns


## SMOOTHING STRATEGIES


class SmoothingStrategy(ABC):
    @abstractmethod
    def apply(self, burn_boundary_raster):
        pass


class GaussianSmoothing(SmoothingStrategy):
    def __init__(self, sigma=1):
        self.sigma = sigma

    def apply(self, disturbed_layer_int):
        smoothed_disturbed_int = gaussian_filter(disturbed_layer_int, sigma=self.sigma)
        return smoothed_disturbed_int


class MedianSmoothing(SmoothingStrategy):
    def __init__(self, size=3):
        self.size = size

    def apply(self, disturbed_layer_int):
        smoothed_disturbed_int = median_filter(disturbed_layer_int, size=self.size)
        return smoothed_disturbed_int


## POLYGON CLEANUP STRATEGIES


class PolygonCleanupStrategy(ABC):
    @abstractmethod
    def apply(self, burn_boundary_polygon):
        pass


class RestrictToSeedPoints(PolygonCleanupStrategy):
    def __init__(self, seed_locations_gpd=None):
        self.seed_locations_gpd = seed_locations_gpd

    def apply(self, burn_boundary_polygon):
        seed_locations_shapes = unary_union(self.seed_locations_gpd.geometry)

        # If the burn boundary is a MultiPolygon, we want to keep only the polygons that intersect the seed points
        burn_boundary_polygon = burn_boundary_polygon["geometry"].apply(
            lambda geom: (
                MultiPolygon(
                    [
                        polygon
                        for polygon in geom.geoms
                        if polygon.intersects(seed_locations_shapes)
                    ]
                )
                if geom.geom_type == "MultiPolygon"
                else geom
            )
        )

        # Drop any empty geometries - if none remain, return None
        burn_boundary_polygon = burn_boundary_polygon[
            burn_boundary_polygon.geometry.apply(lambda geom: not geom.is_empty)
        ]
        if burn_boundary_polygon.is_empty.all():
            return None

        return burn_boundary_polygon


## PIPELINE


class Pipeline:
    def __init__(
        self,
        thresholding_strategy,
        segmentation_strategy,
        smoothing_strategies,
        postprocessing_strategies,
        polygon_cleanup_strategies,
    ):
        self._thresholding_strategy = thresholding_strategy
        self._segmentation_strategy = segmentation_strategy
        self._smoothing_strategies = smoothing_strategies
        self._postprocessing_strategies = postprocessing_strategies
        self._polygon_cleanup_strategies = polygon_cleanup_strategies

    def add_thresholding_strategy(self, thresholding_strategy):
        self._thresholding_strategy = thresholding_strategy

    def add_segmentation_strategy(self, segmentation_strategy):
        self._segmentation_strategy = segmentation_strategy

    def add_smoothing_strategy(self, smoothing_strategy):
        self._smoothing_strategies.append(smoothing_strategy)

    def add_postprocessing_strategy(self, postprocessing_strategy):
        self._postprocessing_strategies.append(postprocessing_strategy)

    def process(self, metric_layer):

        # Apply thresholding strategy - will result in a xr.DataArray with a boolean mask as 'disturbed'
        burn_boundary_raster = self._thresholding_strategy.apply(metric_layer)

        ## TODO: Smelly hard code indexing to remove the seed dimension (0, x, y), which caused annoying dimensionality issues
        ## when I removed, so leaving for now

        # Here on, we use skimage, which expects an int numpy array
        disturbed_layer_int = burn_boundary_raster["disturbed"].values.astype(np.int8)[
            0, :, :
        ]

        # Apply segmentation strategie - will result in a binary mask
        disturbed_layer_int = self._segmentation_strategy.apply(disturbed_layer_int)

        # Apply postprocessing strategies - primarily to fill holes
        for postprocessing_strategy in self._postprocessing_strategies:
            disturbed_layer_int = postprocessing_strategy.apply(disturbed_layer_int)

        # Apply smoothing strategies - reduce noise / artifacts
        for smoothing_strategy in self._smoothing_strategies:
            disturbed_layer_int = smoothing_strategy.apply(disturbed_layer_int)

        # Now, overwrite the original disturbed layer with the processed one
        burn_boundary_raster["disturbed"] = xr.DataArray(
            [disturbed_layer_int.astype(bool)],
            dims=burn_boundary_raster.dims,
            coords=burn_boundary_raster.coords,
        )

        # Convert to a MultiPolygon GeoDataFrame from raster
        burn_boundary_multipolygon = raster_mask_to_geojson(
            burn_boundary_raster["disturbed"]
        )
        burn_boundary_gpd = gpd.GeoDataFrame.from_features(burn_boundary_multipolygon)

        # Clean up polygon artifacts due to coercion from raster
        for polygon_cleanup_strategy in self._polygon_cleanup_strategies:
            burn_boundary_gpd = polygon_cleanup_strategy.apply(burn_boundary_gpd)

        return burn_boundary_gpd


def derive_boundary(
    metric_layer,
    pipeline,
):

    ## TODO(!smelly): Some part of the spectral index process is creating a buffer of NaN
    ## at the outside edge of the metric layer - not an issue to replace with 0 in this case
    ## but zeros inside the image will be erroneously identified as unburned islands which is
    ## a big problem.
    metric_values_exist_binary = np.where(np.isnan(metric_layer.values), 0, 1)
    interior_nan_filled = binary_fill_holes(metric_values_exist_binary)
    no_interior_nan_detected = np.array_equal(
        interior_nan_filled, metric_values_exist_binary
    )

    # TODO (!feat): Improve (and investigate) handling of internal NaNs within derived boundary
    # Internal NaNs are a problem because they may be interpreted as unburned islands, unless we handle
    # them directly. So far so good, it appears we only get these at the edges of the boundary where we
    # may have interpolation issues, so this is very conservative, but a little hacky.

    if no_interior_nan_detected:
        # In this case, we aren't missing interior unburned islands, but we still want the original
        # shape preserved so we can use the mask to fill in the holes later and re-apply the spatial
        # information to the final boundary. We are replacing NaNs with the mean of the metric layer,
        # so that we minimize the leverage of these points in the thresholding process. We will
        # mask them out later.
        metric_layer.values = np.nan_to_num(
            metric_layer.values, np.mean(metric_layer.values)
        )
    else:
        # In this case, we MAY be missing interior unburned islands
        # if we proceed. For now we just want to raise an error, but
        # later we may need to be robust to this
        raise ValueError("NaN values within interior of metric layer")

    burn_boundary_multipolygon = pipeline.process(metric_layer)

    return burn_boundary_multipolygon
