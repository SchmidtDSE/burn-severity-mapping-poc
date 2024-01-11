import requests
import geopandas as gpd
import json

SDM_ENDPOINT = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"

def create_aoi_query(geojson):
    aoi = geojson['features'][0]['geometry']

    create_aoi_data = {
        "SERVICE": "aoi",
        "REQUEST": "create",
        "AOICOORDS": json.dumps(aoi)  
    }

    response = requests.post(SDM_ENDPOINT, data=create_aoi_data)

    return response