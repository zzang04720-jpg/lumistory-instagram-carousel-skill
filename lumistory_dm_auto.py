"""Comment-keyword -> private Instagram reply for published LumiStory posts.

This runs from a local scheduled task. It uses the existing Instagram access
token; no customer data or token is printed to the log.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
LOG_PATH = BASE_DIR / "published_log.json"
SENT_PATH = BASE_DIR / "dm_sent_log.json"
load_dotenv(BASE_DIR / ".env")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
IG_USER_ID = os.environ.get("IG_USER_ID", "")
VERSION = os.environ.get("GRAPH_VERSION", "v21.0")
KEYWORD = os.environ.get("IG_DM_KEYWORD", "무료파일").strip().lower()
BASE = f"https://graph.instagram.com/{VERSION}"


def _history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"기록 파일을 읽을 수 없습니다: {path.name}") from exc
    return content if isinstance(content, list) else []


def _write(path: Path, content: list[dict]) -> None:
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def _comment_matches(text: str) -> bool:
    return KEYWORD and KEYWORD.replace(" ", "") in "".join((text or "").lower().split())


def _comments(media_id: str) -> list[dict]:
    response = requests.get(
        f"{BASE}/{media_id}/comments",
        params={"fields": "id,text,timestamp,username", "limit": 100, "access_token": TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("data", []) if isinstance(data, dict) else []


def _send_private_reply(comment_id: str, source_url: str, title: str) -> None:
    # Meta's Instagram Messaging endpoint allows a single private reply to a
    # qualifying comment. The recipient is the comment ID, never a scraped ID.
    message = f"요청하신 무료 가이드예요 🙂\n{title}\n{source_url}"
    response = requests.post(
        f"{BASE}/{IG_USER_ID}/messages",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"recipient": {"comment_id": comment_id}, "message": {"text": message}},
        timeout=30,
    )
    if response.status_code not in (200, 201):
        try:
            detail = response.json()
        except ValueError:
            detail = {"status": response.status_code}
        raise RuntimeError(f"DM 전송 실패: {detail}")


def main() -> None:
    if os.environ.get("IG_AUTO_DM") != "1":
        raise SystemExit("자동 DM 안전장치: IG_AUTO_DM=1 일 때만 실행됩니다.")
    if not TOKEN or not IG_USER_ID:
        raise SystemExit("자동 DM 중단: 인스타그램 환경값이 없습니다.")
    published = [entry for entry in _history(LOG_PATH) if entry.get("source_url") and entry.get("published_post_id")]
    sent = _history(SENT_PATH)
    sent_comment_ids = {str(entry.get("comment_id")) for entry in sent}
    for post in published:
        for comment in _comments(str(post["published_post_id"])):
            comment_id = str(comment.get("id", ""))
            if not comment_id or comment_id in sent_comment_ids or not _comment_matches(str(comment.get("text", ""))):
                continue
            _send_private_reply(comment_id, str(post["source_url"]), str(post.get("title", "루미스토리 무료 가이드")))
            sent.append({
                "comment_id": comment_id,
                "media_id": str(post["published_post_id"]),
                "source_url": str(post["source_url"]),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            _write(SENT_PATH, sent)  # write immediately to prevent duplicate DM after a later failure
            print(f"DM SENT comment={comment_id}")


if __name__ == "__main__":
    main()
