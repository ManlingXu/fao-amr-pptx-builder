"""Serve on loopback without trusting forwarded headers."""
import os
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parents[1])
    uvicorn.run("presentation_search.main:app", host="127.0.0.1", port=8000,
                workers=1, proxy_headers=False)
