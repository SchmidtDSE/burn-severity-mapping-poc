from titiler.core.algorithm import BaseAlgorithm
from titiler.core.algorithm import algorithms as default_algorithms
from rio_tiler.models import ImageData

class Multiply(BaseAlgorithm):

    # Parameters
    factor: int # There is no default, which means calls to this algorithm without any parameter will fail

    # We don't set any metadata for this Algorithm

    def __call__(self, img: ImageData) -> ImageData:
        # Convert image data to entirely 100s
        data = np.full_like(img.data, 100)
        print("Converting image data to entirely 100s")

        # Create output ImageData
        return ImageData(
            data,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )

algorithms = default_algorithms.register(
    {
        "multiply": Multiply,
    }
)