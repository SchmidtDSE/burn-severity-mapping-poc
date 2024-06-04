import xarray as xr
from scipy.ndimage import binary_fill_holes, gaussian_filter, binary_dilation
from skimage.filters import threshold_otsu
from skimage.segmentation import flood_fill
from ..util.raster_to_poly import raster_mask_to_geojson
from abc import ABC, abstractmethod


## THRESHOLDING STRATEGIES
class ThresholdingStrategy(ABC):
    @abstractmethod
    def apply(self, metrics_layer):
        pass


class OtsuThreshold(ThresholdingStrategy):
    def apply(self, metrics_layer):
        threshold = threshold_otsu(metrics_layer)
        burn_mask = metrics_layer.where(metrics_layer >= threshold, 1, 0)
        return burn_mask


class SimpleThreshold(ThresholdingStrategy):
    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def apply(self, metrics_layer):
        burn_mask = metrics_layer.where(metrics_layer >= self.threshold, 1, 0)
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
    metrics_layer,
    thresholding_strategy=OtsuThreshold(),
    segmentation_strategy=FloodFillSegmentation(),
):

    burn_boundary_raster = thresholding_strategy.apply(metrics_layer)

    burn_boundary_raster_postprocessed = postprocess_burn_mask(
        burn_boundary_raster, fill_holes=True, smooth=True, buffer=True
    )

    burn_boundary_raster_segmented = segmentation_strategy.apply(
        burn_boundary_raster_postprocessed
    )

    burn_boundary_polygon = raster_mask_to_geojson(burn_boundary_raster_segmented)

    return burn_boundary_polygon


def postprocess_burn_mask(burn_mask, fill_holes=True, smooth=True, buffer=True):
    # Fill holes in the burn mask
    if fill_holes:
        burn_mask = binary_fill_holes(burn_mask)

    # Smooth the boundary, removing small artifacts
    if smooth:
        burn_mask = gaussian_filter(burn_mask, sigma=1)

    # Buffer the boundary to ensure it is continuous
    if buffer:
        burn_mask = binary_dilation(burn_mask, iterations=1)

    return burn_mask
