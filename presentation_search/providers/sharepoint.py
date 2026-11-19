from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from urllib.parse import quote, urlsplit

import httpx

from ..config import Settings
from .base import (
    MAX_FILE_BYTES,
    MAX_LIBRARY_FILES,
    KnowledgeProvider,
    Source,
    SourceFailure,
    SourceTooLargeError,
    write_bounded,
)

GRAPH = "https://graph.microsoft.com/v1.0"


class SharePointKnowledgeProvider(KnowledgeProvider):
    """Read one approved folder as the application, and upload to a separate destination."""

    def __init__(self, settings: Settings):
        self.settings = settings
        required = (
            "azure_tenant_id",
            "azure_client_id",
            "azure_client_secret",
            "sharepoint_drive_id",
            "sharepoint_folder_item_id",
            "sharepoint_output_drive_id",
            "sharepoint_output_folder_item_id",
        )
        missing = [name.upper() for name in required if not getattr(settings, name).strip()]
        if missing:
            raise ValueError("Missing SharePoint configuration: " + ", ".join(missing))
        if (settings.sharepoint_drive_id, settings.sharepoint_folder_item_id) == (
            settings.sharepoint_output_drive_id,
            settings.sharepoint_output_folder_item_id,
        ):
            raise ValueError("SharePoint input and output folders must be distinct")
        self.cache_dir = settings.sharepoint_cache_path

    def _token(self) -> str:
        import msal

        try:
            app = msal.ConfidentialClientApplication(
                self.settings.azure_client_id,
                authority=f"https://login.microsoftonline.com/{self.settings.azure_tenant_id}",
                client_credential=self.settings.azure_client_secret,
                timeout=15,
            )
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        except Exception:
            raise RuntimeError("Microsoft Graph authentication failed") from None
        if not result.get("access_token"):
            raise RuntimeError("Microsoft Graph authentication failed")
        return result["access_token"]

    def _client(self):
        return httpx.Client(timeout=httpx.Timeout(60, connect=10), follow_redirects=False)

    @staticmethod
    def _send(client, method, url, *, token=None, content=None, stream=False):
        # Forward credentials only to Graph. Resolve download redirects without a bearer.
        target = urlsplit(url)
        if target.scheme != "https" or not target.hostname or target.username or target.password:
            raise ValueError("Invalid Microsoft Graph resource URL")
        if token and (target.netloc != "graph.microsoft.com" or not target.path.startswith("/v1.0/")):
            raise ValueError("Untrusted Microsoft Graph pagination URL")
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        if content is not None:
            headers["Content-Type"] = (
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        for attempt in range(3):
            if content is not None:
                content.seek(0)
            request = client.build_request(method, url, headers=headers, content=content)
            response = client.send(request, stream=stream, follow_redirects=False)
            if response.status_code in (429, 502, 503, 504) and attempt < 2:
                retry = response.headers.get("Retry-After", "")
                response.close()
                sleep(min(5, int(retry)) if retry.isdigit() and len(retry) < 5 else 1 + attempt)
                continue
            if response.status_code >= 400:
                response.close()
                raise RuntimeError(f"Microsoft Graph request failed (HTTP {response.status_code})")
            return response
        raise RuntimeError("Microsoft Graph request failed")

    def _items(self, client, token):
        s = self.settings
        drive = quote(s.sharepoint_drive_id, safe="")
        pending = [s.sharepoint_folder_item_id]
        visited = set()
        pages = set()
        count = 0
        while pending:
            folder = pending.pop()
            if folder in visited:
                continue
            visited.add(folder)
            url = f"{GRAPH}/drives/{drive}/items/{quote(folder, safe='')}/children?$select=id,name,webUrl,file,folder,size"
            while url:
                if url in pages or len(pages) >= 10000:
                    raise ValueError("Graph folder traversal exceeded the pilot limits")
                pages.add(url)
                response = self._send(client, "GET", url, token=token)
                response.raise_for_status()
                data = response.json()
                for item in data["value"]:
                    key = item["id"]
                    if "folder" in item:
                        if (
                            key != s.sharepoint_output_folder_item_id
                            or s.sharepoint_drive_id != s.sharepoint_output_drive_id
                        ):
                            pending.append(key)
                    elif (
                        "file" in item
                        and item["name"].lower().endswith(".pptx")
                        and not item["name"].startswith("~$")
                    ):
                        count += 1
                        if count > MAX_LIBRARY_FILES:
                            raise ValueError("Approved library exceeds the pilot file limit")
                        yield item, folder
                url = data.get("@odata.nextLink")

    def _download(self, client, token, item, path):
        if item.get("size", 0) > MAX_FILE_BYTES:
            raise SourceTooLargeError("A source deck exceeds the 64 MiB limit.")
        drive = quote(self.settings.sharepoint_drive_id, safe="")
        url = f"{GRAPH}/drives/{drive}/items/{quote(item['id'], safe='')}/content"
        for _ in range(5):
            response = self._send(client, "GET", url, token=token, stream=True)
            try:
                if response.is_redirect:
                    url = response.headers["location"]
                    token = None
                    continue
                response.raise_for_status()
                write_bounded(path, response.iter_bytes(65536))
                return
            finally:
                response.close()
        raise RuntimeError("Microsoft Graph download exceeded its redirect limit")

    def materialize_presentations(self, keys: set[str] | None = None) -> Iterator[Source | SourceFailure]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        token = self._token()
        with self._client() as client, TemporaryDirectory(dir=self.cache_dir) as scratch:
            path = Path(scratch) / "input.pptx"
            for item, folder in self._items(client, token):
                key = self.settings.sharepoint_drive_id + "/" + item["id"]
                if keys is None or key in keys:
                    try:
                        self._download(client, token, item, path)
                    except SourceTooLargeError as exc:
                        if keys is not None:
                            raise
                        yield SourceFailure(item["name"], str(exc))
                        continue
                    url = item.get("webUrl", "")
                    if not isinstance(url, str) or urlsplit(url).scheme != "https":
                        raise RuntimeError("A SharePoint source is missing its HTTPS web URL")
                    yield Source(path, key, item["name"], url, folder)

    def publish(self, path: Path, filename: str) -> str:
        s = self.settings
        drive = quote(s.sharepoint_output_drive_id, safe="")
        folder = quote(s.sharepoint_output_folder_item_id, safe="")
        url = f"{GRAPH}/drives/{drive}/items/{folder}:/{quote(filename, safe='')}:/content"
        with self._client() as client, path.open("rb") as data:
            response = self._send(client, "PUT", url, token=self._token(), content=data)
            response.raise_for_status()
            web_url = response.json().get("webUrl", "")
        if (
            not isinstance(web_url, str)
            or urlsplit(web_url).scheme != "https"
            or not urlsplit(web_url).hostname
        ):
            raise RuntimeError("Graph did not return an authenticated document URL")
        return web_url
