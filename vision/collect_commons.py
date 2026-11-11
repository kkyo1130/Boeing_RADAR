"""Collect real Boeing 737 cockpit photos from Wikimedia Commons.

Requires internet access on the machine executing this script. Downloads are
NOT OCR training labels: every image must be manually reviewed and annotated.
Only images with supported license metadata are downloaded.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "BoeingRADAR-VisionDataset/0.1 (educational research; contact via GitHub kkyo1130/Boeing_RADAR)"
CATEGORIES = ["Category:Boeing 737 NG cockpits", "Category:Boeing 737 MAX cockpits"]
ALLOWED = ("cc-by-", "cc-by-sa-", "public domain", "cc0", "pd-self")
FIELDS = ["filename", "commons_title", "page_url", "image_url", "author",
          "license", "license_url", "sha256", "width", "height",
          "aircraft_type", "review_status", "altitude", "heading"]

def api_query(params):
    url = API + "?" + urlencode({"format": "json", **params})
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return json.load(response)

def clean(value):
    return re.sub("<[^>]+>", "", html.unescape(value or "")).strip()

def acceptable_license(meta):
    code = clean(meta.get("LicenseShortName", {}).get("value", "")).lower()
    url = meta.get("LicenseUrl", {}).get("value", "")
    if code.startswith(("cc by ", "cc by-sa ", "cc-by-", "cc-by-sa-")) or code in ("cc0", "public domain", "pd-self"):
        return True
    return ("creativecommons.org/licenses/by/" in url or
            "creativecommons.org/licenses/by-sa/" in url or
            "creativecommons.org/publicdomain/" in url)

def collect(output: Path, max_files: int = 30, download: bool = False):
    if max_files < 1:
        raise ValueError("max_files must be positive")
    output.mkdir(parents=True, exist_ok=True)
    images = output / "images"
    if download:
        images.mkdir(exist_ok=True)
    results, seen = [], set()
    for category in CATEGORIES:
        continuation = {}
        while len(results) < max_files:
            query = {
                "action": "query", "generator": "categorymembers",
                "gcmtitle": category, "gcmtype": "file", "gcmlimit": 50,
                "prop": "imageinfo", "iiprop": "url|size|extmetadata",
                "iiurlwidth": 1600, **continuation,
            }
            data = api_query(query)
            for page in data.get("query", {}).get("pages", {}).values():
                if len(results) >= max_files:
                    break
                title = page["title"]
                if title in seen or not page.get("imageinfo"):
                    continue
                seen.add(title)
                info = page["imageinfo"][0]
                meta = info.get("extmetadata", {})
                if not acceptable_license(meta):
                    continue
                source = info.get("thumburl") or info.get("url")
                if not source or not re.search(r"\.(jpg|jpeg|png)(?:\?|$)", source, re.I):
                    # Commons thumbnail URLs may end in /<width>px-<name>.jpg
                    continue
                suffix = ".png" if re.search(r"\.png(?:\?|$)", source, re.I) else ".jpg"
                name = hashlib.sha256(title.encode()).hexdigest()[:16] + suffix
                digest = ""
                if download:
                    request = Request(source, headers={"User-Agent": USER_AGENT})
                    with urlopen(request, timeout=40) as response:
                        blob = response.read(15_000_001)
                    if len(blob) > 15_000_000:
                        continue
                    digest = hashlib.sha256(blob).hexdigest()
                    (images / name).write_bytes(blob)
                    time.sleep(0.3)
                results.append({
                    "filename": "images/" + name if download else "",
                    "commons_title": title,
                    "page_url": "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_"),
                    "image_url": source,
                    "author": clean(meta.get("Artist", {}).get("value", "")),
                    "license": clean(meta.get("LicenseShortName", {}).get("value", "")),
                    "license_url": meta.get("LicenseUrl", {}).get("value", ""),
                    "sha256": digest,
                    "width": info.get("width", ""),
                    "height": info.get("height", ""),
                    "aircraft_type": "B737_MAX" if "MAX" in category else "B737_NG",
                    "review_status": "needs_mcp_review",
                    "altitude": "", "heading": "",
                })
            continuation = data.get("continue", {})
            if not continuation:
                break
        if len(results) >= max_files:
            break
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    print(f"Cataloged {len(results)} license-filtered photos; downloaded={download}.")
    print("IMPORTANT: not yet checked for readable MCP ALT/HDG; no numeric labels assigned.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("vision/data/boeing_737/commons"))
    parser.add_argument("--max-files", type=int, default=30)
    parser.add_argument("--download", action="store_true", help="Download license-filtered images")
    args = parser.parse_args()
    collect(args.output, args.max_files, args.download)
