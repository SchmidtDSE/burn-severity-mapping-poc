from titiler.core.algorithm import BaseAlgorithm
from titiler.core.algorithm import algorithms as default_algorithms
from rio_tiler.models import ImageData
import numpy as np

class Classify(BaseAlgorithm):
    
    # Parameters
    thresholds: dict # There is no default, which means calls to this algorithm without any parameter will fail

    def __call__(self, img: ImageData) -> ImageData:

        float_thresholds = {float(k):v for k,v in self.thresholds.items()}

        checks = [img.data < float(threshold) for threshold in float_thresholds]
        values = list(float_thresholds.values())
        classified = np.select(checks, values, default=0).astype(np.uint8)

        # Generate mask where classified is not 0 
        mask = classified != 0

        # Squeeze 1-length dim
        classified_squeezed = np.squeeze(classified)

        # Convert classified_squeezed to a MaskedArray
        final_img = np.ma.MaskedArray(classified_squeezed, mask=mask)

        # Create output ImageData
        return ImageData(
            final_img,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )



algorithms = default_algorithms.register(
    {
        "classify": Classify,
    }
)