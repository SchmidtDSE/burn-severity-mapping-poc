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
    edit_get_ecoclass_info
)
from src.util.cloud_static_io import CloudStaticIOClient

router = APIRouter()

class QuerySoilPOSTBody(BaseModel):
    geojson: Any
    fire_event_name: str
    affiliation: str

@router.post("/api/fetch/fetch-ecoclass")
def analyze_ecoclass(
    body: QuerySoilPOSTBody,
    cloud_static_io_client: CloudStaticIOClient = Depends(get_cloud_static_io_client),
    __sentry: None = Depends(init_sentry),
    logger: Logger = Depends(get_cloud_logger)
):
    fire_event_name = body.fire_event_name
    geojson = json.loads(body.geojson)
    affiliation = body.affiliation

    sentry_sdk.set_context("analyze_ecoclass", {"request": body})

    try:
            
        mapunit_gdf = sdm_get_esa_mapunitid_poly(geojson)
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
            edit_success, edit_ecoclass_json = edit_get_ecoclass_info(ecoclass_id)
            if edit_success:
                n_within_edit += 1
                logger.log_text(f"Success: {ecoclass_id} exists within EDIT backend")
                edit_ecoclass_df_row_dict = edit_ecoclass_json["generalInformation"][
                    "dominantSpecies"
                ]
                edit_ecoclass_df_row_dict["ecoclassid"] = ecoclass_id
                edit_ecoclass_df_row_dicts.append(edit_ecoclass_df_row_dict)
            else:
                logger.log_text(
                    f"Missing: {edit_ecoclass_json} doesn't exist within EDIT backend"
                )

        logger.log_text(
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

        logger.log_text(f"Ecoclass GeoJSON uploaded for {fire_event_name}")
        return f"Ecoclass GeoJSON uploaded for {fire_event_name}", 200

    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.log_text(f"Error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
