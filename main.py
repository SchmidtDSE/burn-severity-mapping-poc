from flask import Flask, request, response
from src.query_sentinel import Sentinel2Client

app = Flask(__name__)

@app.route('/')
def index():
    return 'Hello World! We have some burn data in here.', 200

# create a POST endpoint for running a burn query with an input geojson
@app.route('/analyze-burn', methods=['POST'])
def burn():

    # get the geojson from the request body
    body = request.get_json()
    geojson = body['geojson']
    date_ranges = body['date_ranges']
    fire_name = body['fire_name']

    try:
        # create a Sentinel2Client instance
        geo_client = Sentinel2Client(
            geojson_bounds=geojson,
            buffer=0.1
        )

        # get imagery data before and after the fire
        geo_client.query_fire_event(
            prefire_date_range=date_ranges['prefire'],
            postfire_date_range=date_ranges['postfire'],
            from_bbox=True
        )

        # calculate burn metrics
        geo_client.calc_burn_metrics()

        # save the cog to the FTP server
        # geo_client.upload_cog()

        return f"cog uploaded for {fire_name}", 200

    except Exception as e:

        return f"Error: {e}", 400

if __name__ == '__main__':
    app.run(debug=True)