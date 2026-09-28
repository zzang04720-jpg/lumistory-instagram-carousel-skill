"""Publish a reviewed LumiStory carousel with the existing Instagram setup.

This is deliberately separate from image creation: ``stage_manifest`` uploads
and creates a private Instagram container; ``publish_manifest`` makes it public.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from lumistory_cards import BASE_DIR, SITE
from publish_pipeline import (
    create_carousel_container,
    create_item_container,
    ensure_config,
    find_recent_duplicate_publish,
    publish_container,
    sign_cloudinary_upload,
)


def load_manifest(path: str | Path) -> tuple[Path, dict]:
    manifest_path = Path(path).resolve()
    if not manifest_path.is_file() or manifest_path.name != "manifest.json":
        raise ValueError("검토용 manifest.json 파일을 선택해 주세요.")
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"카드뉴스 정보를 읽을 수 없습니다: {exc}") from exc
    if data.get("schema") != 1 or not isinstance(data.get("article"), dict):
        raise ValueError("지원하지 않는 카드뉴스 정보입니다.")
    if not str(data["article"].get("url", "")).startswith(SITE + "/skills/"):
        raise ValueError("루미스토리 스킬 글에서 만든 카드뉴스만 발행할 수 있습니다.")
    if data.get("status") not in {"preview", "staged", "published"}:
        raise ValueError("올바른 미리보기/발행 상태가 아닙니다.")
    images = [Path(value).resolve() for value in data.get("images", [])]
    if not 3 <= len(images) <= 10 or any(not image.is_file() for image in images):
        raise ValueError("발행할 PNG 카드가 3~10장 모두 준비되어 있어야 합니다.")
    caption = str(data.get("caption", "")).strip()
    if len(caption) < 40:
        raise ValueError("캡션이 비어 있거나 너무 짧아서 발행할 수 없습니다.")
    return manifest_path, data


def stage_manifest(path: str | Path) -> dict:
    """Upload approved preview images and make an unpublished carousel container."""
    manifest_path, data = load_manifest(path)
    if data.get("status") == "published":
        raise ValueError("이미 발행 기록이 있는 카드뉴스입니다.")
    if data.get("status") == "staged":
        return data
    if find_recent_duplicate_publish(data["caption"]):
        raise ValueError("최근 24시간 안에 같은 내용이 이미 발행되어 중단했습니다.")
    ensure_config()
    image_paths = [Path(value).resolve() for value in data["images"]]
    urls = [sign_cloudinary_upload(image) for image in image_paths]
    # Cloudinary can return a public URL a few seconds before Instagram's
    # downloader can fetch that same new derivative. Waiting and retrying here
    # avoids a partial carousel failing on an otherwise valid PNG.
    time.sleep(12)
    item_ids = []
    for position, url in enumerate(urls, 1):
        last_error: Exception | None = None
        for attempt in range(1, 5):
            try:
                item_ids.append(create_item_container(url))
                break
            except Exception as exc:
                last_error = exc
                if attempt < 4:
                    time.sleep(10 * attempt)
        else:
            raise RuntimeError(f"{position}번 카드의 인스타그램 준비에 실패했습니다: {last_error}") from last_error
    carousel_id = create_carousel_container(item_ids, data["caption"])
    data.update({
        "status": "staged",
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "cloudinary_urls": urls,
        "item_ids": item_ids,
        "carousel_id": carousel_id,
    })
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def publish_manifest(path: str | Path) -> str:
    """Make the staged carousel public and append the normal duplicate-protection log."""
    manifest_path, data = load_manifest(path)
    if data.get("status") == "published":
        return str(data.get("permalink") or data.get("published_post_id"))
    if data.get("status") != "staged" or not data.get("carousel_id"):
        raise ValueError("먼저 카드와 캡션을 검토한 뒤 발행 준비를 해야 합니다.")
    post_id = publish_container(str(data["carousel_id"]), caption=data["caption"])
    # A permalink lookup failure must not turn a successful public post into a
    # failed operation, so its ID remains the canonical record.
    permalink = ""
    try:
        from publish_pipeline import GRAPH_VERSION, IG_ACCESS_TOKEN
        response = requests.get(
            f"https://graph.instagram.com/{GRAPH_VERSION}/{post_id}",
            params={"fields": "permalink", "access_token": IG_ACCESS_TOKEN}, timeout=30,
        )
        if response.status_code == 200:
            permalink = str(response.json().get("permalink", ""))
    except Exception:
        pass
    data.update({
        "status": "published",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "published_post_id": post_id,
        "permalink": permalink,
    })
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log_path = BASE_DIR / "published_log.json"
    try:
        history = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
        if not isinstance(history, list):
            history = []
    except (ValueError, OSError):
        history = []
    history.append({
        "created_at": data["published_at"],
        "title": data["article"]["title"],
        "source_url": data["article"]["url"],
        "caption": data["caption"],
        "slides": data["images"],
        "cloudinary_urls": data.get("cloudinary_urls", []),
        "item_ids": data.get("item_ids", []),
        "carousel_id": data["carousel_id"],
        "published_post_id": post_id,
        "permalink": permalink,
    })
    log_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    return post_id
