import logging
from pathlib import Path

from google.cloud import storage

from exception import VoiceNotFound

logger = logging.getLogger(__name__)


class GcloudStorage:
    def __init__(self, api_key, options):
        self._enable = options["enable"]
        self._bucket_name = options["name"]
        self._delete = options["delete"]

        if self._enable:
            self.client = storage.Client.from_service_account_json(api_key)
            self.bucket = self.client.bucket(self._bucket_name)

    def __bool__(self):
        return self._enable

    def get_uri(self, blob_name: str) -> str:
        if not blob_name:
            raise ValueError("Blob name can not be empty.")

        uri = "gs://" + self._bucket_name + "/" + blob_name
        return uri

    def upload(self, filepath: str) -> str:
        if not self.bucket:
            raise ValueError("Not configure Gcloud Storage Bucket yet.")

        file = Path(filepath)
        if not file.exists():
            raise VoiceNotFound(f"Path: {filepath}")
        blob_name = file.name

        blob = self.bucket.blob(blob_name)
        blob.upload_from_filename(filepath)

        return blob_name

    def delete(self, blob_name: str) -> None:
        if not self.bucket:
            raise ValueError("Not configure Gcloud Storage Bucket yet.")
        if not blob_name:
            raise ValueError("Blob name can not be empty.")

        if not self._delete:
            return None

        blob = self.bucket.blob(blob_name)
        blob.delete()
