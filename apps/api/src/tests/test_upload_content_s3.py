import pytest
from unittest.mock import patch, MagicMock, mock_open
import os
from src.services.utils.upload_content import upload_content

@pytest.mark.asyncio
async def test_upload_content_s3api_behavior():
    # Mock config
    with patch("src.services.utils.upload_content.get_learnhouse_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.hosting_config.content_delivery.type = "s3api"
        mock_config.hosting_config.content_delivery.s3api.endpoint_url = "http://localhost:9000"
        mock_config.hosting_config.content_delivery.s3api.bucket_name = "test-bucket"
        mock_get_config.return_value = mock_config

        # Mock boto3
        with patch("src.services.utils.upload_content.boto3") as mock_boto3:
            mock_s3 = MagicMock()
            mock_boto3.client.return_value = mock_s3

            # Mock built-in open to track file writes
            m_open = mock_open()

            # Use os.path.exists and os.makedirs mocking to avoid actual filesystem changes
            with patch("os.path.exists", return_value=False), \
                 patch("os.makedirs") as mock_makedirs, \
                 patch("builtins.open", m_open):

                # Call the function
                await upload_content(
                    directory="logos",
                    type_of_dir="orgs",
                    uuid="test-uuid",
                    file_binary=b"test-content",
                    file_and_format="test.jpg"
                )

                # Assertions for NEW behavior

                # 1. Verify boto3 client creation
                mock_boto3.client.assert_called_with(
                    "s3",
                    endpoint_url="http://localhost:9000"
                )

                # 2. Verify local file write did NOT happen
                assert not m_open.called, "Local file should not be opened/written"

                # 3. Verify makedirs not called
                assert not mock_makedirs.called, "os.makedirs should not be called for S3"

                # 4. Verify s3 put_object called (New implementation uses put_object)
                mock_s3.put_object.assert_called_with(
                    Bucket="test-bucket",
                    Key="content/orgs/test-uuid/logos/test.jpg",
                    Body=b"test-content",
                    ContentType="image/jpg"
                )

                # 5. Verify head_object checks the correct bucket
                mock_s3.head_object.assert_called_with(
                    Bucket="test-bucket",
                    Key="content/orgs/test-uuid/logos/test.jpg"
                )

@pytest.mark.asyncio
async def test_upload_content_filesystem_behavior():
    # Mock config
    with patch("src.services.utils.upload_content.get_learnhouse_config") as mock_get_config:
        mock_config = MagicMock()
        mock_config.hosting_config.content_delivery.type = "filesystem"
        mock_get_config.return_value = mock_config

        # Mock boto3 - should NOT be called
        with patch("src.services.utils.upload_content.boto3") as mock_boto3:

            # Mock built-in open to track file writes
            m_open = mock_open()

            # Use os.path.exists and os.makedirs mocking
            with patch("os.path.exists", return_value=False), \
                 patch("os.makedirs") as mock_makedirs, \
                 patch("builtins.open", m_open):

                # Call the function
                await upload_content(
                    directory="logos",
                    type_of_dir="orgs",
                    uuid="test-uuid",
                    file_binary=b"test-content",
                    file_and_format="test.jpg"
                )

                # Assertions

                # 1. Verify boto3 NOT called
                assert not mock_boto3.called

                # 2. Verify directory creation
                mock_makedirs.assert_called_with("content/orgs/test-uuid/logos")

                # 3. Verify local file write happened
                m_open.assert_called_with("content/orgs/test-uuid/logos/test.jpg", "wb")
                m_open().write.assert_called_with(b"test-content")
