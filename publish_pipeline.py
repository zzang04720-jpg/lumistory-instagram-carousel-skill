"""Instagram API helpers only; local preview never imports browser automation."""
import difflib
import hashlib
import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
LOG_PATH = BASE_DIR / "auto_run.log"
IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")


def safe_console_print(text: str):
    try:
        print(str(text))
    except Exception:
        try:
            print(str(text).encode("utf-8", errors="replace").decode("utf-8"))
        except Exception:
            print("[PRINT_ERROR] unable to print message")


def log_line(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    try:
        with LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception as exc:
        safe_console_print(f"[LOG_ERROR] {type(exc).__name__}: {exc}")
    safe_console_print(line)


def ensure_config():
    required = {
        "IG_USER_ID": IG_USER_ID,
        "IG_ACCESS_TOKEN": IG_ACCESS_TOKEN,
        "CLOUDINARY_CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        "CLOUDINARY_API_KEY": CLOUDINARY_API_KEY,
        "CLOUDINARY_API_SECRET": CLOUDINARY_API_SECRET,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing env values: {', '.join(missing)}")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"\.{3,}", "…", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sign_cloudinary_upload(file_path: Path, transformation: str = "c_fill,ar_4:5,g_auto") -> str:
    print(f"[STEP] Cloudinary 업로드 시작: {file_path.name}")
    try:
        ts = str(int(time.time()))
        public_id = f"card_{ts}_{file_path.stem}"
        payload = {
            "timestamp": ts,
            "api_key": CLOUDINARY_API_KEY,
            "public_id": public_id,
            "transformation": transformation,
        }
        signature_string = f"public_id={public_id}&timestamp={ts}&transformation={transformation}{CLOUDINARY_API_SECRET}"
        payload["signature"] = hashlib.sha1(signature_string.encode("utf-8")).hexdigest()
        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, "image/png")}
            response = requests.post(
                f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/image/upload",
                data=payload,
                files=files,
                timeout=120,
            )
        try:
            resp_json = response.json()
        except ValueError:
            resp_json = {"raw": response.text}
        if response.status_code != 200:
            raise RuntimeError(f"Cloudinary upload failed: {resp_json}")
        secure_url = resp_json.get("secure_url")
        if not secure_url:
            raise RuntimeError(f"Cloudinary response missing secure_url: {resp_json}")

        accessible = False
        for attempt in range(3):
            try:
                head = requests.head(secure_url, timeout=15)
                if head.status_code == 200:
                    accessible = True
                    break
            except requests.exceptions.RequestException:
                pass
            if attempt < 2:
                time.sleep(2)
        if not accessible:
            print(f"[STEP] Cloudinary URL 접근 확인 실패(3회 재시도 후에도 비정상 상태): {secure_url}")

        print(f"[STEP] Cloudinary 업로드 종료: {secure_url}")
        return secure_url
    except Exception:
        print(f"[STEP] Cloudinary 업로드 실패: {file_path.name}")
        raise


def create_item_container(image_url: str, caption: str = "") -> str:
    print(f"[STEP] Instagram 발행 시작: item container 생성")
    try:
        payload = {
            "image_url": image_url,
            "is_carousel_item": "true",
            "access_token": IG_ACCESS_TOKEN,
        }
        if caption:
            payload["caption"] = caption
        response = requests.post(f"https://graph.instagram.com/{GRAPH_VERSION}/{IG_USER_ID}/media", data=payload, timeout=120)
        try:
            resp_json = response.json()
        except ValueError:
            resp_json = {"raw": response.text}
        if response.status_code != 200:
            raise RuntimeError(f"Instagram item creation failed: {resp_json}")
        if "id" not in resp_json:
            raise RuntimeError(f"Instagram item creation missing id: {resp_json}")
        print(f"[STEP] Instagram 발행 종료: item container 생성 완료")
        return str(resp_json["id"])
    except Exception:
        print(f"[STEP] Instagram 발행 실패: item container 생성")
        raise


def create_carousel_container(item_ids: list[str], caption: str) -> str:
    print(f"[STEP] Instagram 발행 시작: carousel container 생성")
    try:
        payload = {
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": IG_ACCESS_TOKEN,
        }
        response = requests.post(f"https://graph.instagram.com/{GRAPH_VERSION}/{IG_USER_ID}/media", data=payload, timeout=120)
        try:
            resp_json = response.json()
        except ValueError:
            resp_json = {"raw": response.text}
        if response.status_code != 200:
            raise RuntimeError(f"Instagram carousel creation failed: {resp_json}")
        if "id" not in resp_json:
            raise RuntimeError(f"Instagram carousel container missing id: {resp_json}")
        print(f"[STEP] Instagram 발행 종료: carousel container 생성 완료")
        return str(resp_json["id"])
    except Exception:
        print(f"[STEP] Instagram 발행 실패: carousel container 생성")
        raise


