# from flask import Flask, request
from fastapi import FastAPI, Depends, HTTPException
from titiler.core.dependencies import TileParams
from src.lib.query_sentinel import Sentinel2Client
from src.util.sftp import SFTPClient
from src.util.aws_secrets import get_ssh_secret
from titiler.core import factory
from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers

from pydantic import BaseModel

# app = Flask(__name__)
app = FastAPI()
cog = factory.TilerFactory()
app.include_router(cog.router, prefix="/cog", tags=["Cloud Optimized GeoTIFF"])
add_exception_handlers(app, DEFAULT_STATUS_CODES)

# create an SFTP client instance
SFTP_HOSTNAME = "s-90987336df8a4faca.server.transfer.us-east-2.amazonaws.com"
SFTP_USERNAME = "sftp-admin"
sftp_client = SFTPClient(SFTP_HOSTNAME, SFTP_USERNAME, get_ssh_secret())


@app.get("/")
def index():
    return "Hello World! We have some burn data in here.", 200


# create a POST endpoint for running a burn query with an input geojson, with its associated POST body class
class AnaylzeBurnPOSTBody(BaseModel):
    geojson: dict
    date_ranges: dict
    fire_event_name: str


@app.post("/analyze-burn")
def analyze_burn(body: AnaylzeBurnPOSTBody):
    geojson = body.geojson
    date_ranges = body.date_ranges
    fire_event_name = body.fire_event_name

    try:
        # create a Sentinel2Client instance
        geo_client = Sentinel2Client(geojson_bounds=geojson, buffer=0.1)

        # get imagery data before and after the fire
        geo_client.query_fire_event(
            prefire_date_range=date_ranges["prefire"],
            postfire_date_range=date_ranges["postfire"],
            from_bbox=True,
        )

        # calculate burn metrics
        geo_client.calc_burn_metrics()

        # save the cog to the FTP server
        sftp_client.connect()
        sftp_client.upload_cog(
            metrics_stack=geo_client.metrics_stack, fire_event_name=fire_event_name
        )
        sftp_client.disconnect()

        return f"cog uploaded for {fire_event_name}", 200

    except Exception as e:
        return f"Error: {e}", 400


@app.get("/polygon/{fire_event_name}/tiles/{z}/{x}/{y}")
def read_polygon(fire_event_name: str, z: int, x: int, y: int):
    try:
        # Fetch the COG file URL corresponding to the given polygon
        cog_url = sftp_client.available_cogs[fire_event_name]
    except KeyError:
        raise HTTPException(status_code=404, detail="Fire event not found")

    # Pass all request parameters along to the COG Tiler
    return cog.tile(cog_url, z, x, y)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
