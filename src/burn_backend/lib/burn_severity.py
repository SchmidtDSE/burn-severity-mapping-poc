import numpy as np
import xarray as xr
import pandas as pd


def calc_nbr(band_nir, band_swir):
    """
    Get the Normalized Burn Ratio (NBR) from the input arrays of NIR and SWIR bands.

    Args:
        band_nir (xr.DataArray): Array of the first band image (e.g., B8A).
        band_swir (xr.DataArray): Array of the second band image (e.g., B12).

    Returns:
        array: Normalized Burn Ratio (NBR).
    """
    nbr = (band_nir - band_swir) / (band_nir + band_swir)
    return nbr


def calc_dnbr(nbr_prefire, nbr_postfire):
    """
    Get the difference Normalized Burn Ratio (dNBR) from the pre-fire and post-fire NBR.

    Args:
        nbr_prefire (xr.DataArray): Pre-fire NBR.
        nbr_postfire (xr.DataArray): Post-fire NBR.

    Returns:
        array: Difference Normalized Burn Ratio (dNBR).
    """
    dnbr = nbr_prefire - nbr_postfire
    return dnbr


def calc_rdnbr(dnbr, nbr_prefire):
    """
    Get the relative difference Normalized Burn Ratio (rdNBR) from the dNBR and pre-fire NBR.

    Args:
        dnbr (xr.DataArray): Difference Normalized Burn Ratio (dNBR).
        nbr_prefire (xr.DataArray): Pre-fire NBR.

    Returns:
        array: Relative difference Normalized Burn Ratio (rdNBR).
    """
    rdnbr = dnbr / np.abs(np.sqrt(nbr_prefire))
    return rdnbr


def calc_rbr(dnbr, nbr_prefire):
    """
    Get the relative burn ratio (rBR) from the dNBR and pre-fire NBR.

    Args:
        dnbr (xr.DataArray): Difference Normalized Burn Ratio (dNBR).
        nbr_prefire (xr.DataArray): Pre-fire NBR.

    Returns:
        array: Relative burn ratio (rBR).
    """
    rbr = dnbr / (nbr_prefire + 1.001)
    return rbr


def calc_burn_metrics(prefire_nir, prefire_swir, postfire_nir, postfire_swir):
    """
    Get the NBR, dNBR, rdNBR, and rBR from the pre- and post-fire NIR and SWIR bands.

    Args:
        prefire_nir (xr.DataArray): Pre-fire NIR.
        prefire_swir (xr.DataArray): Pre-fire SWIR.
        postfire_nir (xr.DataArray): Post-fire NIR.
        postfire_swir (xr.DataArray): Post-fire SWIR.

    Returns:
        xr.DataArray: Stack of NBR, dNBR, rdNBR, and rBR.
    """
    nbr_prefire = calc_nbr(prefire_nir, prefire_swir)
    nbr_postfire = calc_nbr(postfire_nir, postfire_swir)
    dnbr = calc_dnbr(nbr_prefire, nbr_postfire)
    rdnbr = calc_rdnbr(dnbr, nbr_prefire)
    rbr = calc_rbr(dnbr, nbr_prefire)

    burn_stack = xr.concat(
        [nbr_prefire, nbr_postfire, dnbr, rdnbr, rbr],
        pd.Index(
            ["nbr_prefire", "nbr_postfire", "dnbr", "rdnbr", "rbr"], name="burn_metric"
        ),
        coords="minimal",
    )

    return burn_stack


def classify_burn(array, thresholds):
    """
    Reclassify an array based on the given thresholds.

    Args:
        array (xr.DataArray): Input array.
        thresholds (dict): Dictionary of thresholds and their corresponding values.

    Returns:
        xr.DataArray: Reclassified array.
    """
    reclass = xr.full_like(array, np.nan)

    for threshold, value in sorted(thresholds.items()):
        reclass = xr.where((array < threshold) & (reclass.isnull()), value, reclass)

    return reclass
