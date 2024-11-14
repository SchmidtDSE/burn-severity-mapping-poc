import xarray as xr
from scipy.ndimage import binary_fill_holes, gaussian_filter, binary_dilation
from skimage.filters import threshold_otsu, median
from skimage.segmentation import flood_fill, clear_border
from src.burn_backend.util.raster_to_poly import raster_mask_to_geojson
from abc import ABC, abstractmethod
import numpy as np

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
        burn_boundary_raster["disturbed"] = xr.DataArray(
            [filled_holes.astype(bool)],
            dims=burn_boundary_raster.dims,
            coords=burn_boundary_raster.coords,
        )

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
    def apply(self, disturbed_layer_int):
        seed_locations_x, seed_locations_y = np.where(
            metric_layer["seed"].values[0, :, :]
        )
        seed_locations = list(zip(seed_locations_x, seed_locations_y))

        segmented_burns = np.full_like(disturbed_layer_int, fill_value=False)
        for seed_point in seed_locations:

            # Skimage needs the seed point as a tuple, for some reason
            print(f"Processing seed point: {seed_point}")

            # Skip if the seed point is not in the burn boundary, so we don't
            # get the negative space of the burn boundary
            if disturbed_layer_int[seed_point] == 0:
                continue

            # Flood fill the burn boundary from the seed point, and combine with
            # the existing segmented burns from other seed points
            burn_boundary_segmented = flood_fill(
                image=disturbed_layer_int,
                seed_point=seed_point,
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
        burn_boundary_raster["disturbed"] = xr.DataArray(
            [smoothed_disturbed_int.astype(bool)],
            dims=burn_boundary_raster.dims,
            coords=burn_boundary_raster.coords,
        )

        return burn_boundary_raster


class MedianSmoothing(SmoothingStrategy):
    def __init__(self, size=3):
        self.size = size

    def apply(self, disturbed_layer_int):
        smoothed_disturbed_int = median_filter(disturbed_layer_int, size=self.size)
        burn_boundary_raster["disturbed"] = xr.DataArray(
            [smoothed_disturbed_int.astype(bool)],
            dims=burn_boundary_raster.dims,
            coords=burn_boundary_raster.coords,
        )

        return burn_boundary_raster


## PIPELINE


class Pipeline:
    def __init__(
        self,
        thresholding_strategy,
        segmentation_strategy,
        smoothing_strategies,
        postprocessing_strategies,
    ):
        self._thresholding_strategy = thresholding_strategy
        self._segmentation_strategy = segmentation_strategy
        self._smoothing_strategies = smoothing_strategies
        self._postprocessing_strategies = postprocessing_strategies

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

        return burn_boundary_raster


DEFAULT_PIPELINE = Pipeline(
    thresholding_strategy=OtsuThreshold(),
    segmentation_strategy=FloodFillSegmentation(),
    smoothing_strategies=[GaussianSmoothing(sigma=2)],
    postprocessing_strategies=[FillHoles(), BinaryDilation(iterations=2)],
)


def derive_boundary(
    metric_layer,
    pipeline=DEFAULT_PIPELINE,
):

    ## TODO: Some part of the spectral index process is creating a buffer of NaN
    ## at the outside edge of the metric layer - not an issue to replace with 0 in this case
    ## but zeros inside the image will be erroneously identified as unburned islands which is
    ## a big problem.
    metric_values_exist_binary = np.where(np.isnan(metric_layer.values), 0, 1)
    interior_nan_filled = binary_fill_holes(metric_values_exist_binary)
    no_interior_nan_detected = np.array_equal(
        interior_nan_filled, metric_values_exist_binary
    )

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

    burn_boundary_raster = pipeline.process(metric_layer)

    burn_boundary_polygon = raster_mask_to_geojson(burn_boundary_raster["disturbed"])

    return burn_boundary_polygon
