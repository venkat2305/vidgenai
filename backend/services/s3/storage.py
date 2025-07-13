import logging
import boto3
from botocore.config import Config
import os
from botocore.exceptions import ClientError
from core.config import settings

logger = logging.getLogger("vidgenai.r2_storage")


async def upload_to_r2(file_path: str, object_key: str) -> str:
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")

        r2_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )

        # Log configuration (without sensitive data)
        logger.info(f"Uploading to R2: endpoint={settings.R2_ENDPOINT_URL}, bucket={settings.R2_BUCKET_NAME}")

        r2_client.upload_file(
            file_path,
            settings.R2_BUCKET_NAME,
            object_key,
            ExtraArgs={'ACL': 'public-read'}
        )

        # Generate the URL (Cloudflare R2 URL format)
        url = f"{settings.R2_PUBLIC_URL_BASE}/{object_key}"

        logger.info(f"Uploaded {file_path} to R2: {url}")
        return url

    except ClientError as e:
        logger.error(f"Error uploading to R2: {str(e)}", exc_info=True)
        raise Exception(f"Failed to upload {file_path} to {settings.R2_BUCKET_NAME}/{object_key}: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in upload_to_r2: {str(e)}", exc_info=True)
        raise Exception(f"Failed to upload {file_path} to R2: {str(e)}")


