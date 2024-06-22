import zipfile
import geopandas as gpd
import rioxarray as rxr
import os
import tempfile
import zipfile


def ingest_esri_zip_file(zip_file_path):
    """
    Ingests an ESRI zip file containing shapefiles and tif files. This assumes that there are a set of
    shapefiles and tif files in the zip file. The shapefiles are expected to be in the form of a .shp, .shx, and .prj file,
    with a .dbf file being optional.

    Args:
        zip_file_path (str): The path to the ESRI zip file.

    Returns:
        tuple: A tuple containing two lists - valid_shapefiles and valid_tifs.
            - valid_shapefiles: A list of tuples, where each tuple contains the paths to the valid shapefiles and their corresponding GeoJSON representation.
            - valid_tifs: A list of valid tif files.

    """
    valid_shapefiles = []
    valid_tifs = []

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        for file_name in zip_ref.namelist():
            if file_name.endswith(".shp"):
                # Create a temporary directory
                with tempfile.TemporaryDirectory() as tmp_dir:
                    # Extract the related files to the temporary directory
                    shp_base = os.path.splitext(file_name)[0]
                    for ext in [".shp", ".shx", ".dbf", ".prj"]:
                        zip_ref.extract(shp_base + ext, path=tmp_dir)

                    print("Found shapefile: {}".format(file_name))

                    # Check if all required files exist
                    if all(
                        os.path.exists(os.path.join(tmp_dir, shp_base + ext))
                        for ext in [".shp", ".shx", ".prj"]
                    ):
                        # Read the shapefile from the temporary directory
                        valid_shapefile = (
                            os.path.join(tmp_dir, shp_base + ".shp"),
                            os.path.join(tmp_dir, shp_base + ".shx"),
                            os.path.join(tmp_dir, shp_base + ".prj"),
                        )

                        # If .dbf file exists, add it to the tuple
                        if os.path.exists(os.path.join(tmp_dir, shp_base + ".dbf")):
                            valid_shapefile += (
                                os.path.join(tmp_dir, shp_base + ".dbf"),
                            )

                        shp_geojson = shp_to_geojson(valid_shapefile[0])

                        valid_shapefiles.append((valid_shapefile, shp_geojson))

                    else:
                        print(
                            "Shapefile {} is missing required files (shp, shx, and proj).".format(
                                file_name
                            )
                        )

            if file_name.endswith(".tif"):
                print("Found tif file: {}".format(file_name))
                # Create a temporary directory
                with tempfile.TemporaryDirectory() as tmp_dir:
                    # Extract the related files to the temporary directory
                    tif_base = os.path.splitext(file_name)[0]
                    zip_ref.extract(tif_base + ".tif", path=tmp_dir)

                    # Read the shapefile from the temporary directory
                    valid_tif = rxr.open_rasterio(os.path.join(tmp_dir, file_name))

                    valid_tifs.append(valid_tif)

    return valid_shapefiles, valid_tifs


def shp_to_geojson(shp_file_path):
    """
    Convert a shapefile to GeoJSON format, assuming we know the CRS
    of the shapefile based on its helper files.

    Args:
        shp_file_path (str): The file path of the shapefile.

    Returns:
        str: The GeoJSON representation of the shapefile.
    """
    gdf = gpd.read_file(shp_file_path).to_crs("EPSG:4326")
    return gdf.to_json()