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
    def apply(self, metric_values):
        threshold = threshold_otsu(metric_values)
        burn_mask = metric_values.where(metric_values >= threshold, 1, 0)
        return burn_mask


class SimpleThreshold(ThresholdingStrategy):
    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def apply(self, metric_values):
        burn_mask = metric_values.where(metric_values >= self.threshold, 1, 0)
        return burn_mask


## SEGMENTATION STRATEGIES
class SegmentationStrategy(ABC):
    @abstractmethod
    def apply(self, burn_boundary_raster):
        pass


class FloodFillSegmentation(SegmentationStrategy):
    def __init__(self, seed_location):
        self.seed_location = seed_location

    def apply(self, burn_boundary_raster):
        assert self.seed_location.crs == burn_boundary_raster.rio.crs

        burn_boundary_raster_int = burn_boundary_raster.astype(int)
        burn_boundary_segmented = flood_fill(
            burn_boundary_raster_int, self.seed_location
        )

        return burn_boundary_segmented


def derive_boundary(
    metric_layer,
    thresholding_strategy=OtsuThreshold(),
    segmentation_strategy=FloodFillSegmentation(seed_location=(0, 0)),
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
        # information to the final boundary
        metric_values = np.nan_to_num(metric_layer.values, 0)
    else:
        # In this case, we MAY be missing interior unburned islands
        # if we proceed. For now we just want to raise an error, but
        # later we may need to be robust to this
        raise ValueError("NaN values within interior of metric layer")

    burn_boundary_raster = thresholding_strategy.apply(metric_values)

    burn_boundary_raster_postprocessed = postprocess_burn_mask(
        burn_boundary_raster, fill_holes=True, smooth=True, buffer=True
    )

    burn_boundary_raster_segmented = segmentation_strategy.apply(
        burn_boundary_raster_postprocessed
    )

    burn_boundary_polygon = raster_mask_to_geojson(burn_boundary_raster_segmented)

    return burn_boundary_polygon


def postprocess_burn_mask(
    burn_mask, fill_holes=False, smooth_sigma=None, buffer_iterations=None
):
    # Fill holes in the burn mask
    if fill_holes:
        burn_mask = binary_fill_holes(burn_mask)

    # Smooth the boundary, removing small artifacts
    if smooth_sigma:
        burn_mask = gaussian_filter(burn_mask, sigma=smooth_sigma)

    # Buffer the boundary to ensure it is continuous
    if buffer_iterations:
        burn_mask = binary_dilation(burn_mask, iterations=buffer_iterations)

    return burn_mask
