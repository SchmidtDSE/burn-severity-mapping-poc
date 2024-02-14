import pytest
from src.util.cloud_static_io import CloudStaticIOClient
from unittest.mock import patch, MagicMock, ANY, call


@patch("src.util.cloud_static_io.CloudStaticIOClient.update_manifest")
@patch("src.util.cloud_static_io.CloudStaticIOClient.upload_cogs")
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_upload_fire_event(
    mock_init, mock_upload_cogs, mock_update_manifest, test_3d_xarray
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_fire_event
    metrics_stack = test_3d_xarray
    metrics_stack = metrics_stack.rename({"band": "burn_metric"})
    metrics_stack["burn_metric"] = ["rbr", "dnbr"]

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

    # Assert that __init__, upload_cogs and update_manifest were called with the correct arguments
    mock_init.assert_called_once_with()
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


@patch("rioxarray.raster_array.RasterArray.to_raster")
@patch("rasterio.open")
@patch.object(CloudStaticIOClient, "upload", return_value=None)
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_upload_cogs(
    mock_init, mock_upload, mock_rio_open, mock_to_raster, test_3d_xarray
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_cogs
    fire_event_name = "test_event"
    affiliation = "test_affiliation"

    # Give xarray the `burn_metric` band, with rbr and dnbr as values in `burn_metric`
    test_3d_xarray = test_3d_xarray.rename({"band": "burn_metric"})
    test_3d_xarray["burn_metric"] = ["rbr", "dnbr"]

    # Call upload_cogs
    client.upload_cogs(
        test_3d_xarray,
        fire_event_name,
        affiliation,
    )

    mock_init.assert_called_once_with()
    mock_upload.assert_has_calls(
        [
            call(
                source_local_path=ANY,
                remote_path=f"public/{affiliation}/{fire_event_name}/rbr.tif",
            ),
            call(
                source_local_path=ANY,
                remote_path=f"public/{affiliation}/{fire_event_name}/dnbr.tif",
            ),
            call(
                source_local_path=ANY,
                remote_path=f"public/{affiliation}/{fire_event_name}/pct_change_dnbr_rbr.tif",
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("os.path.join")
@patch("rasterio.open")
@patch("rioxarray.raster_array.RasterArray.to_raster")
@patch.object(CloudStaticIOClient, "upload", return_value=None)
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_upload_rap_estimates(
    mock_init,
    mock_upload,
    mock_to_raster,
    mock_rio_open,
    mock_os_join,
    mock_temp_dir,
    test_3d_xarray,
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_rap_estimates
    fire_event_name = "test_event"
    affiliation = "test_affiliation"

    # Give xarray the `band` band, with some band names as values in `band`
    test_3d_xarray["band"] = ["tree", "shrub"]

    # Call upload_rap_estimates
    client.upload_rap_estimates(
        test_3d_xarray,
        fire_event_name,
        affiliation,
    )

    mock_init.assert_called_once_with()
    mock_upload.assert_has_calls(
        [
            call(
                source_local_path=ANY,
                remote_path=f"public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_tree.tif",
            ),
            call(
                source_local_path=ANY,
                remote_path=f"public/{affiliation}/{fire_event_name}/rangeland_analysis_platform_shrub.tif",
            ),
        ]
    )


@patch("tempfile.TemporaryDirectory")
@patch("os.path.join")
@patch("builtins.open", new_callable=MagicMock)
@patch("json.dump")
@patch.object(CloudStaticIOClient, "upload", return_value=None)
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
@patch.object(CloudStaticIOClient, "get_manifest")
def test_update_manifest(
    mock_get_manifest,
    mock_init,
    mock_upload,
    mock_json_dump,
    mock_open,
    mock_os_join,
    mock_temp_dir,
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for update_manifest
    fire_event_name = "test_event"
    bounds = "test_bounds"
    prefire_date_range = "test_prefire_range"
    postfire_date_range = "test_postfire_range"
    affiliation = "test_affiliation"
    derive_boundary = "test_boundary"

    # Mock the return value of get_manifest
    mock_get_manifest.return_value = {}

    # Call update_manifest
    client.update_manifest(
        fire_event_name,
        bounds,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
    )

    # Assert that __init__, get_manifest, json.dump and upload were called with the correct arguments
    mock_init.assert_called_once_with()
    mock_get_manifest.assert_called_once_with()
    mock_json_dump.assert_called_once()
    mock_upload.assert_called_once_with(
        source_local_path=mock_os_join.return_value,
        remote_path="manifest.json",
    )
