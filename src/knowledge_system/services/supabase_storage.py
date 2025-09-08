"""
Supabase Storage Service for uploading files explicitly selected by the user.

This service intentionally performs no automatic uploads. It is used by the
Cloud Uploads GUI tab to push selected local files to Supabase Storage.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ..config import get_settings
from ..logger import get_logger
from ..utils.optional_deps import add_vendor_to_sys_path, ensure_module

logger = get_logger(__name__)


class SupabaseStorageService:
    """Wrapper around Supabase Storage client with safe optional dependency.

    Notes:
    - Reads credentials from settings if not provided explicitly.
    - Does not perform any background or automatic uploads.
    """

    def __init__(
        self,
        supabase_url: str | None = None,
        supabase_key: str | None = None,
        bucket: str | None = None,
        client: object | None = None,
    ) -> None:
        settings = get_settings()

        # Accept modern structured config if present; otherwise fall back to legacy roots
        url = supabase_url
        key = supabase_key
        bkt = bucket

        # Try nested cloud config first
        try:
            cloud = getattr(settings, "cloud", None)
            if cloud is not None:
                url = url or getattr(cloud, "supabase_url", None)
                key = key or getattr(cloud, "supabase_key", None)
                bkt = bkt or getattr(cloud, "supabase_bucket", None)
        except Exception:
            pass

        # Fallback to legacy flat attributes if they exist
        url = url or getattr(settings.cloud, "supabase_url", None)
        key = key or getattr(settings.cloud, "supabase_key", None)
        bkt = bkt or getattr(settings.cloud, "supabase_bucket", None)

        self.supabase_url: str | None = url
        self.supabase_key: str | None = key
        self.bucket: str | None = bkt
        self.client = None

        if client is not None:
            self.client = client
        else:
            if not self.supabase_url or not self.supabase_key:
                logger.info("Supabase credentials not configured; storage disabled")
                return

            try:
                add_vendor_to_sys_path()
                supabase_mod = ensure_module("supabase", "supabase")
                create_client = getattr(supabase_mod, "create_client")
                self.client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                logger.warning(f"Supabase storage client unavailable: {e}")
                self.client = None

    def is_configured(self) -> bool:
        """Return True if storage client and bucket are ready."""
        return self.client is not None and bool(self.bucket)

    def upload_file(
        self,
        local_path: str | Path,
        destination_path: str | None = None,
        *,
        upsert: bool = True,
        bucket: str | None = None,
        subfolder: str | None = None,
    ) -> tuple[bool, str]:
        """Upload a single file to Supabase Storage.

        Returns (success, message).
        """
        effective_bucket = bucket or self.bucket

        if self.client is None or not effective_bucket:
            return False, "Supabase storage is not configured"

        path = Path(local_path)
        if not path.exists() or not path.is_file():
            return False, f"File not found: {path}"

        # Compute destination path if not provided. Try to preserve relative path under output dir.
        dest_path = destination_path
        if not dest_path:
            try:
                out_dir = Path(
                    getattr(get_settings().paths, "output_dir", "") or ""
                ).expanduser()
                if out_dir and out_dir.exists():
                    dest_path = str(path.relative_to(out_dir))
                else:
                    dest_path = path.name
            except Exception:
                dest_path = path.name

        if subfolder:
            prefix = subfolder.strip().strip("/\\")
            if prefix:
                dest_path = f"{prefix}/{dest_path}"

        content_type, _ = mimetypes.guess_type(path.name)
        # Some client versions require header values to be strings
        file_options = {"upsert": "true" if upsert else "false"}
        if content_type:
            file_options["content-type"] = content_type

        try:
            with open(path, "rb") as f:
                # Supabase-py v2: storage.from_(bucket).upload(file=f, path=dest, file_options={...})
                response = self.client.storage.from_(
                    effective_bucket
                ).upload(  # type: ignore[attr-defined]
                    file=f, path=dest_path, file_options=file_options
                )
            # Some client versions return dict-like; accept as success if no exception
            return True, f"Uploaded to {self.bucket}/{dest_path}"
        except Exception as e:
            logger.error(f"Failed to upload {path}: {e}")
            return False, str(e)
