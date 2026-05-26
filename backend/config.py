import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Proxy (optional, set via env var)
HTTP_PROXY = os.environ.get("HTTP_PROXY", "")
HTTPS_PROXY = os.environ.get("HTTPS_PROXY", "")

# Max concurrent downloads
MAX_CONCURRENT_DOWNLOADS = 3
