import xarray as xr
from scipy.ndimage import binary_fill_holes, gaussian_filter, binary_dilation
from skimage.filters import threshold_otsu
from skimage.segmentation import flood_fill, clear_border
from ..util.raster_to_poly import raster_mask_to_geojson
from abc import ABC, abstractmethod
import numpy as np


## THRESHOLDING STRATEGIES
class ThresholdingStrategy(ABC):
    @abstractmethod
    def apply(self, metric_layer):
        pass


class OtsuThreshold(ThresholdingStrategy):

    def apply(self, metric_layer):
        threshold = threshold_otsu(metric_layer.values)
        metric_layer.expand_dims(dim="burned")
        metric_layer["burned"] = xr.DataArray(
            np.where(metric_layer.values > threshold, False, True),
            dims=metric_layer.dims,
            coords=metric_layer.coords,
        )


class SimpleThreshold(ThresholdingStrategy):
    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def apply(self, metric_layer):
        metric_layer.expand_dims(dim="disturbed")
        metric_layer["disturbed"] = xr.DataArray(
            np.where(metric_layer.values > self.threshold, False, True),
            dims=metric_layer.dims,
            coords=metric_layer.coords,
        )

        return metric_layer


## SEGMENTATION STRATEGIES
class SegmentationStrategy(ABC):
    @abstractmethod
    def apply(self, burn_boundary_raster):
        pass


class FloodFillSegmentation(SegmentationStrategy):
    def __init__(self, seed_location=None):
        self.seed_location = seed_location

    def set_seed_location(self, seed_location):
        self.seed_location = seed_location

    def apply(self, metric_layer):
        disturbed_layer_int = metric_layer["disturbed"].values.astype(int)
        seed_location_layer = metric_layer["seed"]

        burn_boundary_segmented = flood_fill(
            image=disturbed_layer_int, seed_point=self.seed_location, new_value=0
        )

        return burn_boundary_segmented


def derive_boundary(
    metric_layer,
    seed_locations=None,
    thresholding_strategy=OtsuThreshold(),
    segmentation_strategy=FloodFillSegmentation(),
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

    burn_boundary_raster = thresholding_strategy.apply(metric_layer)

    burn_boundary_raster_postprocessed = postprocess_burn_mask(
        burn_boundary_raster, fill_holes=True, smooth_sigma=1, buffer_iterations=1
    )

    burn_boundary_raster_segmented = segmentation_strategy.apply(
        burn_boundary_raster_postprocessed
    )

    burn_boundary_polygon = raster_mask_to_geojson(burn_boundary_raster_segmented)

    return burn_boundary_polygon


def postprocess_burn_mask(
    burn_mask, fill_holes=False, smooth_sigma=None, buffer_iterations=None
):
    burn_mask_values = burn_mask.values

    # Fill holes in the burn mask
    if fill_holes:
        burn_mask_values = binary_fill_holes(burn_mask_values)

    # Smooth the boundary, removing small artifacts
    if smooth_sigma:
        burn_mask_values = gaussian_filter(burn_mask_values, sigma=smooth_sigma)

    # Buffer the boundary to ensure it is continuous
    if buffer_iterations:
        burn_mask_values = binary_dilation(
            burn_mask_values, iterations=buffer_iterations
        )

    burn_mask.values = burn_mask_values
    return burn_mask
