from typing import Literal, Optional
import aiofiles
import aioboto3
from botocore.exceptions import ClientError
import os
from fastapi import HTTPException, UploadFile
from config.config import get_learnhouse_config
from src.security.file_validation import validate_upload


def ensure_directory_exists(directory: str):
    if not os.path.exists(directory):
        os.makedirs(directory)


async def upload_file(
    file: UploadFile,
    directory: str,
    type_of_dir: Literal["orgs", "users"],
    uuid: str,
    allowed_types: list[str],
    filename_prefix: str,
    max_size: Optional[int] = None,
) -> str:
    """
    Secure file upload with validation.
    
    Args:
        file: The uploaded file
        directory: Target directory (e.g., "logos", "avatars")
        type_of_dir: "orgs" or "users"
        uuid: Organization or user UUID
        allowed_types: List of allowed file types ('image', 'video', 'document')
        filename_prefix: Prefix for the generated filename
        max_size: Maximum file size in bytes (optional)
        
    Returns:
        The saved filename
    """
    from uuid import uuid4
    from src.security.file_validation import get_safe_filename
    
    # Validate the file
    _, content = validate_upload(file, allowed_types, max_size)
    
    # Generate safe filename
    filename = get_safe_filename(file.filename, f"{uuid4()}_{filename_prefix}")
    
    # Save the file
    await upload_content(
        directory=directory,
        type_of_dir=type_of_dir,
        uuid=uuid,
        file_binary=content,
        file_and_format=filename,
        allowed_formats=None,  # Already validated
    )
    
    return filename


async def upload_content(
    directory: str,
    type_of_dir: Literal["orgs", "users"],
    uuid: str,  # org_uuid or user_uuid
    file_binary: bytes,
    file_and_format: str,
    allowed_formats: Optional[list[str]] = None,
):
    # Get Learnhouse Config
    learnhouse_config = get_learnhouse_config()

    file_format = file_and_format.split(".")[-1].strip().lower()

    # Get content delivery method
    content_delivery = learnhouse_config.hosting_config.content_delivery.type

    # Check if format file is allowed
    if allowed_formats:
        if file_format not in allowed_formats:
            raise HTTPException(
                status_code=400,
                detail=f"File format {file_format} not allowed",
            )

    if content_delivery == "filesystem":
        ensure_directory_exists(f"content/{type_of_dir}/{uuid}/{directory}")
        # upload file to server
        async with aiofiles.open(
            f"content/{type_of_dir}/{uuid}/{directory}/{file_and_format}",
            "wb",
        ) as f:
            await f.write(file_binary)

    elif content_delivery == "s3api":
        # Upload directly to s3 (AWS Keys are stored in environment variables and are loaded by boto3)
        print("Uploading to s3...")
        async with aioboto3.Session().client(
            "s3",
            endpoint_url=learnhouse_config.hosting_config.content_delivery.s3api.endpoint_url,
        ) as s3:
            bucket_name = learnhouse_config.hosting_config.content_delivery.s3api.bucket_name or "learnhouse-media"
            file_path = f"content/{type_of_dir}/{uuid}/{directory}/{file_and_format}"

            print("Uploading to s3 using boto3...")
            try:
                await s3.put_object(
                    Bucket=bucket_name,
                    Key=file_path,
                    Body=file_binary,
                    ContentType=f"image/{file_format}" if file_format in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "application/octet-stream"
                )
            except ClientError as e:
                print(e)

            print("Checking if file exists in s3...")
            try:
                await s3.head_object(
                    Bucket=bucket_name,
                    Key=file_path,
                )
                print("File upload successful!")
            except Exception as e:
                print(f"An error occurred: {str(e)}")
