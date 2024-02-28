import pytest
import requests
from unittest.mock import patch, Mock
from src.lib.query_soil import sdm_get_esa_mapunitid_poly, edit_get_ecoclass_info
from shapely.geometry import Polygon
import geopandas as gpd
import json


@patch("requests.get")
def test_sdm_get_esa_mapunitid_poly_success(
    mock_get, test_geojson, test_sdm_get_esa_mapunitid_poly_response
):
    # Set the mock response
    mock_get.return_value = test_sdm_get_esa_mapunitid_poly_response

    # Call the function
    result = sdm_get_esa_mapunitid_poly(test_geojson)

    # Add assertions to check the result
    assert result is not None
    assert isinstance(result, gpd.GeoDataFrame)


@patch("requests.get")
def test_sdm_get_esa_mapunitid_poly_failure(mock_get, test_geojson):
    # Define the mock response
    mock_response = Mock()
    mock_response.status_code = 400

    # Set the mock response
    mock_get.return_value = mock_response

    # Call the function
    result = sdm_get_esa_mapunitid_poly(test_geojson)

    # Add assertions to check the result
    assert result is None


@patch("requests.get")
def test_sdm_get_esa_mapunitid_poly_exception(mock_get, test_geojson):
    # Set the mock to raise an exception
    mock_get.side_effect = requests.exceptions.ConnectionError

    # Call the function and expect an exception
    with pytest.raises(Exception):
        sdm_get_esa_mapunitid_poly(
            test_geojson, backoff_max=2, backoff_increment=1, backoff_value=0
        )


@patch("requests.get")
def test_edit_get_ecoclass_info_success(mock_get):
    # Define the mock response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = json.dumps({"key": "value"})

    # Set the mock response
    mock_get.return_value = mock_response

    # Call the function
    result = edit_get_ecoclass_info("E1234")

    # Add assertions to check the result
    assert result is not None
    assert result["key"] == "value"
    assert (
        result["hyperlink"] == "https://edit.jornada.nmsu.edu/catalogs/esd/1234/E1234"
    )


@patch("requests.get")
def test_edit_get_ecoclass_info_not_found(mock_get):
    # Define the mock response
    mock_response = Mock()
    mock_response.status_code = 404

    # Set the mock response
    mock_get.return_value = mock_response

    # Call the function
    result = edit_get_ecoclass_info("E1234")

    # Add assertions to check the result
    assert result is None


@patch("requests.get")
def test_edit_get_ecoclass_info_failure(mock_get):
    # Define the mock response
    mock_response = Mock()
    mock_response.status_code = 500

    # Set the mock response
    mock_get.return_value = mock_response

    # Call the function and expect an exception
    with pytest.raises(Exception):
        edit_get_ecoclass_info("E1234")


@patch("requests.get")
def test_edit_get_ecoclass_info_exception(mock_get):
    # Set the mock to raise an exception
    mock_get.side_effect = requests.exceptions.ConnectionError

    # Call the function and expect an exception
    with pytest.raises(Exception):
        edit_get_ecoclass_info("E1234")
