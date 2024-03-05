from fastapi import Depends, APIRouter, HTTPException
from logging import Logger
from typing import Any
from pydantic import BaseModel
import tempfile
import sentry_sdk
import json
import pandas as pd

from ..dependencies import get_cloud_logger, get_cloud_static_io_client, init_sentry
from src.lib.query_soil import (
    sdm_get_esa_mapunitid_poly,
    sdm_get_ecoclassid_from_mu_info,
    edit_get_ecoclass_info,
)
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()


class FetchEcoclassPOSTBody(BaseModel):
    """
    Represents the request body for querying soil data.

    Attributes:
        geojson (str): The GeoJSON data.
        fire_event_name (str): The name of the fire event.
        affiliation (str): The affiliation of the user.
    """

    geojson: Any
    fire_event_name: str
    affiliation: str


@router.post(
    "/api/fetch/ecoclass",
    tags=["fetch"],
    description="Fetch ecoclass data (using Soil Data Mart / Web Soil Survey for Map Unit polygons, and the Ecological Site Description database for ecoclass info)",
)
def fetch_ecoclass(
    body: FetchEcoclassPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger),
):
    """
    Fetches ecoclass information from EDIT based on the provided parameters.

    Args:
        body (QuerySoilPOSTBody): The request body containing the necessary parameters.
        cloud_static_io_client (CloudStaticIOClient, optional): The client for interacting with the cloud storage service. FastAPI handles this as a dependency injection.
        __sentry (None, optional): Sentry client, just needs to be initialized. FastAPI handles this as a dependency injection.
        logger (Logger, optional): Google cloud logger. FastAPI handles this as a dependency injection.

    Returns:
        tuple: A tuple containing the success message and the HTTP status code.
    """
    fire_event_name = body.fire_event_name
    geojson_boundary = json.loads(body.geojson)
    affiliation = body.affiliation

    sentry_sdk.set_context("analyze_ecoclass", {"request": body})

    main(
        fire_event_name=fire_event_name,
        geojson_boundary=geojson_boundary,
        affiliation=affiliation,
        cloud_static_io_client=cloud_static_io_client,
        logger=logger,
    )


def main(
    fire_event_name, geojson_boundary, affiliation, cloud_static_io_client, logger
):
    try:

        mapunit_gdf = sdm_get_esa_mapunitid_poly(geojson_boundary)
        mu_polygon_keys = [
            mupolygonkey
            for __musym, __nationalmusym, __mukey, mupolygonkey in mapunit_gdf.index
        ]
        mrla_df = sdm_get_ecoclassid_from_mu_info(mu_polygon_keys)

        # join mapunitids with link table for ecoclassids
        mapunit_with_ecoclassid_df = mapunit_gdf.join(mrla_df).set_index("ecoclassid")

        edit_ecoclass_df_row_dicts = []
        ecoclass_ids = mrla_df["ecoclassid"].unique()

        n_ecoclasses = len(ecoclass_ids)
        n_within_edit = 0

        for ecoclass_id in ecoclass_ids:
            edit_ecoclass_json = edit_get_ecoclass_info(ecoclass_id)
            if edit_ecoclass_json:
                n_within_edit += 1
                logger.info(f"Success: {ecoclass_id} exists within EDIT backend")
                edit_ecoclass_df_row_dict = edit_ecoclass_json["generalInformation"][
                    "dominantSpecies"
                ]
                edit_ecoclass_df_row_dict["ecoclassid"] = ecoclass_id
                edit_ecoclass_df_row_dicts.append(edit_ecoclass_df_row_dict)
            else:
                logger.info(
                    f"Missing: {edit_ecoclass_json} doesn't exist within EDIT backend"
                )

        logger.info(
            f"Found {n_within_edit} of {n_ecoclasses} ecoclasses ({100*round(n_within_edit/n_ecoclasses, 2)}%) within EDIT backend"
        )

        if n_within_edit > 0:
            edit_ecoclass_df = pd.DataFrame(edit_ecoclass_df_row_dicts).set_index(
                "ecoclassid"
            )
        else:
            # Populate with empty dataframe, for consistency's sake (so that the frontend doesn't have to handle this case)
            edit_ecoclass_df = pd.DataFrame(
                [],
                columns=[
                    "dominantTree1",
                    "dominantShrub1",
                    "dominantHerb1",
                    "dominantTree2",
                    "dominantShrub2",
                    "dominantHerb2",
                ],
            )

        # join ecoclassids with edit ecoclass info, to get spatial ecoclass info
        edit_ecoclass_geojson = mapunit_with_ecoclassid_df.join(
            edit_ecoclass_df, how="left"
        ).to_json()

        # save the ecoclass_geojson to the FTP server
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmp_geojson_path = tmp.name
            with open(tmp_geojson_path, "w") as f:
                f.write(edit_ecoclass_geojson)

            cloud_static_io_client.upload(
                source_local_path=tmp_geojson_path,
                remote_path=f"public/{affiliation}/{fire_event_name}/ecoclass_dominant_cover.geojson",
            )

        logger.info(f"Ecoclass GeoJSON uploaded for {fire_event_name}")
        return f"Ecoclass GeoJSON uploaded for {fire_event_name}", 200

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
