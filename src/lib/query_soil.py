import requests
import geopandas as gpd
import json
from shapely.geometry import shape
from shapely.ops import transform
import xml.etree.ElementTree as ET
import tempfile
from osgeo import ogr

SDM_ENDPOINT_TABULAR = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"
SDM_ENDPOINT_SPATIAL = "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs"

def sdm_create_aoi(geojson):
    try:
        aoi = geojson['features'][0]['geometry']

        create_aoi_data = {
            "SERVICE": "aoi",
            "REQUEST": "create",
            "AOICOORDS": json.dumps(aoi)  
        }

        response = requests.post(SDM_ENDPOINT_TABULAR, data=create_aoi_data)

        return response

    except Exception as e:
        print("Error:", str(e))
        return None

def sdm_get_available_interpretations(aoi_smd_id):
    try:
        get_available_interpretations_data = {
            "SERVICE": "interpretation",
            "REQUEST": "getcatalog",
            "AOIID": aoi_smd_id  
        }

        response = requests.post(SDM_ENDPOINT_TABULAR, data=get_available_interpretations_data)

        # Check status and print available interpretations
        if response.status_code == 200:
            available_interpretations = response.json()
            print(available_interpretations)
            return available_interpretations

        else: 
            print("Error:", response.status_code)
            return None

    except Exception as e:
        print("Error:", str(e))
        return None

# def sdm_get_esa_mapunitid_poly(aoi_smd_id):
def sdm_get_esa_mapunitid_poly(geojson):

    geometry = geojson['features'][0]['geometry']
    shapely_geom = shape(geometry)
    bounds = shapely_geom.bounds

    bottom_left = f"{bounds[0]},{bounds[1]}"
    top_right = f"{bounds[2]},{bounds[3]}"

    # # format the filter as GML2 / XML
    # filter_GML2_fmt = f"<Filter><BBOX><PropertyName>Geometry</PropertyName><Box srsName='EPSG:4326'><coordinates>{bottom_left} {top_right}</coordinates></Box></BBOX></Filter>"
    filter_fmt = ET.Element('Filter')
    bbox = ET.SubElement(filter_fmt, 'BBOX')
    prop_name = ET.SubElement(bbox, 'PropertyName')
    prop_name.text = 'Geometry'
    box = ET.SubElement(bbox, 'Box', {'srsName': 'EPSG:4326'})
    coordinates = ET.SubElement(box, 'coordinates')
    coordinates.text = f'{bottom_left} {top_right}'

    filter_GML2_fmt = ET.tostring(filter_fmt, encoding='unicode')

    try:
        get_esa_mapunitid_poly_data = {
            'SERVICE': 'WFS',
            'VERSION': '1.1.0',
            'REQUEST': 'GetFeature',
            'TYPENAME': 'mapunitpoly',
            'FILTER': filter_GML2_fmt,
            'SRSNAME': 'EPSG:4326',
            'OUTPUTFORMAT': 'GML2'
        }

        response = requests.get(SDM_ENDPOINT_SPATIAL, params=get_esa_mapunitid_poly_data)

        if response.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix='.gml') as tmp:
                tmp.write(response.content)
                tmp.seek(0)

                # gdf = gpd.read_file(tmp.name)
                # # GML is in lon/lat, so we need to transform to lat/lon
                # gdf['geometry'] = gdf['geometry'].apply(lambda geom: transform(lambda x, y: (y, x), geom))

                gdf = gml_to_gpd(tmp.name)

                mapunitpoly_geojson = gdf.to_json()
                return mapunitpoly_geojson
        elif response.status_code == 400:
            print("Error:", response.status_code)
            return None

    except Exception as e:
        print("Error:", str(e))
        return None

def gml_to_gpd(gml_file):
    gml = ogr.Open(gml_file)
    layer = gml.GetLayer(0)

    # Get the features and create a list to put geometries
    features=[]
    for i in range(0,layer.GetFeatureCount()):
        feature = layer.GetFeature(i)
        geom = feature.GetGeometryRef()
        features.append(wkt.loads(geom.ExportToWkt()))

    # convert this list into a geopandas dataframe  
    gdf = gpd.GeoDataFrame(geometry=features)