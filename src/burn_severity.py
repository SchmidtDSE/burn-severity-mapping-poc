import os
from osgeo import osr
from osgeo import ogr
from osgeo import gdal
import numpy as np
import boto3
from botocore.exceptions import NoCredentialsError
from botocore.handlers import disable_signing
import requests
import matplotlib
import matplotlib.pyplot as plt
import rasterio
from rasterio.merge import merge
import glob
from rasterio.mask import mask
from shapely.geometry import mapping
import geopandas as gpd
import math
import xarray as xr
import rioxarray as rxr
import pandas as pd

os.environ["AWS_NO_SIGN_REQUEST"] = "YES" # to avoid signing requests, avoid AWS auth

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
    burn_stack = xr.concat(
        [nbr_prefire, nbr_postfire, dnbr, rdnbr, rbr],
        pd.Index(['nbr_prefire', 'nbr_postfire', 'dnbr', 'rdnbr', 'rbr'], name='burn_metric')
    )

    return burn_stack

def reclassify(array, thresholds):
    """
    This function reclassifies an array
    input:  array           xarray.DataArray    input array
    output: reclass         xarray.DataArray    reclassified array
    """
    
    reclass = xr.full_like(array, np.nan)

    for threshold, value in sorted(thresholds.items()):
        reclass = xr.where((array < threshold) & (reclass.isnull()), value, reclass)
    
    return reclass

def is_s3_url_valid(url):
    """
    This function checks if an S3 URL is valid
    """
    s3 = boto3.client('s3')
    s3.meta.events.register('choose-signer.s3.*', disable_signing)

    bucket_name = url.split('/')[2]
    key = '/'.join(url.split('/')[3:])
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=key)
        for obj in response.get('Contents', []):
            if obj['Key'] == key:
                return True
        return False
    except NoCredentialsError:
        print("No AWS credentials found")
        return False
    except Exception as e:
        print(f"Invalid S3 URL: {url}. Exception: {str(e)}")
        return False