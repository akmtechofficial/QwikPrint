import os
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

class R2StorageManager:
    def __init__(self):
        self.account_id = os.getenv("R2_ACCOUNT_ID", "").strip()
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID", "").strip()
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
        self.bucket_name = os.getenv("R2_BUCKET_NAME", "print-soft").strip()
        
        endpoint = os.getenv("R2_ENDPOINT_URL", "").strip()
        if not endpoint and self.account_id:
            endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
        self.endpoint_url = endpoint

        self.s3_client = None
        self.is_enabled = False
        self._init_client()

    def _init_client(self):
        """Initializes S3 boto3 client for Cloudflare R2 if credentials exist."""
        if self.access_key_id and self.secret_access_key and self.endpoint_url:
            try:
                self.s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    config=Config(signature_version="s3v4"),
                    region_name="auto"
                )
                self.is_enabled = True
                print(f"[Cloudflare R2] Configured successfully for bucket: {self.bucket_name}")
            except Exception as e:
                print(f"[Cloudflare R2 Warning] Failed to initialize client: {e}")
                self.is_enabled = False
        else:
            self.is_enabled = False

    def upload_file(self, local_file_path: str, object_name: str = None) -> tuple[bool, str]:
        """
        Uploads a local file to Cloudflare R2 bucket.
        Returns (success: bool, object_name_or_error: str).
        """
        if not self.is_enabled or not self.s3_client:
            return False, "Cloudflare R2 not enabled"

        if not os.path.exists(local_file_path):
            return False, f"Local file not found: {local_file_path}"

        if not object_name:
            object_name = os.path.basename(local_file_path)

        try:
            # Determine Content-Type
            content_type = "application/octet-stream"
            ext = os.path.splitext(local_file_path)[1].lower()
            if ext == ".pdf":
                content_type = "application/pdf"
            elif ext in (".jpg", ".jpeg"):
                content_type = "image/jpeg"
            elif ext == ".png":
                content_type = "image/png"

            self.s3_client.upload_file(
                local_file_path,
                self.bucket_name,
                object_name,
                ExtraArgs={"ContentType": content_type}
            )
            print(f"[Cloudflare R2] Successfully uploaded '{object_name}' to bucket '{self.bucket_name}'")
            return True, object_name
        except ClientError as e:
            err_msg = str(e)
            print(f"[Cloudflare R2 Error] Upload failed: {err_msg}")
            return False, err_msg
        except Exception as e:
            print(f"[Cloudflare R2 Error] Upload exception: {e}")
            return False, str(e)

    def get_presigned_url(self, object_name: str, expiration: int = 3600) -> str:
        """Generates a pre-signed S3 download URL for an R2 object."""
        if not self.is_enabled or not self.s3_client:
            return ""
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            print(f"[Cloudflare R2 Error] Presigned URL generation failed: {e}")
            return ""

    def object_exists(self, object_name: str) -> bool:
        """Verifies if an object exists in Cloudflare R2 bucket."""
        if not self.is_enabled or not self.s3_client:
            return False
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except Exception:
            return False

    def download_file(self, object_name: str, destination_path: str) -> bool:
        """Downloads an object from Cloudflare R2 to a local destination file path."""
        if not self.is_enabled or not self.s3_client:
            return False
        try:
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            self.s3_client.download_file(self.bucket_name, object_name, destination_path)
            return True
        except Exception as e:
            print(f"[Cloudflare R2 Error] Download object '{object_name}' failed: {e}")
            return False

    def delete_file(self, object_name: str) -> bool:
        """Deletes an object from Cloudflare R2 bucket."""
        if not self.is_enabled or not self.s3_client:
            return False
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=object_name)
            print(f"[Cloudflare R2] Deleted object '{object_name}' from cloud storage")
            return True
        except Exception as e:
            print(f"[Cloudflare R2 Error] Delete object '{object_name}' failed: {e}")
            return False

r2_storage = R2StorageManager()
