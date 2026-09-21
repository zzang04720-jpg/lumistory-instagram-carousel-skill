import os
import sys
import time
import hashlib
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")

if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    print("ERROR: Missing Cloudinary config in .env.")
    print("Required: CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET")
    sys.exit(1)

if not all([IG_USER_ID, IG_ACCESS_TOKEN]):
    print("ERROR: Missing Instagram config in .env.")
    print("Required: IG_USER_ID, IG_ACCESS_TOKEN")
    sys.exit(1)


def upload_to_cloudinary(file_path: str | Path) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    timestamp = str(int(time.time()))
    public_id = f"test_upload_{timestamp}_{path.stem}"
    params = {
        "timestamp": timestamp,
        "api_key": CLOUDINARY_API_KEY,
        "public_id": public_id,
    }

    signature_payload = f"public_id={public_id}&timestamp={timestamp}{CLOUDINARY_API_SECRET}"
    signature = hashlib.sha1(signature_payload.encode("utf-8")).hexdigest()
    params["signature"] = signature

    with open(path, "rb") as f:
        files = {"file": f}
        response = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
            data=params,
            files=files,
            timeout=60,
        )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.status_code != 200:
        msg = payload.get("error", {}).get("message") or payload.get("message") or payload.get("raw") or response.text
        raise RuntimeError(f"Cloudinary upload failed: {msg}")

    url = payload.get("secure_url") or payload.get("url")
    if not url:
        raise RuntimeError(f"Cloudinary response missing secure_url: {payload}")

    return url


def get_instagram_media_status(media_id: str) -> dict:
    url = f"https://graph.instagram.com/{GRAPH_VERSION}/{media_id}"
    params = {"fields": "status_code", "access_token": IG_ACCESS_TOKEN}
    response = requests.get(url, params=params, timeout=60)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.status_code != 200:
        raise RuntimeError(
            payload.get("error", {}).get("message")
            or payload.get("message")
            or payload.get("raw")
            or response.text
        )

    return payload


def publish_instagram_media(creation_id: str) -> dict:
    url = f"https://graph.instagram.com/{GRAPH_VERSION}/{IG_USER_ID}/media_publish"
    data = {"creation_id": creation_id, "access_token": IG_ACCESS_TOKEN}
    response = requests.post(url, data=data, timeout=60)
    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.status_code != 200:
        raise RuntimeError(
            payload.get("error", {}).get("message")
            or payload.get("message")
            or payload.get("raw")
            or response.text
        )

    return payload


if __name__ == "__main__":
    default_image = Path(__file__).resolve().parent / "skills" / "ig-carousel-publish" / "assets" / "cover-dark.html"
    fallback_image = Path(__file__).resolve().parent / "avatar.jpg"
    image_file = fallback_image if fallback_image.exists() else default_image

    print(f"Attempting upload for: {image_file}")
    try:
        url = upload_to_cloudinary(image_file)
        print("SUCCESS: uploaded image URL")
        print(url)
    except Exception as exc:
        print("ERROR: Cloudinary upload failed")
        print(type(exc).__name__ + ": " + str(exc))
        sys.exit(1)

    media_id = "18093363215184570"
    print(f"Checking Instagram media status for: {media_id}")
    try:
        status = get_instagram_media_status(media_id)
        print("STATUS_RESPONSE:")
        print(status)
        if status.get("status_code") == "FINISHED":
            print("Publishing media...")
            result = publish_instagram_media(media_id)
            print("PUBLISH_RESPONSE:")
            print(result)
        else:
            print(f"Media is not finished yet. status_code={status.get('status_code')}")
    except Exception as exc:
        print("ERROR: Instagram status/publish failed")
        print(type(exc).__name__ + ": " + str(exc))
        sys.exit(1)
