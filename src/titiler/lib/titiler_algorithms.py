from titiler.core.algorithm import BaseAlgorithm
from titiler.core.algorithm import algorithms as default_algorithms
from rio_tiler.models import ImageData
import numpy as np


def convert_to_rgb(classified: np.ndarray, mask: np.ndarray, color: str) -> np.ndarray:
    """
    Convert a classified image to RGB format, essentially creating a false-color image. This is used
    extensively by Titiler to create the final image that is returned to the user, upon a tile request.
    We will likely do this on the front-end in v1.

    Args:
        classified (np.ndarray): The classified image.
        mask (np.ndarray): The mask indicating which pixels to include in the final image.
        color (str): The color to use for the RGB image. Must be one of "red", "green", or "blue".

    Returns:
        np.ndarray: The RGB image.

    Raises:
        ValueError: If an invalid color is provided.
    """
    if color == "red":
        r_channel = np.full_like(classified, 255)
        classified_rgb = np.stack([r_channel, classified, classified], axis=0)
    elif color == "green":
        g_channel = np.full_like(classified, 255)
        classified_rgb = np.stack([classified, g_channel, classified], axis=0)
    elif color == "blue":
        b_channel = np.full_like(classified, 255)
        classified_rgb = np.stack([classified, classified, b_channel], axis=0)
    else:
        raise ValueError(f"Invalid color: {color}")

    rgb_mask = np.stack([mask, mask, mask], axis=0).squeeze()

    final_img = np.ma.MaskedArray(classified_rgb, mask=rgb_mask)
    return final_img


class Classify(BaseAlgorithm):
    thresholds: dict  # There is no default, which means calls to this algorithm without any parameter will fail
    color: str = "red"  # Default to red

    def __call__(self, img: ImageData) -> ImageData:
        """
        Apply classification algorithm to the input image. Essentially, this converts floats to
        integers based on a set of thresholds, input by the GET request for a tile.

        Args:
            img (ImageData): Input image data.

        Returns:
            ImageData: Classified image data.
        """
        float_burn_data = img.data.squeeze()
        float_thresholds = {float(k): v for k, v in self.thresholds.items()}
        png_int_values = list(float_thresholds.values())

        threshold_checks = [
            float_burn_data < float(threshold) for threshold in float_thresholds
        ]
        mask = (np.isnan(float_burn_data)) | (float_burn_data == -99)

        classified = np.select(threshold_checks, png_int_values).astype(np.uint8)

        final_img = convert_to_rgb(classified, mask, self.color)

        # Create output ImageData
        return ImageData(
            final_img,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )


class CensorAndScale(BaseAlgorithm):
    thresholds: dict
    color: str = "red"

    def __call__(self, img: ImageData) -> ImageData:
        """
        Algorithm for censoring and scaling image data. Everything between the min and max thresholds
        will be scaled to 0-255, while everything below the min threshold will be set to 255 and everything
        above the max threshold will be set to 0.

        Args:
            thresholds (dict): Dictionary containing the minimum and maximum threshold values.
            color (str, optional): Color to use for censoring. Defaults to "red".

        Returns:
            ImageData: The processed image data.

        """
        scale_min = float(self.thresholds["min"])
        scale_max = float(self.thresholds["max"])

        # Create masks for values below min and above max
        mask_below = img.data < scale_min
        mask_above = img.data > scale_max

        # Create a mask for NaN values or values equal to -99
        mask_transparent = (np.isnan(img.data)) | (img.data == -99)

        # Set values below min to white (255, 255, 255) and above max to red (255, 0, 0)
        img.data[mask_below] = 255
        img.data[mask_above] = 0

        # Scale values between min and max to 255 to 0
        mask_middle = ~mask_below & ~mask_above
        img.data[mask_middle] = (
            255 - ((img.data[mask_middle] - scale_min) / (scale_max - scale_min)) * 255
        )

        # Convert to uint8
        int_data = img.data.astype(np.uint8).squeeze()

        final_img = convert_to_rgb(int_data, mask_transparent, self.color)

        return ImageData(
            final_img,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )


# Register the algorithms with Titiler
algorithms = default_algorithms.register(
    {"classify": Classify, "censor_and_scale": CensorAndScale}
)
