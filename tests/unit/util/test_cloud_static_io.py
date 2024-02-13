import pytest
from src.util.cloud_static_io import CloudStaticIOClient
from unittest.mock import patch, MagicMock, ANY


@patch("src.util.cloud_static_io.CloudStaticIOClient.update_manifest")
@patch("src.util.cloud_static_io.CloudStaticIOClient.upload_cogs")
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_upload_fire_event(mock_init, mock_upload_cogs, mock_update_manifest):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_fire_event
    metrics_stack = MagicMock()
    fire_event_name = "test_event"
    prefire_date_range = "test_prefire_range"
    postfire_date_range = "test_postfire_range"
    affiliation = "test_affiliation"
    derive_boundary = "test_boundary"

    # Call upload_fire_event
    client.upload_fire_event(
        metrics_stack,
        fire_event_name,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
    )

    # Assert that upload_cogs and update_manifest were called with the correct arguments
    mock_upload_cogs.assert_called_once_with(
        metrics_stack=metrics_stack,
        fire_event_name=fire_event_name,
        affiliation=affiliation,
    )
    mock_update_manifest.assert_called_once_with(
        fire_event_name=fire_event_name,
        bounds=ANY,
        prefire_date_range=prefire_date_range,
        postfire_date_range=postfire_date_range,
        affiliation=affiliation,
        derive_boundary=derive_boundary,
    )
