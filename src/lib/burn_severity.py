import numpy as np
import xarray as xr
import pandas as pd


def calc_nbr(band_nir, band_swir):
    """
    This function takes an input the arrays of the bands from the read_band_image
    function and returns the Normalized Burn ratio (NBR)
    input:  band_nir   array (n x m)      array of first band image e.g B8A
            band_swir   array (n x m)      array of second band image e.g. B12
    output: nbr     array (n x m)      normalized burn ratio
    """
    nbr = (band_nir - band_swir) / (band_nir + band_swir)
    return nbr


def calc_dnbr(nbr_prefire, nbr_postfire):
    """
    This function takes as input the pre- and post-fire NBR and returns the dNBR
    input:  nbr_prefire     array (n x m)       pre-fire NBR
            nbr_postfire     array (n x m)       post-fire NBR
    output: dnbr     array (n x m)       dNBR
    """
    dnbr = nbr_prefire - nbr_postfire
    return dnbr


def calc_rdnbr(dnbr, nbr_prefire):
    """
    This function takes as input the dNBR and prefire NBR, and returns the relative dNBR
    input:  dnbr     array (n x m)       dNBR
            nbr_prefire     array (n x m)       pre-fire NBR
    output: rdnbr    array (n x m)       relative dNBR
    """
    rdnbr = dnbr / np.abs(np.sqrt(nbr_prefire))
    return rdnbr


def calc_rbr(dnbr, nbr_prefire):
    """
    This function takes as input the dNBR and prefire NBR, and returns the relative burn ratio
    input:  dnbr     array (n x m)       dNBR
            nbr_prefire     array (n x m)       pre-fire NBR
    output: rbr    array (n x m)       relative burn ratio
    """
    rbr = dnbr / (nbr_prefire + 1.001)
    return rbr


def calc_burn_metrics(prefire_nir, prefire_swir, postfire_nir, postfire_swir):
    """
    This function takes as input the pre- and post-fire NIR and SWIR bands and returns the
    NBR, dNBR, rDNBR, and rBR
    input:  prefire_nir     array (n x m)       pre-fire NIR
            prefire_swir     array (n x m)       pre-fire SWIR
            postfire_nir     array (n x m)       post-fire NIR
            postfire_swir     array (n x m)       post-fire SWIR
    output: nbr_prefire     array (n x m)       normalized burn ratio
            nbr_postfire     array (n x m)       normalized burn ratio
            dnbr     array (n x m)       dNBR
            rdnbr    array (n x m)       relative dNBR
            rbr    array (n x m)       relative burn ratio
    """
    nbr_prefire = calc_nbr(prefire_nir, prefire_swir)
    nbr_postfire = calc_nbr(postfire_nir, postfire_swir)
    dnbr = calc_dnbr(nbr_prefire, nbr_postfire)
    rdnbr = calc_rdnbr(dnbr, nbr_prefire)
    rbr = calc_rbr(dnbr, nbr_prefire)

    # stack these arrays together, naming them by their source
    # TODO [#22]: Look into other sources of useful info that come with satellite imagery - cloud cover, defective pixels, etc.
    # Some of these might help us filter out bad data (especially as it relates to cloud occlusion)
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
    This function reclassifies an array
    input:  array           xarray.DataArray    input array
    output: reclass         xarray.DataArray    reclassified array
    """

    reclass = xr.full_like(array, np.nan)

    for threshold, value in sorted(thresholds.items()):
        reclass = xr.where((array < threshold) & (reclass.isnull()), value, reclass)

    return reclass
