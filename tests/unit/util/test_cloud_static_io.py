import pytest
from src.util.cloud_static_io import CloudStaticIOClient, BUCKET_HTTPS_PREFIX
from unittest.mock import patch, MagicMock, ANY, call, mock_open
from boto3.session import Session


@patch("src.util.cloud_static_io.CloudStaticIOClient.update_manifest")
@patch("src.util.cloud_static_io.CloudStaticIOClient.upload_cogs")
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_upload_fire_event(
    mock_init, mock_upload_cogs, mock_update_manifest, test_3d_valid_xarray_epsg_4326
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_fire_event
    metrics_stack = test_3d_valid_xarray_epsg_4326
    metrics_stack = metrics_stack.rename({"band": "burn_metric"})
    metrics_stack["burn_metric"] = ["rbr", "dnbr"]

    fire_event_name = "test_event"
    prefire_date_range = "test_prefire_range"
    postfire_date_range = "test_postfire_range"
    affiliation = "test_affiliation"
    derive_boundary = "test_boundary"
    satellite_pass_information = {
        "n_prefire_passes": 4,
        "n_postfire_passes": 4,
        "latest_pass": "2021-01-01",
    }

    # Call upload_fire_event
    client.upload_fire_event(
        metrics_stack,
        fire_event_name,
        prefire_date_range,
        postfire_date_range,
        affiliation,
        derive_boundary,
        satellite_pass_information=satellite_pass_information,
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
        satellite_pass_information=satellite_pass_information,
    )


@patch("rioxarray.raster_array.RasterArray.to_raster")
@patch("rasterio.open")
@patch.object(CloudStaticIOClient, "upload", return_value=None)
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_upload_cogs(
    mock_init,
    mock_upload,
    mock_rio_open,
    mock_to_raster,
    test_3d_valid_xarray_epsg_4326,
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_cogs
    fire_event_name = "test_event"
    affiliation = "test_affiliation"

    # Give xarray the `burn_metric` band, with rbr and dnbr as values in `burn_metric`
    test_3d_valid_xarray_epsg_4326 = test_3d_valid_xarray_epsg_4326.rename(
        {"band": "burn_metric"}
    )
    test_3d_valid_xarray_epsg_4326["burn_metric"] = ["rbr", "dnbr"]

    # Call upload_cogs
    client.upload_cogs(
        test_3d_valid_xarray_epsg_4326,
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
    test_3d_valid_xarray_epsg_4326,
):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the arguments for upload_rap_estimates
    fire_event_name = "test_event"
    affiliation = "test_affiliation"

    # Give xarray the `band` band, with some band names as values in `band`
    test_3d_valid_xarray_epsg_4326["band"] = ["tree", "shrub"]

    # Call upload_rap_estimates
    client.upload_rap_estimates(
        test_3d_valid_xarray_epsg_4326,
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
@patch("builtins.open", new_callable=mock_open)
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
    satellite_pass_information = {
        "n_prefire_passes": 4,
        "n_postfire_passes": 4,
        "latest_pass": "2021-01-01",
    }

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
        satellite_pass_information,
    )

    # Assert that __init__, get_manifest, json.dump and upload were called with the correct arguments
    mock_init.assert_called_once_with()
    mock_get_manifest.assert_called_once_with()
    mock_json_dump.assert_called_once()
    mock_upload.assert_called_once_with(
        source_local_path=mock_os_join.return_value,
        remote_path="manifest.json",
    )


@patch("json.load")
@patch.object(CloudStaticIOClient, "download", return_value=None)
@patch("builtins.open", new_callable=mock_open)
@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_get_manifest(mock_init, mock_open, mock_download, mock_json_load):
    # Create an instance of CloudStaticIOClient
    client = CloudStaticIOClient()

    # Mock the logger
    client.logger = MagicMock()

    # Define the return value for json.load
    mock_json_load.return_value = {"key": "value"}

    # Call get_manifest
    result = client.get_manifest()

    # Assert that __init__, download and json.load were called with the correct arguments
    mock_init.assert_called_once_with()
    mock_download.assert_called_once()
    mock_json_load.assert_called_once()

    # Assert that the result is as expected
    assert result == {"key": "value"}


@patch.object(CloudStaticIOClient, "__init__", return_value=None)
def test_get_derived_products(mock_init):
    # Define test affiliation and fire event name
    affiliation = "test_affiliation"
    fire_event_name = "test_event"
    s3_bucket_name = "test_bucket"
    # Define test pages
    test_pages = [
        {
            "Contents": [
                {"Key": f"public/{affiliation}/{fire_event_name}/test_file1.tif"}
            ]
        },
        {
            "Contents": [
                {"Key": f"public/{affiliation}/{fire_event_name}/test_file2.tif"}
            ]
        },
    ]

    # Mock s3 client and paginator
    mock_s3_client = MagicMock()
    mock_paginator = MagicMock()

    # Mock boto_session and its client method
    mock_boto_session = MagicMock()
    mock_boto_session.client.return_value = mock_s3_client
    mock_paginator.paginate.return_value = test_pages
    mock_s3_client.get_paginator.return_value = mock_paginator

    # Create an instance of CloudStaticIOClient, and give it an s3 client
    client = CloudStaticIOClient()
    client.s3_bucket_name = s3_bucket_name
    client.https_prefix = BUCKET_HTTPS_PREFIX.format(
        s3_bucket_name=client.s3_bucket_name
    )
    client.boto_session = mock_boto_session

    # Call get_derived_products
    derived_products = client.get_derived_products(affiliation, fire_event_name)

    # Assert that boto_session.client was called with "s3"
    mock_boto_session.client.assert_called_once_with("s3")

    # Assert that get_paginator was called with "list_objects_v2"
    mock_s3_client.get_paginator.assert_called_once_with("list_objects_v2")

    # Assert that paginate was called with the correct Bucket and Prefix
    mock_paginator.paginate.assert_called_once_with(
        Bucket=client.s3_bucket_name, Prefix=f"public/{affiliation}/{fire_event_name}/"
    )

    # Assert that the returned derived products match the expected derived products
    expected_derived_products = {
        "test_file1.tif": client.https_prefix
        + "/public/test_affiliation/test_event/test_file1.tif",
        "test_file2.tif": client.https_prefix
        + "/public/test_affiliation/test_event/test_file2.tif",
    }

    assert derived_products == expected_derived_products
