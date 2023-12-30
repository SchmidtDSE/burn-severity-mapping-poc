from titiler.core.algorithm import BaseAlgorithm
from titiler.core.algorithm import algorithms as default_algorithms
from rio_tiler.models import ImageData
import numpy as np

class Classify(BaseAlgorithm):
    
    # Parameters
    thresholds: dict # There is no default, which means calls to this algorithm without any parameter will fail

    # We don't set any metadata for this Algorithm

    def __call__(self, img: ImageData) -> ImageData:
        # Convert image data to entirely 100s
        # convert thresholds keys to float
        float_thresholds = {float(k):v for k,v in self.thresholds.items()}

        checks = [img.data < float(threshold) for threshold in float_thresholds]

        values = list(float_thresholds.values())

        classified = np.select(checks, values, default=0).astype(np.uint8)

        # Create output ImageData
        return ImageData(
            classified,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )

algorithms = default_algorithms.register(
    {
        "classify": Classify,
    }
)