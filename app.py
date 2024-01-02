from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
# from pathlib import Path
# import uvicorn
# from pydantic import BaseModel

# from titiler.core.factory import TilerFactory
# from titiler.core.errors import DEFAULT_STATUS_CODES, add_exception_handlers


# from src.lib.query_sentinel import Sentinel2Client
# from src.util.sftp import SFTPClient
# from src.util.aws_secrets import get_ssh_secret
# from src.lib.titiler_algorithms import algorithms

# app = Flask(__name__)
app = FastAPI()
# cog = TilerFactory(process_dependency=algorithms.dependency)
# app.include_router(cog.router, prefix='/cog', tags=["Cloud Optimized GeoTIFF"])
# add_exception_handlers(app, DEFAULT_STATUS_CODES)

# # create an SFTP client instance
# SFTP_HOSTNAME = "s-90987336df8a4faca.server.transfer.us-east-2.amazonaws.com"
# SFTP_USERNAME = "sftp-admin"
# S3_BUCKET_NAME = "burn-severity"
# sftp_client = SFTPClient(SFTP_HOSTNAME, SFTP_USERNAME, get_ssh_secret())

@app.get("/")
def index():
    return "Hello World! We have some burn data in here.", 200

@app.get("/test_aws")
def test_aws():
    try:
        aws_secret = get_ssh_secret()
        return f"Here's some secret: {aws_secret[0:10]}", 200
    except Exception as e:
        return f"Error: {e}", 400

# # create a POST endpoint for running a burn query with an input geojson, with its associated POST body class
# class AnaylzeBurnPOSTBody(BaseModel):
#     geojson: dict
#     date_ranges: dict
#     fire_event_name: str


# @app.post("/analyze-burn")
# def analyze_burn(body: AnaylzeBurnPOSTBody):
#     geojson = body.geojson
#     date_ranges = body.date_ranges
#     fire_event_name = body.fire_event_name

#     try:
#         # create a Sentinel2Client instance
#         geo_client = Sentinel2Client(geojson_bounds=geojson, buffer=0.1)

#         # get imagery data before and after the fire
#         geo_client.query_fire_event(
#             prefire_date_range=date_ranges["prefire"],
#             postfire_date_range=date_ranges["postfire"],
#             from_bbox=True,
#         )

#         # calculate burn metrics
#         geo_client.calc_burn_metrics()

#         # save the cog to the FTP server
#         sftp_client.connect()
#         sftp_client.upload_cogs(
#             metrics_stack=geo_client.metrics_stack, fire_event_name=fire_event_name
#         )
#         sftp_client.disconnect()

#         return f"cog uploaded for {fire_event_name}", 200

#     except Exception as e:
#         return f"Error: {e}", 400

# @app.get("/map/{fire_event_name}", response_class=HTMLResponse)
# def serve_map(fire_event_name: str):
#     html_content = Path("src/index.html").read_text()
#     return html_content