def wait_for_media_ready(container_id: str, max_attempts: int = 10, delay_seconds: int = 2) -> str:
    print(f"[STEP] Instagram 상태 확인 시작: container_id={container_id}")
    for attempt in range(1, max_attempts + 1):
        status_url = f"https://graph.instagram.com/{GRAPH_VERSION}/{container_id}?fields=status_code&access_token={IG_ACCESS_TOKEN}"
        response = requests.get(status_url, timeout=30)
        try:
            data = response.json()
        except ValueError:
            data = {"raw": response.text}

        status_code = data.get("status_code") if isinstance(data, dict) else None
        print(f"[STEP] Instagram 상태 확인 attempt={attempt}/{max_attempts}: status_code={status_code}")

        if status_code == "FINISHED":
            print(f"[STEP] Instagram 상태 확인 종료: FINISHED")
            return container_id
        if status_code == "IN_PROGRESS":
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Instagram carousel container did not finish processing within {max_attempts * delay_seconds} seconds: last_status={status_code}, response={data}"
                )
            print(f"[STEP] Instagram 상태 확인 대기: IN_PROGRESS -> {delay_seconds}초 후 재확인")
            time.sleep(delay_seconds)
            continue

        if response.status_code != 200:
            raise RuntimeError(f"Instagram status check failed: {data}")

        raise RuntimeError(f"Instagram container status unexpected: {data}")

    raise RuntimeError(f"Instagram container not ready after {max_attempts} attempts: {container_id}")


def find_recent_matching_media(caption: str, minutes: int = 15) -> str | None:
    """최근 N분 이내 게시물 중 caption이 완전히 일치하는 게 있으면 그 게시물 id를 반환한다.
    media_publish 호출이 에러/타임아웃을 반환했을 때, 실제로는 서버 쪽에서 게시가
    완료됐을 가능성을 재확인하기 위한 용도. creation_id는 media_publish 응답에서만
    확인 가능하고 공개 media 목록 조회로는 역추적할 수 없어 caption 일치로만 판단한다."""
    if not caption:
        return None
    try:
        response = requests.get(
            f"https://graph.instagram.com/{GRAPH_VERSION}/{IG_USER_ID}/media",
            params={"fields": "id,caption,timestamp", "limit": 10, "access_token": IG_ACCESS_TOKEN},
            timeout=30,
        )
        if response.status_code != 200:
            return None
        data = response.json()
    except Exception:
        return None

    target = clean_text(caption)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    for item in data.get("data", []) if isinstance(data, dict) else []:
        if clean_text(item.get("caption", "")) != target:
            continue
        try:
            ts = datetime.strptime(item.get("timestamp", ""), "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            continue
        if ts < cutoff:
            continue
        return str(item.get("id"))
    return None


def find_recent_duplicate_publish(caption: str, hours: int = 24) -> dict | None:
    """published_log.json 이력 중 최근 N시간 이내에 caption(또는 title)이 사실상
    동일한 발행 기록이 있으면 그 기록을 반환한다. 완전일치이거나 유사도 0.95 이상일 때만
    중복으로 판단해서, 우연히 비슷한 다른 콘텐츠까지 막지 않도록 한다."""
    log_path = BASE_DIR / "published_log.json"
    if not log_path.exists() or not caption:
        return None
    try:
        history = json.loads(log_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("게시 기록을 읽을 수 없어 중복 확인을 중단합니다.") from exc
    if not isinstance(history, list):
        raise ValueError("게시 기록은 목록이어야 합니다.")

    target = clean_text(caption)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    for entry in history:
        if not isinstance(entry, dict):
            continue
        created_at = str(entry.get("created_at", ""))
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if created_dt.tzinfo is None:
            created_dt = created_dt.astimezone()
        if created_dt < cutoff:
            continue
        candidate = clean_text(entry.get("caption") or entry.get("title") or "")
        if not candidate:
            continue
        if candidate == target or difflib.SequenceMatcher(None, target, candidate).ratio() >= 0.95:
            return entry
    return None


def publish_container(creation_id: str, caption: str = "") -> str:
    print(f"[STEP] Instagram 발행 시작: publish")
    try:
        wait_for_media_ready(creation_id)
        payload = {"creation_id": creation_id, "access_token": IG_ACCESS_TOKEN}
        try:
            response = requests.post(f"https://graph.instagram.com/{GRAPH_VERSION}/{IG_USER_ID}/media_publish", data=payload, timeout=120)
            resp_ok = response.status_code == 200
            try:
                resp_json = response.json()
            except ValueError:
                resp_json = {"raw": response.text}
            failure_detail = None if (resp_ok and "id" in resp_json) else resp_json
        except requests.exceptions.RequestException as exc:
            resp_ok = False
            resp_json = {}
            failure_detail = f"{type(exc).__name__}: {exc}"

        if failure_detail is not None:
            log_line(f"media_publish 실패 응답({failure_detail}) - 실제 게시 여부를 재확인한다")
            matched_id = find_recent_matching_media(caption)
            if matched_id:
                log_line(f"재확인 결과 실제로 게시됨(post_id={matched_id}) - 성공으로 처리, 예외 던지지 않음")
                print(f"[STEP] Instagram 발행 종료: publish 완료 (에러 응답이었으나 재확인으로 성공 확인됨)")
                return matched_id
            raise RuntimeError(f"Instagram publish failed: {failure_detail}")

        print(f"[STEP] Instagram 발행 종료: publish 완료")
        return str(resp_json["id"])
    except Exception:
        print(f"[STEP] Instagram 발행 실패: publish")
        raise
