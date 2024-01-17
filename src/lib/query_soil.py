import requests
from requests import ConnectionError
import geopandas as gpd
import pandas as pd
import json
from shapely.geometry import shape
from shapely.ops import transform
import xml.etree.ElementTree as ET
import tempfile
import urllib
from shapely.ops import transform

SDM_ENDPOINT_TABULAR = "https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest"
SDM_ENDPOINT_SPATIAL = "https://SDMDataAccess.sc.egov.usda.gov/Spatial/SDMWGS84Geographic.wfs"
EDIT_ECOCLASS_ENDPOINT = "https://edit.jornada.nmsu.edu/services/descriptions"

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
def sdm_get_esa_mapunitid_poly(geojson, backoff_max = 200, backoff_value = 0, backoff_increment = 25):

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

                mapunit_gdf = gpd.read_file(tmp.name)
                mapunit_gdf.set_crs(epsg=4326, inplace=True)

                # Swap x and y coordinates, as GML2 is lon, lat and everything else is lat, lon
                mapunit_gdf.geometry = mapunit_gdf.geometry.map(lambda polygon: transform(lambda x, y: (y, x), polygon))

                # Set composite key
                mapunit_gdf['musym'] = mapunit_gdf['musym'].astype(str)
                mapunit_gdf['nationalmusym'] = mapunit_gdf['nationalmusym'].astype(str)
                mapunit_gdf['mukey'] = mapunit_gdf['mukey'].astype(str)
                mapunit_gdf.set_index(['musym', 'nationalmusym', 'mukey'], inplace=True)

                return mapunit_gdf

        elif response.status_code == 400:
            print("Error:", response.status_code)
            return None
    except ConnectionError as e:
        # TODO: Remove this if we end up using cloud tasks' backoff
        print("SMD Refused Traffic:", str(e))
        print(f"Backoff: {backoff_value}")
        if backoff_value < backoff_max:
            backoff_value += backoff_increment
            return sdm_get_esa_mapunitid_poly(geojson, backoff_value=backoff_value)
        else:
            raise Exception("SDM Refused Traffic. Backoff max reached.")
    except Exception as e:
        print("Error:", str(e))
        return None

def sdm_get_ecoclassid_from_mu_info(mu_polygon_keys):
    SQL_QUERY = """
        SELECT DISTINCT
            ecoclassid,
            ecoclassname,
            muname,
            mu.mukey,
            mup.mupolygonkey,
            mu.musym,
            mu.nationalmusym
        FROM legend
        INNER JOIN laoverlap AS lao ON legend.lkey = lao.lkey
        INNER JOIN muaoverlap AS mua ON mua.lareaovkey = lao.lareaovkey
        INNER JOIN mapunit AS mu ON mu.mukey = mua.mukey
        INNER JOIN mupolygon AS mup ON mu.mukey = mup.mukey AND mup.mupolygonkey IN ({})
        INNER JOIN component c ON c.mukey = mu.mukey AND compkind = 'series'
        INNER JOIN coecoclass ON c.cokey = coecoclass.cokey AND coecoclass.ecoclassref = 'Ecological Site Description Database'
        GROUP BY ecoclassid, ecoclassname, muname, mu.mukey, mup.mupolygonkey, mu.musym, mu.nationalmusym, legend.areasymbol, legend.areaname
    """
    # mu_pairs = [mu_info.mu_pair for mu_info in mu_info_list]

    # TODO: Hacky SQL 98 solution to lack of tuples (should revist)
    # conditions = ' OR '.join("(musym = {} AND nationalmusym = '{}')".format(nationalmusym, musym) for nationalmusym, musym in mu_info_list)
    # query = SQL_QUERY.format(conditions)
    in_mu_polygon_keys_list = ','.join([str(key) for key in mu_polygon_keys])
    query = SQL_QUERY.format(in_mu_polygon_keys_list)
    query = ' '.join(query.split())  # remove newlines and extra spaces
    query = urllib.parse.quote_plus(query)

    data = f"QUERY={query}&FORMAT=json%2Bcolumnname"

    response = requests.post(SDM_ENDPOINT_TABULAR, data=data)

    if response.status_code == 200:
        mu_info_json = json.loads(response.content)['Table']
        mu_info_df = pd.DataFrame(mu_info_json)
        mu_info_df.columns = mu_info_df.iloc[0]
        mu_info_df = mu_info_df[1:]
        mu_info_df = mu_info_df.reset_index(drop=True)

        mu_info_df['mukey'] = mu_info_df['mukey'].astype(str)
        mu_info_df['musym'] = mu_info_df['musym'].astype(str)
        mu_info_df['nationalmusym'] = mu_info_df['nationalmusym'].astype(str)
        mu_info_df.set_index(['musym', 'nationalmusym', 'mukey'], inplace=True)

        return mu_info_df
    else:
        raise Exception(f"Error in SDM: {response.status_code}, {response.content}")
    
def edit_get_ecoclass_info(ecoclass_id):
    try:
        geoUnit = ecoclass_id[1:5]
        edit_endpoint_fmt = EDIT_ECOCLASS_ENDPOINT + f"/esd/{geoUnit}/{ecoclass_id}.json"

        response = requests.get(edit_endpoint_fmt)

        if response.status_code == 200:
            edit_json = json.loads(response.content)

            # Add hyperlink to EDIT human readable page
            edit_json['hyperlink'] = f"https://edit.jornada.nmsu.edu/catalogs/esd/{geoUnit}/{ecoclass_id}"

            return True, edit_json
        elif response.status_code == 404:
            print(f"EcoClass ID not found within EDIT database:, {ecoclass_id}")
            return False, {"error": f"EcoClass ID not found within EDIT database: {ecoclass_id}"}
        else:
            print("Error:", response.status_code)
            raise Exception(f"Error in EDIT: {response.status_code}, {response.content}")

    except Exception as e:
        print("Error:", str(e))
        return None