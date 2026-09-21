import difflib
import hashlib
import html
import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
BROWSERS_DIR = BASE_DIR / "browsers"
BROWSERS_DIR.mkdir(exist_ok=True)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BROWSERS_DIR.resolve())

OUT_DIR = BASE_DIR / "out"
TEMPLATE_DIR = BASE_DIR / "skills" / "ig-carousel-publish" / "assets"
LOG_PATH = BASE_DIR / "auto_run.log"

IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")
GRAPH_VERSION = os.getenv("GRAPH_VERSION", "v21.0")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")

ACCENT_COLOR_POOL = [
    ("#E63946", "230,57,70"),    # 빨강
    ("#FF3D7F", "255,61,127"),   # 핫핑크
    ("#F77F00", "247,127,0"),    # 진한 주황
    ("#3A86FF", "58,134,255"),   # 선명한 파랑
    ("#7209B7", "114,9,183"),    # 진한 보라
]

BADGE_TEXT_POOL = ["🔥 충격", "🚨 긴급", "📢 필독", "😱 놓치면 손해", "📌 지금 꼭 확인"]

FONTS_DIR = TEMPLATE_DIR / "fonts"

HANDWRITING_FONT_FILES = {
    "Gaegu": ("Gaegu-Bold.ttf", 700),
    "Nanum Pen Script": ("NanumPenScript-Regular.ttf", 400),
}

_FONT_FACE_CACHE: dict[str, str] = {}


def get_handwriting_font_face_css(font_name: str) -> str:
    """지정된 손글씨 폰트 파일을 base64로 인라인한 @font-face CSS 블록을 반환한다(캐시됨)."""
    if font_name in _FONT_FACE_CACHE:
        return _FONT_FACE_CACHE[font_name]
    filename, weight = HANDWRITING_FONT_FILES[font_name]
    font_path = FONTS_DIR / filename
    if not font_path.exists():
        raise FileNotFoundError(f"Handwriting font file not found: {font_path}")
    import base64
    b64 = base64.b64encode(font_path.read_bytes()).decode("ascii")
    css = (
        "@font-face{"
        f"font-family:'{font_name}';font-style:normal;font-weight:{weight};"
        f"src:url(data:font/ttf;base64,{b64}) format('truetype');"
        "font-display:block;"
        "}"
    )
    _FONT_FACE_CACHE[font_name] = css
    return css


BLUEPRINT_RED = "#E63946"

_STATIC_FONT_FACE_CACHE: dict[str, str] = {}


def get_static_font_face_css(cache_key: str, family: str, filename: str, fmt: str, weight: str, mime: str) -> str:
    """assets/fonts 의 폰트 파일을 base64로 인라인한 @font-face CSS 블록을 반환한다(캐시됨)."""
    if cache_key in _STATIC_FONT_FACE_CACHE:
        return _STATIC_FONT_FACE_CACHE[cache_key]
    font_path = FONTS_DIR / filename
    if not font_path.exists():
        raise FileNotFoundError(f"Font file not found: {font_path}")
    import base64
    b64 = base64.b64encode(font_path.read_bytes()).decode("ascii")
    css = (
        "@font-face{"
        f"font-family:'{family}';font-style:normal;font-weight:{weight};"
        f"src:url(data:{mime};base64,{b64}) format('{fmt}');"
        "font-display:block;"
        "}"
    )
    _STATIC_FONT_FACE_CACHE[cache_key] = css
    return css


BLUEPRINT_FONT_MAP = {
    "title": {"cache_key": "jua", "family": "Jua", "filename": "Jua-Regular.ttf", "fmt": "truetype", "weight": "400", "mime": "font/ttf"},
    "body": {"cache_key": "pretendard_variable", "family": "Pretendard", "filename": "PretendardVariable.woff2", "fmt": "woff2-variations", "weight": "45 920", "mime": "font/woff2"},
}


def get_blueprint_font_faces_css() -> str:
    """Jua(제목) + Pretendard(본문) @font-face를 하나로 합쳐 반환한다(캐시됨, link/@import 미사용).
    Jalnan은 'ㅎ' 받침 음절이 깨지는 글리프 결함이 실측 확인되어 Jua로 교체했다."""
    parts = []
    for spec in BLUEPRINT_FONT_MAP.values():
        parts.append(get_static_font_face_css(
            spec["cache_key"], spec["family"], spec["filename"], spec["fmt"], spec["weight"], spec["mime"]
        ))
    return "".join(parts)


def highlight_numbers_red(text: str, accent_hex: str = BLUEPRINT_RED) -> str:
    """블루프린트 디자인용: 숫자를 박스 없이 포인트 컬러 텍스트로만 강조한다."""
    def repl(match: re.Match) -> str:
        return f'<span style="color:{accent_hex};">{match.group(0)}</span>'
    return NUMBER_HIGHLIGHT_RE.sub(repl, text or "")


def pick_accent_color() -> tuple[str, str]:
    return random.choice(ACCENT_COLOR_POOL)


def pick_badge_text() -> str:
    return random.choice(BADGE_TEXT_POOL)


def resolve_claude_cli_path() -> str | None:
    """claude.exe 절대 경로를 찾는다. 환경변수 -> PATH -> VSCode 확장 설치 경로 순."""
    env_path = os.getenv("CLAUDE_EXE") or os.getenv("CLAUDE_PATH")
    if env_path and Path(env_path).is_file():
        return env_path

    which_path = shutil.which("claude") or shutil.which("claude.exe")
    if which_path:
        return which_path

    ext_root = Path.home() / ".vscode" / "extensions"
    if ext_root.is_dir():
        candidates = sorted(
            ext_root.glob("anthropic.claude-code-*/resources/native-binary/claude.exe"),
            reverse=True,
        )
        if candidates:
            return str(candidates[0])

    return None


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


def step_log(label: str, status: str):
    safe_console_print(f"[STEP] {label} {status}")


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


def split_title_to_lines(title: str) -> tuple[str, int, int]:
    """제목 줄바꿈은 CSS(word-break:keep-all)에 맡기고, 총 글자수 기준으로 줄당 12자 내외가
    되도록 폰트 크기만 조정한다. 손글씨 폰트(Gaegu)는 920px 컨테이너 폭 기준 대략 140px에서
    한 줄에 7~8자, 96px에서 10~11자 정도가 들어간다 — 실측 렌더링으로 보정된 값."""
    normalized = " ".join(title.split())
    if not normalized:
        return "", 1, 96
    length = len(normalized)
    if length <= 10:
        font_size = 132
    elif length <= 16:
        font_size = 108
    elif length <= 22:
        font_size = 92
    else:
        font_size = 78
    return normalized, 1, font_size


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"\.{3,}", "…", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def shorten_text(value: str | None, limit: int = 46) -> str:
    text = (value or "").strip()
    text = re.sub(r"\.{3,}", "…", text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


NUMBER_HIGHLIGHT_RE = re.compile(r"\d[\d,]*(?:천|만|억)?원|\d+(?:\.\d+)?\s?%")


def derive_headline_amount(title: str = "", benefit: str = "") -> str:
    for source in (title, benefit):
        if not source:
            continue
        matches = re.findall(r"\d[\d,]*(?:천|만|억)?원", str(source))
        if matches:
            return matches[-1]
    return "0원"


def highlight_numbers(text: str, accent_hex: str) -> str:
    def repl(match: re.Match) -> str:
        return f'<span style="color:{accent_hex};font-size:1.25em;font-weight:900;">{match.group(0)}</span>'
    return NUMBER_HIGHLIGHT_RE.sub(repl, text or "")


def highlight_numbers_marker(text: str, accent_rgb: str) -> str:
    def repl(match: re.Match) -> str:
        angle = round(random.uniform(-3, 3), 1)
        return (
            '<span style="position:relative;z-index:0;display:inline-block;font-weight:900;color:#111;line-height:1;">'
            f'<span style="position:absolute;left:-8px;right:-8px;top:-0.14em;bottom:-0.18em;'
            f'background:rgba({accent_rgb},0.4);border:2px solid #111;'
            f'transform:rotate({angle}deg);'
            'border-radius:4px;z-index:-1;"></span>'
            f'{match.group(0)}</span>'
        )
    return NUMBER_HIGHLIGHT_RE.sub(repl, text or "")


def normalize_support_title(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def load_published_titles() -> set[str]:
    log_path = BASE_DIR / "published_log.json"
    if not log_path.exists():
        return set()
    try:
        data = json.loads(log_path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    titles = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                title = item.get("title") or item.get("program_title") or ""
                if title:
                    titles.add(normalize_support_title(title))
    return titles


def extract_support_fields(title: str, snippet: str = "", article_text: str = "") -> dict:
    merged = " ".join(part for part in [title, snippet, article_text] if part).strip()
    if not merged:
        return {}

    title = clean_text(title)
    snippet = clean_text(snippet)
    combined = " ".join(part for part in [title, snippet, article_text] if part)

    target = ""
    benefit = ""
    period = ""
    method = ""

    target_match = re.search(r"(대상|지원대상|신청대상|누가 받을 수 있나요?)[^\n]*[:：]?\s*([^\n\.]+)", combined)
    if target_match:
        candidate_target = target_match.group(2).strip(" .")
        if len(candidate_target) >= 3 and candidate_target not in {"다", "이다", "입니다"}:
            target = candidate_target
    if not target:
        for pattern in [r"(청년.*?\d+세.*?\d+세.*?\b(?:세대|가구|인원)\b.*)", r"(무주택.*?(세입자|가구|청년).*)", r"(소득.*?재산.*?\b(?:가구|세대|분)\b.*)"]:
            match = re.search(pattern, combined)
            if match:
                target = match.group(1).strip(" .")
                break
    if not target:
        target_match = re.search(r"((?:수도권\s*)?(?:취업\s*)?청년(?:층|근로자|구직자)?)", combined)
        if target_match:
            target = target_match.group(1).strip()

    benefit_match = re.search(r"\d[\d,]*(?:만원|원|억원|억)", combined)
    if benefit_match:
        benefit = benefit_match.group(0)
    if not benefit:
        benefit = "정부 지원금 혜택 확인"

    period_match = re.search(
        r"(\d{4}[.\/-]\d{1,2}[.\/-]\d{1,2}\s*(?:~|부터|까지)\s*\d{4}[.\/-]\d{1,2}[.\/-]\d{1,2}|"
        r"(?:신청 기간|접수 기간|신청기간|지원 기간)\s*[:：]?\s*(?:\d{4}[.\/-]\d{1,2}[.\/-]\d{1,2}(?:\s*(?:~|부터|까지)\s*\d{4}[.\/-]\d{1,2}[.\/-]\d{1,2})?|상시|예산 소진 시까지|예산 소진시까지|[^.]{2,80})|"
        r"(?:상시|예산 소진 시까지|예산 소진시까지|마감 시까지))",
        combined,
    )
    if period_match:
        period = period_match.group(0).strip(" .")
    if not period:
        for token in ["신청 마감", "신청 시작", "접수 중", "접수 마감"]:
            if token in combined:
                period = token
                break
    if not period:
        period = "신청 기간 확인 필요"

    if re.search(r"(온라인|인터넷|홈페이지)[^。.]{0,30}신청|신청[^。.]{0,30}(온라인|인터넷|홈페이지)", combined):
        method = "온라인 신청"
    elif re.search(r"방문[^。.]{0,30}신청|신청[^。.]{0,30}방문", combined):
        method = "방문 신청"
    else:
        method = "온라인/오프라인 신청"

    if not title:
        title = "정부 지원금 바로 확인"

    return {
        "title": title,
        "badge": "📌 지금 꼭 확인",
        "subtitle": benefit,
        "handle": "lumistoy",
        "hairline": "지원금 정보 요약",
        "target": target or "해당 지원 대상 확인",
        "benefit": benefit,
        "period": period,
        "method": method,
        "summary": "한 번만 확인하면 생활비와 부담을 줄일 수 있어요.",
    }


def fetch_article_metadata(link: str) -> tuple[str, str, str]:
    if not link:
        return "", "", ""
    try:
        response = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        if response.status_code != 200:
            return "", "", ""
        values = {}
        for name in ("title", "description"):
            match = re.search(
                rf'<meta[^>]+property=["\']og:{name}["\'][^>]+content=["\']([^"\']*)',
                response.text,
                flags=re.I,
            )
            values[name] = clean_text(match.group(1)) if match else ""
        article_text = re.sub(r"<script[^>]*>.*?</script>|<style[^>]*>.*?</style>|<noscript[^>]*>.*?</noscript>", " ", response.text, flags=re.I | re.S)
        article_text = clean_text(article_text)
        return values["title"], values["description"], article_text
    except Exception:
        return "", "", ""


def is_complete_support_story(story: dict) -> bool:
    return (
        story.get("period") not in {"", "신청 기간 확인 필요"}
        and story.get("method") not in {"", "온라인/오프라인 신청"}
    )


def fetch_naver_news_candidates(query: str, max_results: int = 6) -> list[dict]:
    candidates: list[dict] = []
    headers = {"User-Agent": "Mozilla/5.0"}
    params = {"where": "news", "query": query}
    url = "https://search.naver.com/search.naver"
    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        if response.status_code != 200:
            return candidates

        html_text = response.text
        anchors = re.findall(
            r'<a(?=[^>]*data-heatmap-target="\.tit")[^>]*href="(https?://[^\"]+)"[^>]*>(.*?)</a>',
            html_text,
            flags=re.S | re.I,
        )
        for href, title_html in anchors:
            href = href.strip()
            if not href or "://" not in href:
                continue
            host = href.lower()
            if any(token in host for token in ("search.naver.com", "news.naver.com", "n.news.naver.com", "m.news.naver.com", "media.naver.com")):
                continue

            title = clean_text(title_html)
            title = re.sub(r"\s*(?:새 창 열림|\.\.\.)$", "", title).strip()
            if not title:
                title_match = re.search(r'title="([^"]+)"', html_text[html_text.find(href)-200:html_text.find(href)+300], flags=re.S | re.I)
                if title_match:
                    title = clean_text(title_match.group(1))
            if not title or title in {"네이버뉴스 새 창 열림", "새 창 열림"}:
                continue
            if len(title) < 8:
                continue

            snippet = ""
            snippet_match = re.search(rf'<a[^>]*href="{re.escape(href)}"[^>]*>(.*?)</a>(?:.*?<div[^>]*class="[^"]*desc[^"]*"[^>]*>)(.*?)</div>', html_text, flags=re.S | re.I)
            if snippet_match:
                snippet = clean_text(snippet_match.group(2))
            candidates.append({"title": title, "snippet": snippet, "link": href})
    except Exception:
        return candidates

    seen = set()
    deduped: list[dict] = []
    for item in candidates:
        key = normalize_support_title(item.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped[:max_results]


def is_support_candidate(title: str, snippet: str = "") -> bool:
    text = clean_text(f"{title or ''} {snippet or ''}").lower()
    if not text:
        return False

    required_tokens = ["지원금", "지원", "월세", "생활비", "수당", "바우처", "장려금", "급여"]
    if not any(token in text for token in required_tokens):
        return False

    blocked_tokens = ["맛집", "추천", "리뷰", "광고", "축제", "콘서트", "주식", "투자"]
    if any(token in text for token in blocked_tokens):
        return False

    return True


def search_support_with_claude(query: str) -> dict | None:
    cli_path = resolve_claude_cli_path()
    if not cli_path:
        return None

    prompt = (
        "정부 지원금 관련 최신 검색 결과를 읽고, JSON 하나만 반환해. "
        "반드시 형식은 {\"title\":\"...\",\"snippet\":\"...\"} 이어야 하고, "
        "정부지원금이 아닌 광고/뉴스는 제외해. 검색어: " + query
    )
    try:
        result = subprocess.run(
            [cli_path, "--print", "--allowedTools", "WebSearch", "-p", prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return None
        payload = result.stdout.strip()
        if payload.startswith("```"):
            payload = payload.strip("`\n ")
            if payload.startswith("json"):
                payload = payload[4:].strip()
        parsed = json.loads(payload)
        if isinstance(parsed, dict) and parsed.get("title"):
            return {"title": parsed.get("title", ""), "snippet": parsed.get("snippet", "")}
    except Exception:
        return None
    return None


def fallback_support_story() -> dict:
    return {
        "category": "청년지원금",
        "title": "청년 월세 부담, 정부가 덜어드려요",
        "badge": "📌 지금 꼭 확인",
        "subtitle": "최대 20만원 지원, 신청 마감 임박",
        "handle": "lumistoy",
        "hairline": "지원금 정보 요약",
        "target": "청년 1인 가구, 무주택 세입자, 월세 부담이 큰 분",
        "benefit": "월 최대 20만원, 1년 한도 내 지원",
        "period": "신청 기간: 2026.09.01 ~ 2026.09.30",
        "method": "온라인 신청 → 서류 제출 → 심사 후 지급",
        "summary": "한 번만 확인하면 매달 부담을 줄일 수 있어요.",
        "cta_bottom": "지금 조건 확인하고 신청 기한 놓치지 마세요.",
        "loss_reason": "신청 안 하면 월 최대 20만원, 이거 그냥 못 받는 거예요. 신청은 어렵지 않으니까 미루지 마세요.",
        "tips": [
            "서류 하나만 빠져도 반려돼서 다시 준비해야 해요",
            "신청 기한 하루만 넘겨도 그 달치 못 받아요",
            "조건 미리 안 보면 헛걸음할 수 있어요",
        ],
        "loss_causes": [
            "신청 안 하면 월 최대 20만원 그대로 못 받아요",
            "기한 지나면 그 달 지원은 그냥 소멸돼요",
            "늦게 신청할수록 받는 개월 수도 줄어들어요",
        ],
        "comparison": "이거면 한 달 관리비 정도는 커버돼요",
        "comment_keyword": "월세",
        "selection_status": "no_suitable_candidate",
        "publishable": False,
    }


def extract_json_object(text: str) -> dict | None:
    payload = (text or "").strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", payload, flags=re.S | re.I)
    if fenced_match:
        payload = fenced_match.group(1)
    else:
        object_match = re.search(r"\{.*\}", payload, flags=re.S)
        if object_match:
            payload = object_match.group(0)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def extract_json_array(text: str) -> list | None:
    payload = (text or "").strip()
    fenced_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", payload, flags=re.S | re.I)
    if fenced_match:
        payload = fenced_match.group(1)
    else:
        array_match = re.search(r"\[.*\]", payload, flags=re.S)
        if array_match:
            payload = array_match.group(0)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, list) else None


GENERIC_SUPPORT_KEYWORDS = {
    "정부지원금", "정부 지원금", "지원금", "나라지원금", "나라 지원금",
    "국가지원금", "국가 지원금", "지자체지원금", "지자체 지원금",
    "정부혜택", "정부 혜택", "지원혜택", "지원 혜택",
}


def is_generic_support_keyword(keyword: str) -> bool:
    """'정부지원금'처럼 특정 제도를 가리키지 않는 포괄적 키워드인지 판별한다."""
    normalized = clean_text(keyword or "").replace(" ", "")
    return normalized in {k.replace(" ", "") for k in GENERIC_SUPPORT_KEYWORDS}


def parse_deadline_date(deadline: str) -> datetime | None:
    text = (deadline or "").strip()
    if not text or text in {"상시", "상시접수", "상시 접수", "미정", "확인불가", "수시", "수시접수"}:
        return None
    match = re.search(r"(\d{4})[.\-년\s]+(\d{1,2})[.\-월\s]+(\d{1,2})", text)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def sort_candidates_by_deadline(candidates: list[dict]) -> list[dict]:
    """마감일이 가장 임박한 순으로 정렬한다. '상시'/마감일 불명/이미 지난 마감일은 뒤로 민다."""
    today = datetime.now()

    def sort_key(item: dict):
        parsed_date = parse_deadline_date(item.get("deadline", ""))
        if parsed_date is None:
            return (1, datetime.max)
        days_left = (parsed_date - today).days
        if days_left < 0:
            return (1, datetime.max)
        return (0, parsed_date)

    return sorted(candidates, key=sort_key)


def find_support_candidates() -> dict:
    """Claude CLI(WebSearch)로 현재 신청 가능한 정부/지자체 지원금 후보를 조회해
    '마감임박' TOP5 / '신규·시작' TOP5 두 그룹으로 분류해 반환한다.
    조건에 맞는 후보가 5개 미만이면 억지로 채우지 않고 있는 만큼만 반환한다.
    같은 지원금이 두 그룹에 겹치면 마감임박 쪽에만 남긴다.
    실패 시 두 그룹 모두 빈 리스트를 반환한다.

    반환: {"deadline_soon": [...], "new_or_started": [...]}
    각 항목: {"name", "deadline", "target", "status"}
    """
    cli_path = resolve_claude_cli_path()
    if not cli_path:
        log_line("Claude Code CLI를 찾지 못했다 (find_support_candidates)")
        return {"deadline_soon": [], "new_or_started": []}

    prompt = (
        "지금(오늘) 기준으로 대한민국에서 실제로 신청 가능한 정부/지자체 지원금 제도를 실제 웹검색으로 찾아서 "
        "최대 20개까지 JSON 배열로만 응답해 (다른 설명 텍스트 없이 JSON만).\n"
        "각 항목은 다음 필드를 포함해:\n"
        '- name: 지원금 정식 명칭\n'
        '- deadline: 신청 마감일. 알 수 있으면 "YYYY-MM-DD" 형식으로 쓰고, 상시 접수이거나 마감일을 확인할 수 없으면 "상시"라고 써.\n'
        '- target: 지원 대상 한 줄 요약(30자 이내)\n'
        '- status: 마감일이 임박한 제도면 "마감임박", 최근에 신청이 열렸거나 새로 시작된 제도면 "신규/시작"이라고 써.\n\n'
        "이미 마감됐거나 실제로 존재하는지 확실하지 않은 제도는 포함하지 마.\n"
        '응답 형식: [{"name":"...","deadline":"YYYY-MM-DD","target":"...","status":"마감임박"}, ...]'
    )
    try:
        result = subprocess.run(
            [cli_path, "--print", "--allowedTools", "WebSearch", "-p", prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=330,
            check=False,
        )
    except Exception as exc:
        log_line(f"Claude Code CLI 후보 검색 실패: {type(exc).__name__}")
        return {"deadline_soon": [], "new_or_started": []}
    if result.returncode != 0:
        log_line("Claude Code CLI가 후보 검색에 정상 응답하지 않았다")
        return {"deadline_soon": [], "new_or_started": []}

    raw_candidates = extract_json_array(result.stdout)
    if not raw_candidates:
        log_line("후보 검색 결과를 JSON으로 파싱하지 못했다")
        return {"deadline_soon": [], "new_or_started": []}

    cleaned: list[dict] = []
    seen_keys: set[str] = set()
    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        name = clean_text(str(item.get("name", "")))
        if not name:
            continue
        key = normalize_support_title(name)
        if not key or key in seen_keys:
            continue
        seen_keys.add(key)
        cleaned.append({
            "name": name,
            "deadline": clean_text(str(item.get("deadline", ""))) or "상시",
            "target": clean_text(str(item.get("target", ""))),
            "status": clean_text(str(item.get("status", ""))),
        })

    dated = [c for c in cleaned if parse_deadline_date(c["deadline"]) is not None]
    deadline_soon = sort_candidates_by_deadline(dated)[:5]
    used_keys = {normalize_support_title(c["name"]) for c in deadline_soon}

    remaining = [c for c in cleaned if normalize_support_title(c["name"]) not in used_keys]
    new_or_started = [c for c in remaining if c["status"] == "신규/시작"][:5]

    log_line(f"[후보검색] 마감임박 {len(deadline_soon)}개 / 신규·시작 {len(new_or_started)}개")
    for idx, candidate in enumerate(deadline_soon, 1):
        log_line(f"[마감임박 {idx}] {candidate['name']} | 마감:{candidate['deadline']} | 대상:{candidate['target']}")
    for idx, candidate in enumerate(new_or_started, 1):
        log_line(f"[신규/시작 {idx}] {candidate['name']} | 마감:{candidate['deadline']} | 대상:{candidate['target']}")

    return {"deadline_soon": deadline_soon, "new_or_started": new_or_started}


def search_support_by_keyword(keyword: str) -> dict | None:
    cli_path = resolve_claude_cli_path()
    if not cli_path:
        log_line("Claude Code CLI를 찾지 못했다")
        return None

    is_childcare_leave_keyword = "육아휴직" in keyword

    childcare_scope_note = (
        (
            "반드시 '일반 근로자 대상 고용보험 육아휴직급여' 범위로 검색하고, 공무원/지자체/특정 업종 전용 제도와 혼동될 수 있는 검색 결과는 제외한다. "
            "검색 결과에 '공무원', '국가공무원법', '지방공무원법', '육아기 근로시간단축' 같은 단어가 포함된 출처는 이 카드의 target/benefit 정보로 쓰지 마. "
            "다른 제도이므로 대상 나이·급여 조건이 다를 수 있다.\n"
        )
        if is_childcare_leave_keyword
        else ""
    )
    childcare_benefit_ratio_note = (
        "특히 육아휴직급여는 급여 비율이 구간별로 달라서, 1~6개월은 통상임금 100%, 7~12개월은 통상임금 80%라는 표현을 정확히 구분해서 적어. "
        if is_childcare_leave_keyword
        else ""
    )
    childcare_age_limit_note = (
        (
            "특히 육아휴직급여의 대상 연령은 '만 8세 이하(초등학교 2학년 이하)'로 제한하고, 이 기준을 title/subtitle/target에 반영해. "
            "대상 나이가 장기저리되거나 다른 제도 기준이 나오면 그 표현을 사용하지 말고 일반 근로자 고용보험 기준으로 다시 써.\n"
        )
        if is_childcare_leave_keyword
        else ""
    )

    prompt = (
        f"{keyword}에 대한 정부 지원금 인스타 카드뉴스를 만들려고 해. 8장짜리 카드뉴스인데, "
        "표지에서 던진 손실이 뒤 슬라이드에서 '왜' 발생하는지 논리적으로 증명되는 구조로 만들 거야. "
        "아래 순서로 진행해줘.\n\n"
        "1) 먼저 실제 웹검색으로 정확한 사실을 찾아. 대상(target), 혜택(benefit), 신청기간(period), "
        "신청방법(method)은 반드시 실제로 존재하고 지금 신청 가능한 정확한 정보여야 해. "
        "특히 금액·퍼센트·날짜 숫자는 실제 검색 결과의 정확한 숫자를 써야 해(추측 금지). "
        "신청기간이나 방법을 명확히 찾을 수 없으면 해당 값에 '확인불가'라고 쓰고 다른 관련 정보를 다시 찾아봐.\n"
        f"{childcare_scope_note}"
        "일반 규칙: 검색된 정보가 정확히 이 키워드가 가리키는 제도의 것인지, 이름이 비슷한 다른 제도(공무원 전용, 지자체 전용, 특정 업종 전용 등)는 아닌지 반드시 확인해. "
        "이름이 비슷한 제도는 대상·급여·기간 조건이 다를 수 있으므로 일치 여부를 먼저 검증한 뒤 사용해.\n"
        "이 카드뉴스 전체는 존댓말 구어체로 통일한다. title, subtitle, caption, loss_reason, loss_causes, comparison, tips, method, cta_bottom, "
        "헤딩/배너/고정 문구까지 모두 존댓말 톤으로 작성한다. 반말 또는 구어체 표현('그냥 날아감', '증발', '알려드려요' 같은 표현)은 절대 쓰지 않고, "
        "모든 문장은 존댓말로 바꿔서 써야 한다.\n"
        "금액 표현 규칙(모든 필드 공통): 금액이 기간별로 다르면 어느 필드에서든 '최대 250만원' 같은 대표값만 쓰지 말고, "
        "반드시 조건을 붙여서 '첫 3개월 250만원', '1~3개월 250만원', '4~6개월 200만원', '7~12개월 160만원'처럼 구간 혹은 시점을 함께 적어. "
        "특히 caption/title/subtitle에서는 핵심 금액을 headline_amount 필드로 별도로 넣어야 하고, headline_amount는 title 안의 금액과 정확히 같은 숫자여야 해. "
        "즉 title이 '첫 3개월 250만원'이면 headline_amount도 반드시 '250만원' 이어야 하며, title에서 쓰는 숫자와 다른 금액을 추론해서는 안 된다. "
        "특정 구간의 대표값만 쓰는 표지 제목이나 subtitle도 '첫', '~부터', '1~3개월' 같은 조건어를 꼭 붙여. "
        f"{childcare_benefit_ratio_note}"
        "benefit 필드에서는 금액이 구간별로 다르면 '1~6개월 OO원, 7~12개월 OO원'처럼 구간별로 나눠 쓰거나, 괄호 설명을 빼고 구간별 금액만 명시해서 헷갈리지 않게 작성해. "
        "아예 한 줄로 합쳐서 '통상임금 100%, 상한액 기준'처럼 전체에 동일하게 적용되는 것처럼 쓰는 표현은 금지한다. "
        "benefit 필드에는 구간을 전부 명시해 (예: '1~6개월 OO원, 7~12개월 OO원'). "
        "그 외 필드(title, subtitle, loss_causes, comparison, tips, caption, loss_reason, method, cta_bottom)에도 금액이 들어가면 조건 없이 숫자만 던지는 표현을 금지하고, "
        "항상 적용 조건과 함께 쓰도록 한다. 대표값을 넣을 때는 반드시 구간/시점/조건이 붙어야 하며, 구간이 달라지는 제도면 절대 평균값·최대값만으로 요약하지 않는다.\n"
        "benefit은 100자 이내로, target은 60자 이내로, period는 40자 이내로 정확한 사실을 유지하면서 최대한 간결하게 요약해.\n\n"
        "2) 찾은 사실을 바탕으로, 숫자와 사실은 절대 왜곡하지 말고 표현만 최대한 어그로 있게 후킹력을 살려서 "
        "아래 카피를 새로 써줘. 이 계정은 '읽씹하면 손해보는 정부지원금 정보'를 컨셉으로 하는 자극적인 톤이 목표야.\n"
        "- title: 카드뉴스 표지에 크게 들어갈 제목. '모르면'이 아니라 반드시 '신청 안 하면/신청을 안 해서' "
        "처럼 명확한 행동 부재를 원인으로 명시하고, 아래 세 가지 패턴 중 하나를 그대로 따라 써줘. "
        "1)에서 찾은 실제 금액이나 날짜 숫자를 반드시 넣어줘. 혜택 금액이 구간별로 다르면 대표 최고값이 아니라 "
        "실제로 처음 적용되는 구간의 숫자를 쓰고 필요하면 '첫 O개월' 같은 짧은 조건을 붙여줘(과장 금지). "
        f"{childcare_age_limit_note}"
        "  · 손실회피형: '신청 안 하면 첫 3개월 250만원 그냥 날아감'\n"
        "  · 충격형: '직장인 10명 중 8명이 신청 안 해서 놓치는 첫 3개월 250만원'\n"
        "  · 긴급형: 'OO까지 신청 안 하면 끝'\n"
        "  전체 15~22자 내외, 화면에서는 두 줄로 나뉘어 보이니 각 줄이 12자 정도가 되게 자연스러운 위치에서 끊어줘.\n"
        "- subtitle: title을 더 세게 밀어주는 한 줄. 스크롤을 멈추게 할 정도의 임팩트, 숫자 포함. 반드시 조건을 붙여서 표현하되, 조건 없이 대표값만 쓰지 않는다.\n"
        "- loss_causes: title에서 던진 손실이 '왜' 실제로 발생하는지 증명하는 구체적 이유를 배열로 3개. "
        "실제 검색한 수치를 근거로 넣어줘 (예: '12개월 지나면 남은 급여 전액 소멸', "
        "'하루씩 늦을 때마다 68,100원씩 계속 손해', '서류 준비 안 하면 마감 임박해서 못 냄'). "
        "각 항목 35자 이내로, 절대 45자를 넘기지 마(넘으면 한 문장을 두 항목으로 쪼개).\n"
        "- comparison: 혜택 금액을 체감되게 만드는 비교 문구 하나. 실제 금액 기준으로 "
        "'첫 3개월 250만원이면 두 달 치 월세', '첫 3개월 250만원이면 매달 생활비 절반' 같은 식으로 실감나게. 20자 내외.\n"
        "- cta_bottom: 혜택 슬라이드 맨 아래 배너에 들어갈 한 줄 문구, 반드시 26자 이내로 짧게. "
        "'지금 안 하면 놓친다'는 긴급성과 함께, 이 주제에 맞는 구체적인 다음 행동을 제안해줘 "
        "(예: '지금 고용24 들어가서 신청부터' 같은 식). "
        "'한 번 확인하면 부담을 줄일 수 있어요' 같은 뻔하고 안전한 문구는 절대 금지.\n"
        "- caption: 인스타그램 게시물 캡션. 첫 줄부터 강하게 후킹하고, 존댓말 구어체와 이모지를 섞어서 "
        "광고처럼 딱딱하지 않게, 해시태그 4~5개 포함해서 5~8문장으로.\n"
        "- loss_reason: '신청 안 하면 손해보는 이유'를 재환기하는 문구. 정확히 2문장으로 제한하고, 각 문장 45자 이내로. "
        "이미 slide4(혜택)에서 구간별 금액을 다 보여줬으니, loss_reason에서는 구간을 다시 나열하지 말고 '신청 안 하면 못 받는다'는 결과만 집중해. "
        "예: '육아휴직급여는 신청해야 나오는 돈이에요. 기한(종료 후 12개월) 넘기면 그 돈은 다시 못 받아요.'처럼 간결한 톤으로 써. "
        "신청 안 했을 때 실제로 얼마를 못 받는지 숫자를 넣는 건 가능하지만, 구간별 금액을 반복해 나열하는 표현은 금지.\n"
        "- method: 신청 방법을 '→'로 구분한 단계별로 써줘 (예: '① 구직등록 → ② 온라인 교육 이수 → "
        "③ 고용센터 방문 신청'). 이 중 놓치기 쉬운 단계 최소 1개에는 ' — 놓치면 OOO' 형태로 짧은 "
        "위험 요소를 그 단계 문구 끝에 바로 붙여줘 (예: '③ 고용센터 방문 신청 — 늦으면 처음부터 다시 신청').\n"
        "- tips: 신청 전 꼭 알아야 할 주의사항·팁을 배열로 3개. 각 항목은 '무엇을 놓치면' + "
        "'그래서 어떤 손해(돈/시간)를 보는지'를 한 문장 안에 짧게 같이 담아줘 "
        "(예: '서류 하나만 빠져도 반려돼서 2주 이상 밀려요', '기한 하루만 넘겨도 그 달치 못 받아요'). "
        "각 항목 35자 이내로, 절대 45자를 넘기지 마(넘으면 한 문장을 두 항목으로 쪼개).\n"
        "- comment_keyword: 이 주제를 대표하는 아주 짧은 키워드 2~4글자. 인스타 댓글에 그대로 "
        f"타이핑하기 쉬운 단어로 ({keyword}가 길면 핵심 단어만 줄여서, 예: '실업급여'→'급여').\n\n"
        "다음 표현은 밋밋하고 안전해서 절대 쓰지 마: '~에 도움이 됩니다', '확인해보세요', "
        "'~하는 데 도움이 됩니다', '알아보세요'.\n\n"
        "아래 JSON 형식으로만 응답해 (다른 설명 텍스트 없이 JSON만):\n"
        '{"title":"...","headline_amount":"250만원","subtitle":"...","cta_bottom":"...","caption":"...",'
        '"loss_reason":"...","loss_causes":["...","...","..."],"comparison":"...",'
        '"tips":["...","...","..."],'
        '"comment_keyword":"...",'
        '"target":"...","benefit":"...","period":"...","method":"..."}'
    )
    try:
        result = subprocess.run(
            [cli_path, "--print", "--allowedTools", "WebSearch", "-p", prompt],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=330,
            check=False,
        )
    except Exception as exc:
        log_line(f"Claude Code CLI 검색 실패: {type(exc).__name__}")
        return None
    if result.returncode != 0:
        log_line("Claude Code CLI가 정상 응답하지 않았다")
        return None

    parsed = extract_json_object(result.stdout)
    required = ("title", "headline_amount", "target", "benefit", "period", "method")
    if not parsed or any(not str(parsed.get(key, "")).strip() for key in required):
        return None
    if any(str(parsed[key]).strip() == "확인불가" for key in ("period", "method")):
        return None
    if not str(parsed.get("headline_amount", "")).strip():
        parsed["headline_amount"] = derive_headline_amount(str(parsed.get("title", "")), str(parsed.get("benefit", "")))
    else:
        parsed["headline_amount"] = str(parsed["headline_amount"]).strip()
    if not str(parsed.get("subtitle", "")).strip():
        parsed["subtitle"] = str(parsed["benefit"])
    if not str(parsed.get("cta_bottom", "")).strip():
        parsed["cta_bottom"] = "지금 조건 확인하고 신청 기한 놓치지 마세요."
    if not str(parsed.get("loss_reason", "")).strip():
        parsed["loss_reason"] = f"신청 안 하면 {parsed['benefit']}, 이거 그냥 못 받는 거예요. 신청은 어렵지 않으니까 미루지 마세요."
    if not isinstance(parsed.get("tips"), list) or not parsed.get("tips"):
        parsed["tips"] = [
            "서류 하나만 빠져도 반려돼서 다시 준비해야 해요",
            "신청 기한 하루만 넘겨도 그 달치 못 받아요",
            "조건 미리 안 보면 헛걸음할 수 있어요",
        ]
    if not isinstance(parsed.get("loss_causes"), list) or not parsed.get("loss_causes"):
        parsed["loss_causes"] = [
            f"신청 안 하면 {parsed['benefit']} 그대로 못 받아요",
            "기한 지나면 남은 금액도 전부 소멸돼요",
            "늦게 신청할수록 받는 금액도 줄어들어요",
        ]
    if not str(parsed.get("comparison", "")).strip():
        parsed["comparison"] = "이거면 생활비 부담이 확 줄어요"
    if not str(parsed.get("comment_keyword", "")).strip():
        parsed["comment_keyword"] = shorten_text(str(parsed["title"]), 4)
    parsed.update({
        "badge": "📌 지금 꼭 확인",
        "handle": "lumistoy",
        "hairline": "지원금 정보 요약",
        "summary": "신청 대상과 방법을 확인하고 놓치지 마세요.",
        "category": "정부지원금",
        "publishable": True,
        "selection_status": "keyword_cli_candidate",
    })
    return parsed


def choose_support_story(keyword: str | None = None) -> dict:
    if keyword:
        story = search_support_by_keyword(keyword)
        if story:
            return story
        log_line(f"키워드 후보 부적합: {keyword}")
        return fallback_support_story()

    published_titles = load_published_titles()
    search_queries = [
        "최근 정부 청년 지원금",
        "최신 청년 월세 지원",
        "정부 지원금 신청",
        "청년 생활비 지원 뉴스",
    ]

    candidates: list[dict] = []
    for query in search_queries:
        for item in fetch_naver_news_candidates(query, max_results=5):
            if not item.get("title"):
                continue
            title = clean_text(item["title"])
            if normalize_support_title(title) in published_titles:
                continue
            if not is_support_candidate(title, item.get("snippet", "")):
                continue
            article_title, article_description, article_text = fetch_article_metadata(item.get("link", ""))
            story = extract_support_fields(
                article_title or title,
                article_description or item.get("snippet", ""),
                article_text,
            )
            if is_complete_support_story(story):
                candidates.append(story)

    for query in search_queries:
        claude_result = search_support_with_claude(query)
        if not claude_result or not claude_result.get("title") or not claude_result.get("link"):
            continue
        title = clean_text(claude_result["title"])
        if normalize_support_title(title) in published_titles or not is_support_candidate(title, claude_result.get("snippet", "")):
            continue
        article_title, article_description, article_text = fetch_article_metadata(claude_result["link"])
        story = extract_support_fields(
            article_title or title,
            article_description or claude_result.get("snippet", ""),
            article_text,
        )
        if is_complete_support_story(story):
            candidates.append(story)

    if not candidates:
        log_line("오늘은 적합한 후보를 못 찾았다")
        return fallback_support_story()

    story = candidates[0]
    story.update({
        "category": "정부지원금",
        "handle": "lumistoy",
        "hairline": "지원금 정보 요약",
        "summary": "한 번만 확인하면 생활비와 부담을 줄일 수 있어요.",
        "cta_bottom": "지금 조건 확인하고 신청 기한 놓치지 마세요.",
        "loss_reason": f"신청 안 하면 {story.get('benefit', '이 혜택')}, 이거 그냥 못 받는 거예요.",
        "tips": [
            "서류 하나만 빠져도 반려돼서 다시 준비해야 해요",
            "신청 기한 하루만 넘겨도 그 달치 못 받아요",
            "조건 미리 안 보면 헛걸음할 수 있어요",
        ],
        "loss_causes": [
            f"신청 안 하면 {story.get('benefit', '이 혜택')} 그대로 못 받아요",
            "기한 지나면 그 달 지원은 그냥 소멸돼요",
            "늦게 신청할수록 받는 금액도 줄어들어요",
        ],
        "comparison": "이거면 생활비 부담이 확 줄어요",
        "comment_keyword": shorten_text(str(story.get("title", "정보")), 4),
    })
    story["headline_amount"] = story.get("headline_amount") or derive_headline_amount(story.get("title", ""), story.get("benefit", ""))
    return story


def build_caption(story: dict | None = None) -> str:
    if story is None:
        story = {
            "title": "청년 월세 부담, 정부가 덜어드려요",
            "target": "청년 1인 가구, 무주택 세입자, 월세 부담이 큰 분",
            "benefit": "월 최대 20만원, 1년 한도 내 지원",
            "period": "신청 기간: 2026.09.01 ~ 2026.09.30",
            "method": "온라인 신청 → 서류 제출 → 심사 후 지급",
        }

    title = story.get("title", "정부 지원금")
    target = story.get("target", "지원 대상 확인")
    benefit = story.get("benefit", "정부 지원금 혜택 확인")
    period = story.get("period", "신청 기간 확인")
    method = story.get("method", "온라인/오프라인 신청")

    hook = f'"{title}, 이렇게 챙겨보세요?"'
    body_1 = (
        f"정부가 매년 확대하는 지원 제도를 확인해보면, {title} 같은 정책이 실질적인 생활비 부담을 줄이는 데 큰 도움이 됩니다."
    )
    body_2 = (
        "최근에는 이런 제도를 미리 알고 신청하는 사람이 실제로 혜택을 더 많이 받는 경우가 많아요. "
        "꼭 필요한 순간에 맞춰 한 번 확인해두면 훨씬 유리해요."
    )
    quality_block = (
        "📍 누가 받을 수 있나요?\n"
        f"대상: {target}\n"
        f"혜택: {benefit}\n"
        f"신청 기간: {period}\n"
        f"신청 방법: {method}"
    )
    warning_block = "주의할 점!\n예산이 소진되면 조기 마감될 수 있으니 빠르게 확인하는 게 좋아요."
    hashtags = "#정부지원금 #청년지원금 #지원금 #생활비절약 #꿀팁"
    follow_line = "* 지원금 정보, 놓치지 않으려면 팔로우 버튼 꾸욱."
    return "\n\n".join([
        hook,
        body_1,
        body_2,
        quality_block,
        warning_block,
        hashtags,
        follow_line,
    ])


def build_story(keyword: str | None = None):
    print(f"[STEP] 지원금 정보 정리 시작")
    try:
        story = choose_support_story(keyword)
        if not str(story.get("caption", "")).strip():
            story["caption"] = build_caption(story)
        else:
            story["caption"] = story["caption"].replace(
                "자녀를 둔 근로자라면 누구나 대상이에요!",
                "자녀를 둔 근로자라면 조건 맞으면 누구나 대상이에요!",
            )
        story["badge"] = pick_badge_text()
        print(f"[STEP] 지원금 정보 정리 종료")
        return story
    except Exception:
        print(f"[STEP] 지원금 정보 정리 실패")
        raise


def inject_template(template_text: str, replacements: dict) -> str:
    html = template_text
    for key, value in replacements.items():
        html = html.replace(key, value)
    OUT_DIR.mkdir(exist_ok=True)
    debug_path = OUT_DIR / "debug_cover.html"
    debug_path.write_text(html, encoding="utf-8")
    return html


def ensure_template_file(path: Path, label: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"{label} template not found: {path}")
    return path


def get_topic_keyword_map() -> dict[str, list[str]]:
    return {
        "work": ["office work desk dark", "calculator finance dark night"],
        "childcare": ["nursery baby room soft dark"],
        "housing": ["apartment building dark night"],
        "education": ["study desk books dark"],
        "default": ["city night dark minimal"],
    }


def resolve_story_theme_keywords(story: dict) -> list[str]:
    text = " ".join(
        str(value) for key in ("category", "title", "subtitle", "badge") for value in ([story.get(key)] if isinstance(story.get(key), str) else [])
    ).lower()
    keyword_map = get_topic_keyword_map()
    if any(token in text for token in ("근로", "취업", "임금", "job", "career", "wage", "salary")):
        return keyword_map["work"]
    if any(token in text for token in ("육아", "출산", "아이", "baby", "childcare", "nursery")):
        return keyword_map["childcare"]
    if any(token in text for token in ("월세", "주거", "임대", "housing", "rent", "apartment", "rental")):
        return keyword_map["housing"]
    if any(token in text for token in ("교육", "학자금", "study", "scholarship", "tuition")):
        return keyword_map["education"]
    return keyword_map["default"]


def infer_subject_keyword(story: dict) -> str:
    return resolve_story_theme_keywords(story)[0]


def build_search_queries(story: dict, slide_role: str = "cover") -> list[str]:
    base_keywords = resolve_story_theme_keywords(story)
    query_set = []
    for kw in base_keywords:
        query_set.append(kw)
        bare = re.sub(r"\b(dark|night|soft)\b", "", kw, flags=re.I)
        bare = re.sub(r"\s+", " ", bare).strip()
        if bare and bare != kw:
            query_set.append(bare)
    for kw in get_topic_keyword_map()["default"]:
        if kw not in query_set:
            query_set.append(kw)
    return query_set


def get_slide_background_image(story: dict, slide_index: int = 1, used_urls: set[str] | None = None) -> str:
    fallback_path = (BASE_DIR / "avatar.jpg").resolve()
    if not PEXELS_API_KEY:
        return fallback_path.as_uri() if fallback_path.exists() else "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80"

    used_urls = used_urls or set()
    person_tokens = (
        "people", "person", "portrait", "human", "face", "woman", "man", "girl", "boy",
        "family", "couple", "team", "group of people", "person standing",
        "hand", "hands", "finger", "fingers", "arm", "arms", "body", "figure", "legs",
        "wallet", "money", "cash", "counting money"
    )

    query_variants = build_search_queries(story, slide_role="cover" if slide_index == 1 else "body")
    if slide_index == 1:
        query_variants.insert(0, infer_subject_keyword(story))
    if slide_index > 1:
        for extra in [
            "city building exterior",
            "modern apartment exterior",
            "urban residential night",
            "minimal city architecture",
            "building facade dark",
            "housing exterior dark",
        ]:
            if extra not in query_variants:
                query_variants.append(extra)
    print(f"[PEXELS] slide_index={slide_index} subject_keyword={infer_subject_keyword(story)}")
    print(f"[PEXELS] slide_query_variants={query_variants}")

    headers = {"Authorization": PEXELS_API_KEY}
    candidates: list[dict] = []

    try:
        seen = set()
        for query in query_variants:
            if query in seen:
                continue
            seen.add(query)
            page = random.randint(1, 3)
            params = {"query": query, "per_page": 10, "page": page, "orientation": "landscape"}
            print(f"[PEXELS] calling API query={query!r} params={params}")
            response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=30)
            if response.status_code == 429:
                print(f"[PEXELS] rate limited for query={query!r}; skipping")
                continue
            response.raise_for_status()
            photos = response.json().get("photos") or []
            for photo in photos:
                photo_id = photo.get("id", "unknown")
                alt_text = (photo.get("alt") or "").lower()
                photographer = (photo.get("photographer") or "").lower()
                raw_tags = photo.get("tags") or []
                tag_values = []
                for tag in raw_tags:
                    if isinstance(tag, dict):
                        title = tag.get("title") or tag.get("name") or ""
                        if title:
                            tag_values.append(str(title))
                    elif isinstance(tag, str):
                        tag_values.append(tag)
                tag_text = " ".join(str(v) for v in tag_values).lower()
                combined_text = f"{alt_text} {tag_text} {photographer}"
                if any(token in combined_text for token in person_tokens):
                    print(f"[PEXELS] skipping person/body result id={photo_id} alt={alt_text[:80]!r} tags={tag_text[:80]!r}")
                    continue

                image_url = (
                    photo.get("src", {}).get("large2x")
                    or photo.get("src", {}).get("large")
                    or photo.get("src", {}).get("medium")
                    or photo.get("src", {}).get("original")
                )
                if not image_url:
                    continue
                if image_url in used_urls:
                    print(f"[PEXELS] skipping already-used result id={photo_id} url={image_url[:120]}")
                    continue

                width = int(photo.get("width") or 0)
                height = int(photo.get("height") or 1)
                aspect = width / max(height, 1)
                dark_bonus = 0
                if any(token in query.lower() for token in ("dark", "night", "minimal")):
                    dark_bonus += 25
                if 0.45 <= aspect <= 0.9:
                    dark_bonus += 20
                score = dark_bonus - abs(aspect - 0.75) * 120
                candidates.append({
                    "image_url": image_url,
                    "id": photo.get("id", "default"),
                    "score": score,
                    "aspect": aspect,
                    "query": query,
                })
            if len(candidates) >= 6:
                break

        best_candidate = None
        if candidates:
            candidates.sort(key=lambda c: c["score"], reverse=True)
            top_pool = candidates[:5]
            best_candidate = random.choice(top_pool)

        if best_candidate is not None:
            image_url = best_candidate["image_url"]
            print(f"[PEXELS] pool_size={len(candidates)} top_pool={[(c['id'], round(c['score'], 1)) for c in candidates[:5]]}")
            print(f"[PEXELS] selected id={best_candidate['id']} query={best_candidate['query']!r} score={best_candidate['score']:.2f} aspect={best_candidate['aspect']:.3f}")
            image_response = requests.get(image_url, timeout=60)
            image_response.raise_for_status()
            saved_path = OUT_DIR / f"pexels_slide_{slide_index}_{best_candidate['id']}.jpg"
            saved_path.parent.mkdir(exist_ok=True, parents=True)
            saved_path.write_bytes(image_response.content)
            print(f"[PEXELS] saved slide-{slide_index} background to {saved_path.name}")
            return saved_path.resolve().as_uri()
    except Exception as exc:
        log_line(f"Pexels slide background fetch failed ({slide_index}): {type(exc).__name__}: {exc}")

    print(f"[PEXELS] slide {slide_index} using fallback avatar.jpg")
    return fallback_path.as_uri() if fallback_path.exists() else "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=1200&q=80"


def render_cover_html(story: dict, accent_hex: str = "#34D399", accent_rgb: str = "52,211,153", background_url: str | None = None) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "cover-dark.html", "cover").read_text(encoding="utf-8")
    title_html, line_count, title_font_size = split_title_to_lines(story["title"])
    title_html = highlight_numbers(title_html, accent_hex)
    title_style = f"font-size: {title_font_size}px;"
    handle_value = story["handle"].lstrip("@")
    title_html = f"<span class='title-line'>{title_html}</span>"
    subtitle_html = highlight_numbers(story["subtitle"], accent_hex)
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=1),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__HANDLE__": handle_value,
        "__BADGE_TEXT__": story["badge"],
        "__TITLE__": title_html,
        "__TITLE_STYLE__": title_style,
        "__SUBTITLE__": subtitle_html,
        "__FOOTER_TEXT__": "스와이프해서 확인 →",
    }
    return inject_template(template, replacements)


def render_info_html(story: dict, accent_hex: str = "#34D399", accent_rgb: str = "52,211,153", background_url: str | None = None) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "info-card-dark.html", "info").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    body = (
        "<div class='body-text'>" + story.get("intro", "") + "</div>"
        "<div class='checklist'>"
        "<div class='row'><span class='mark'>✅</span><span>대상: <span class='mono'>" + story["target"] + "</span></span></div>"
        "<div class='row'><span class='mark'>✅</span><span>지원: <span class='mono'>" + story["benefit"] + "</span></span></div>"
        "<div class='row no'><span class='mark'>⚠️</span><span>유의: <span class='mono'>" + story["period"] + "</span></span></div>"
        "</div>"
    )
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=2),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": story["hairline"],
        "__HEADING__": f"{story.get('category', '정부지원금')} 확인 포인트",
        "__BODY_HTML__": body,
        "__SUMMARY__": story["summary"],
        "__PAGE_NUM__": "1",
        "__TOTAL_PAGES__": "4",
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_benefit_html(story: dict, accent_hex: str = "#34D399", accent_rgb: str = "52,211,153", background_url: str | None = None) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "info-card-dark.html", "benefit").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    body = (
        "<div class='checklist'>"
        "<div class='row'><span class='mark'>💵</span><span>지원금: <span class='mono'>" + shorten_text(story["benefit"], 34) + "</span></span></div>"
        "<div class='row'><span class='mark'>📅</span><span>신청기간: <span class='mono'>" + shorten_text(story["period"], 34) + "</span></span></div>"
        "<div class='row'><span class='mark'>🙋</span><span>대상: <span class='mono'>" + shorten_text(story["target"], 34) + "</span></span></div>"
        "<div class='row no'><span class='mark'>📝</span><span>신청방법: <span class='mono'>" + shorten_text(story["method"], 34) + "</span></span></div>"
        "</div>"
    )
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=3),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "혜택 확인",
        "__HEADING__": f"한 번 확인하면 달라지는 {story.get('category', '지원금')} 혜택",
        "__BODY_HTML__": body,
        "__SUMMARY__": shorten_text(story.get("cta_bottom", "지금 조건 확인하고 신청 기한 놓치지 마세요."), 32),
        "__PAGE_NUM__": "2",
        "__TOTAL_PAGES__": "4",
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_cta_html(story: dict, accent_hex: str = "#34D399", accent_rgb: str = "52,211,153", background_url: str | None = None) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "cta-follow.html", "cta").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=8),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__PAGE_NUM__": "8/8",
        "__HEADLINE__": "다음 지원금 소식도<br>바로 확인해보세요",
        "__AVATAR_HTML__": "@",
        "__HANDLE__": handle_value,
        "__GUIDE_TEXT__": "팔로우하고 최신 정책 정보 받기",
        "__SMALL_TEXT__": "<mark>지원금·대출·청년 정책</mark> 업데이트를 빠르게 받아보세요.",
    }
    return inject_template(template, replacements)


FACT_SLIDE_SPECS = [
    ("target", "🙋", "나도 받을 수 있어?", "대상 확인", "조건 맞으면 무조건 신청 가능"),
    ("benefit", "💰", "얼마 받을 수 있는데?", "혜택 확인", "가만히 있으면 그대로 증발"),
    ("period", "⏰", "언제까지 신청해야 해?", "기간 확인", "기한 지나면 칼같이 끝"),
    ("method", "📝", "어떻게 신청하는데?", "방법 확인", "생각보다 훨씬 간단해"),
]


def render_fact_slide_html(
    story: dict,
    field_key: str,
    icon: str,
    heading: str,
    label: str,
    footer_text: str,
    page_num: int,
    total_pages: int = 8,
    accent_hex: str = "#34D399",
    accent_rgb: str = "52,211,153",
    background_url: str | None = None,
) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "info-card-dark.html", f"fact-{field_key}").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    value_text = highlight_numbers(shorten_text(str(story.get(field_key, "")), 90), accent_hex)
    body = (
        "<div class='example-box'>"
        f"<div class='example-tag'>{icon} {label}</div>"
        f"<div class='example-text'>{value_text}</div>"
        "</div>"
    )
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=page_num),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": label,
        "__HEADING__": heading,
        "__BODY_HTML__": body,
        "__SUMMARY__": footer_text,
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_loss_reason_html(story: dict, accent_hex: str = "#34D399", accent_rgb: str = "52,211,153", background_url: str | None = None) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "info-card-dark.html", "loss-reason").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    benefit_match = NUMBER_HIGHLIGHT_RE.search(story.get("benefit", ""))
    benefit_amount = benefit_match.group(0) if benefit_match else "0원"
    body = (
        "<div class='compare-box'>"
        "<div class='col bad'><span class='tag'>😩 모르면</span><span class='big'>0원</span>"
        "<span class='desc'>그냥 못 받고 끝</span></div>"
        f"<div class='col good'><span class='tag'>😎 알면</span><span class='big'>{benefit_amount}</span>"
        "<span class='desc'>신청만 하면 내 돈</span></div>"
        "</div>"
        "<div class='body-text' style='margin-top:36px;'>" + highlight_numbers(shorten_text(story.get("loss_reason", ""), 120), accent_hex) + "</div>"
    )
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=6),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "놓치면 손해",
        "__HEADING__": "몰랐다는 이유로<br>손해보는 거예요",
        "__BODY_HTML__": body,
        "__SUMMARY__": shorten_text(story.get("cta_bottom", "지금 조건 확인하고 신청 기한 놓치지 마세요."), 32),
        "__PAGE_NUM__": "6",
        "__TOTAL_PAGES__": "8",
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_tips_html(story: dict, accent_hex: str = "#34D399", accent_rgb: str = "52,211,153", background_url: str | None = None) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "info-card-dark.html", "tips").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    tips = story.get("tips") or ["서류 하나만 빠져도 반려될 수 있어요", "신청 기한 놓치면 못 받아요"]
    items_html = "".join(
        f"<div class='item'><div class='num'>{idx}</div><div class='text'>{highlight_numbers(str(tip), accent_hex)}</div></div>"
        for idx, tip in enumerate(tips[:4], start=1)
    )
    body = f"<div class='numbered-list'>{items_html}</div>"
    replacements = {
        "__BG_IMAGE__": background_url or get_slide_background_image(story, slide_index=7),
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "주의사항",
        "__HEADING__": "이것만 놓치면<br>진짜 억울해요",
        "__BODY_HTML__": body,
        "__SUMMARY__": "꼼꼼히 챙겨야 놓치지 않아요",
        "__PAGE_NUM__": "7",
        "__TOTAL_PAGES__": "8",
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_cover_light_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 1, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-cover-light.html", "cover-light").read_text(encoding="utf-8")
    title_html, line_count, title_font_size = split_title_to_lines(story["title"])
    title_html = highlight_numbers_marker(title_html, accent_rgb)
    title_style = f"font-size: {title_font_size}px;"
    handle_value = story["handle"].lstrip("@")
    title_html = f"<span class='title-line'>{title_html}</span>"
    subtitle_html = highlight_numbers_marker(story["subtitle"], accent_rgb)
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__HANDLE__": handle_value,
        "__BADGE_TEXT__": story["badge"],
        "__TITLE__": title_html,
        "__TITLE_STYLE__": title_style,
        "__SUBTITLE__": subtitle_html,
        "__FOOTER_TEXT__": "스와이프해서 확인 →",
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
    }
    return inject_template(template, replacements)


def render_loss_causes_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 2, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-light.html", "loss-causes").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    causes = story.get("loss_causes") or ["신청 안 하면 혜택을 그대로 못 받아요", "기한 지나면 그냥 소멸돼요", "늦게 신청할수록 손해예요"]
    items_html = "".join(
        f"<div class='check-item'><div class='box'>✕</div><div>{highlight_numbers_marker(str(c), accent_rgb)}</div></div>"
        for c in causes[:3]
    )
    body = f"<div class='card'>{items_html}</div>"
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "손실 이유",
        "__HEADING__": "신청 안 하면<br>이런 일이 생겨요",
        "__BODY_HTML__": body,
        "__SUMMARY__": "이래서 신청 안 하면 진짜 손해예요",
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_target_confirm_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 3, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-light.html", "target-confirm").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    value_text = highlight_numbers_marker(shorten_text(str(story.get("target", "")), 140), accent_rgb)
    body = f"<div class='card'><div class='row'><span class='mark'>🙋</span><span>{value_text}</span></div></div>"
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "대상 확인",
        "__HEADING__": "이 조건, 하나라도<br>안 맞으면 제외예요",
        "__BODY_HTML__": body,
        "__SUMMARY__": "조건 다 맞아야 신청 가능해요",
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_benefit_preview_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 4, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-light.html", "benefit-preview").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    body = (
        "<div class='card'>"
        f"<div class='row'><span class='mark'>💰</span><span>{highlight_numbers_marker(shorten_text(story.get('benefit', ''), 150), accent_rgb)}</span></div>"
        f"<div class='row'><span class='mark'>📅</span><span>{highlight_numbers_marker(shorten_text(story.get('period', ''), 90), accent_rgb)}</span></div>"
        "</div>"
    )
    comparison = story.get("comparison") or "이거면 생활비 부담이 확 줄어요"
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "혜택 미리보기",
        "__HEADING__": "이런 혜택을<br>받게 됩니다",
        "__BODY_HTML__": body,
        "__SUMMARY__": shorten_text(comparison, 30),
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_method_steps_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 5, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-light.html", "method-steps").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    method_text = str(story.get("method", ""))
    steps = [s.strip(" ·") for s in re.split(r"→|->", method_text) if s.strip()]
    if len(steps) < 2:
        steps = [shorten_text(method_text, 90)]
    steps = [re.sub(r"^[①②③④⑤⑥⑦⑧⑨\d]+[.).\s]*", "", s).strip() for s in steps]
    items_html = "".join(
        f"<div class='item'><div class='num'>{idx}</div><div class='text'>{highlight_numbers_marker(shorten_text(step, 90), accent_rgb)}</div></div>"
        for idx, step in enumerate(steps[:4], start=1)
    )
    body = f"<div class='step-list'>{items_html}</div>"
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "신청 방법",
        "__HEADING__": "신청 절차는<br>이렇습니다",
        "__BODY_HTML__": body,
        "__SUMMARY__": "생각보다 훨씬 간단해요",
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_compare_light_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 6, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-light.html", "compare-light").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    won_re = re.compile(r"\d[\d,]*(?:천|만|억)원")
    benefit_amount = None
    for text in (story.get("loss_reason", ""), story.get("benefit", "")):
        won_matches = won_re.findall(text or "")
        big_matches = [m for m in won_matches if "만원" in m or "억원" in m]
        if big_matches:
            benefit_amount = big_matches[-1]
            break
        if won_matches:
            benefit_amount = won_matches[0]
            break
    if not benefit_amount:
        fallback_match = NUMBER_HIGHLIGHT_RE.search(story.get("benefit", ""))
        benefit_amount = fallback_match.group(0) if fallback_match else "0원"
    body = (
        "<div class='compare-box'>"
        "<div class='col bad'><span class='tag'>😩 신청 안 하면</span><span class='big'>0원</span>"
        "<span class='desc'>그냥 못 받고 끝</span></div>"
        f"<div class='col good'><span class='tag'>😎 신청하면</span><span class='big'>{benefit_amount}</span>"
        "<span class='desc'>조건 맞으면 내 돈</span></div>"
        "</div>"
        "<div class='body-text' style='margin-top:8px;font-size:30px;color:rgba(17,17,17,0.55);'>"
        "※ 조건을 충족해야 받을 수 있어요. 과장 없이 실제 기준 그대로예요.</div>"
        "<div class='body-text' style='margin-top:14px;'>" + highlight_numbers_marker(shorten_text(story.get("loss_reason", ""), 140), accent_rgb) + "</div>"
    )
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "놓치면 손해",
        "__HEADING__": "숫자로 보면<br>더 명확해요",
        "__BODY_HTML__": body,
        "__SUMMARY__": shorten_text(story.get("cta_bottom", "지금 조건 확인하고 신청 기한 놓치지 마세요."), 32),
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_tips_light_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 7, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-light.html", "tips-light").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    tips = story.get("tips") or ["서류 하나만 빠져도 반려될 수 있어요", "신청 기한 놓치면 못 받아요"]
    items_html = "".join(
        f"<div class='item'><div class='num'>{idx}</div><div class='text'>{highlight_numbers_marker(shorten_text(str(tip), 45), accent_rgb)}</div></div>"
        for idx, tip in enumerate(tips[:4], start=1)
    )
    body = f"<div class='step-list'>{items_html}</div>"
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__LABEL__": "주의사항",
        "__HEADING__": "이것만 놓치면<br>진짜 억울해요",
        "__BODY_HTML__": body,
        "__SUMMARY__": "꼼꼼히 챙겨야 놓치지 않아요",
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
        "__HANDLE__": handle_value,
    }
    return inject_template(template, replacements)


def render_cta_dm_html(story: dict, accent_hex: str = "#E63946", accent_rgb: str = "230,57,70", page_num: int = 8, total_pages: int = 8, handwriting_font: str = "Gaegu") -> str:
    template = ensure_template_file(TEMPLATE_DIR / "story-cta-light.html", "cta-dm").read_text(encoding="utf-8")
    handle_value = story["handle"].lstrip("@")
    keyword = story.get("comment_keyword") or "정보"
    replacements = {
        "__FONT_FACE_CSS__": get_handwriting_font_face_css(handwriting_font),
        "__HANDWRITING_FONT__": handwriting_font,
        "__ACCENT_HEX__": accent_hex,
        "__ACCENT_RGB__": accent_rgb,
        "__HEADLINE__": "지금 안 하면<br>계속 모르고 지나가요",
        "__COMMENT_KEYWORD__": keyword,
        "__DESC_TEXT__": "댓글에 남기고 지금 바로 확인하세요",
        "__GUIDE_TEXT__": "팔로우 안 하면 다음 지원금도 계속 놓쳐요",
        "__SMALL_TEXT__": '<span class="accent">지원금·대출·청년 정책</span>, 놓치기 전에 지금 팔로우하세요.',
        "__HANDLE__": handle_value,
        "__PAGE_NUM__": str(page_num),
        "__TOTAL_PAGES__": str(total_pages),
    }
    return inject_template(template, replacements)


def _bp_box_row(icon: str, label: str, desc: str = "", accent_hex: str = BLUEPRINT_RED) -> str:
    label_html = highlight_numbers_red(label, accent_hex)
    inner = f"<div class='label'>{label_html}</div>"
    if desc:
        inner += f"<div class='desc'>{highlight_numbers_red(desc, accent_hex)}</div>"
    return f"<div class='box box-row'><div class='icon'>{icon}</div><div class='text'>{inner}</div></div>"


def _bp_box_highlight(message_html: str) -> str:
    return f"<div class='box box-highlight accent-border'><div class='msg'>{message_html}</div></div>"


def render_cover_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 1, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-cover.html", "blueprint-cover").read_text(encoding="utf-8")
    title_text, _, title_font_size = split_title_to_lines(story["title"])
    title_html = highlight_numbers_red(title_text, accent_hex)
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": story.get("badge", "🔥 충격"),
        "__TITLE__": title_html,
        "__TITLE_STYLE__": f"font-size:{title_font_size}px;",
        "__SUBTITLE__": story.get("subtitle", ""),
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_loss_causes_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 2, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-content.html", "loss-causes-blueprint").read_text(encoding="utf-8")
    causes = story.get("loss_causes") or ["신청 안 하면 혜택을 그대로 못 받아요", "기한 지나면 그냥 소멸돼요", "늦게 신청할수록 손해예요"]
    icons = ["✕", "⚠️", "📉"]
    rows = "".join(_bp_box_row(icons[i % len(icons)], shorten_text(str(c), 45), "", accent_hex) for i, c in enumerate(causes[:3]))
    body = rows + _bp_box_highlight("이래서 신청 안 하면 <span class='accent'>진짜 손해</span>예요")
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": "손실 이유",
        "__HEADING__": "신청 안 하면<br><span class='accent'>이런 일</span>이 생겨요",
        "__BODY_HTML__": body,
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_target_confirm_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 3, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-content.html", "target-confirm-blueprint").read_text(encoding="utf-8")
    body = _bp_box_row("🙋", shorten_text(str(story.get("target", "")), 60), "", accent_hex)
    body += _bp_box_highlight("조건 다 맞아야 <span class='accent'>신청 가능</span>해요")
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": "대상 확인",
        "__HEADING__": "이 조건, 하나라도<br><span class='accent'>안 맞으면 제외</span>예요",
        "__BODY_HTML__": body,
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_benefit_preview_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 4, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-content.html", "benefit-preview-blueprint").read_text(encoding="utf-8")
    body = _bp_box_row("💰", shorten_text(str(story.get("benefit", "")), 100), "", accent_hex)
    body += _bp_box_row("📅", shorten_text(str(story.get("period", "")), 40), "", accent_hex)
    comparison = story.get("comparison") or "이거면 생활비 부담이 확 줄어요"
    body += _bp_box_highlight(highlight_numbers_red(shorten_text(comparison, 30), accent_hex))
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": "혜택 미리보기",
        "__HEADING__": "이런 <span class='accent'>혜택</span>을<br>받게 돼요",
        "__BODY_HTML__": body,
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_method_steps_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 5, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-content.html", "method-steps-blueprint").read_text(encoding="utf-8")
    method_text = str(story.get("method", ""))
    steps = [s.strip(" ·") for s in re.split(r"→|->", method_text) if s.strip()]
    if len(steps) < 2:
        steps = [shorten_text(method_text, 90)]
    steps = [re.sub(r"^[①②③④⑤⑥⑦⑧⑨\d]+[.).\s]*", "", s).strip() for s in steps]

    step_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
    risk_note = None
    rows = []
    for idx, step in enumerate(steps[:4], start=1):
        main_part = step
        if "—" in step:
            main_part, _, risk_part = step.partition("—")
            main_part = main_part.strip()
            if risk_note is None:
                risk_note = risk_part.strip(" —")
        desc_html = highlight_numbers_red(shorten_text(main_part, 45), accent_hex)
        rows.append(
            "<div class='stack-row'>"
            f"<div class='stack-index'>{idx}</div>"
            f"<div class='stack-info'><div class='stack-icon'>{step_emojis[idx - 1]}</div><div class='stack-desc'>{desc_html}</div></div>"
            "</div>"
        )

    if len(steps) <= 4:
        grid_html = f"<div class='stack-list'>{''.join(rows)}</div>"
    else:
        cells = []
        for idx, step in enumerate(steps[:4], start=1):
            main_part = step
            if "—" in step:
                main_part, _, risk_part = step.partition("—")
                main_part = main_part.strip()
                if risk_note is None:
                    risk_note = risk_part.strip(" —")
            desc_html = highlight_numbers_red(shorten_text(main_part, 45), accent_hex)
            cells.append(
                "<div class='cell'>"
                f"<div class='icon'>{step_emojis[idx - 1]}</div>"
                f"<div class='label'>STEP {idx}</div>"
                f"<div class='desc'>{desc_html}</div>"
                "</div>"
            )
        grid_html = f"<div class='grid-2x2'>{''.join(cells)}</div>"
    highlight_msg = f"<span class='accent'>{highlight_numbers_red(shorten_text(risk_note, 40), accent_hex)}</span>" if risk_note else "순서대로만 하면 <span class='accent'>어렵지 않아요</span>"
    body = grid_html + _bp_box_highlight(highlight_msg)
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": "신청 방법",
        "__HEADING__": "신청 절차는<br>이렇게 돼요",
        "__BODY_HTML__": body,
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_compare_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 6, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-content.html", "compare-blueprint").read_text(encoding="utf-8")
    benefit_amount = story.get("headline_amount") or derive_headline_amount(str(story.get("title", "")), str(story.get("benefit", "")))

    stat_row = (
        "<div class='stat-row'>"
        "<div class='stat'><div class='value'>0원</div><div class='divider'></div><div class='label'>신청 안 하면</div></div>"
        f"<div class='stat'><div class='value' style='color:{accent_hex};'>{benefit_amount}</div><div class='divider'></div><div class='label'>신청하면</div></div>"
        "</div>"
    )
    note = "<div class='note-text' style='text-align:center;'>※ 조건을 충족해야 받을 수 있어요. 과장 없이 실제 기준 그대로예요.</div>"
    highlight = _bp_box_highlight(highlight_numbers_red(shorten_text(story.get("loss_reason", ""), 140), accent_hex))
    body = stat_row + note + highlight
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": "놓치면 손해",
        "__HEADING__": "숫자로 보면<br><span class='accent'>더 명확</span>해요",
        "__BODY_HTML__": body,
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_tips_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 7, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-content.html", "tips-blueprint").read_text(encoding="utf-8")
    tips = story.get("tips") or ["서류 하나만 빠져도 반려될 수 있어요", "신청 기한 놓치면 못 받아요"]
    icons = ["⚠️", "📌", "🕐"]
    rows = "".join(_bp_box_row(icons[i % len(icons)], shorten_text(str(t), 45), "", accent_hex) for i, t in enumerate(tips[:3]))
    body = rows + _bp_box_highlight("이것만 지키면 <span class='accent'>억울할 일</span> 없어요")
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": "주의사항",
        "__HEADING__": "이것만 놓치면<br><span class='accent'>진짜 억울</span>해요",
        "__BODY_HTML__": body,
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_cta_blueprint_html(story: dict, accent_hex: str = BLUEPRINT_RED, page_num: int = 8, total_pages: int = 8) -> str:
    template = ensure_template_file(TEMPLATE_DIR / "blueprint-cta.html", "cta-blueprint").read_text(encoding="utf-8")
    keyword = story.get("comment_keyword") or "정보"
    badge_text = "🚨 긴급"
    replacements = {
        "__FONT_FACE_CSS__": get_blueprint_font_faces_css(),
        "__ACCENT_HEX__": accent_hex,
        "__KICKER_TEXT__": badge_text,
        "__HEADLINE__": "지금 안 하면<br><span class='accent'>계속 모르고</span> 지나가요",
        "__EXPLAIN_TEXT__": "댓글 남기면 다음 콘텐츠에 반영해요",
        "__COMMENT_LEAD__": f"댓글에 <span class='accent'>'{keyword}'</span> 남겨주세요",
        "__DESC_TEXT__": "다음 카드뉴스에서 더 자세히 다뤄드릴게요",
        "__GUIDE_TEXT__": f"지원금·대출·청년 정책, <span class='accent'>지금 팔로우</span>하고 놓치지 마세요",
        "__PAGE_NUM__": f"{page_num:02d}",
        "__TOTAL_PAGES__": f"{total_pages:02d}",
    }
    return inject_template(template, replacements)


def render_slides_blueprint(story: dict | None = None, out_prefix: str = "bp_slide") -> list[tuple[str, Path]]:
    """참고 이미지 스타일(블랙 테두리 박스 + 레드 단일 포인트 컬러) 신규 템플릿 렌더러.
    기존 render_slides()/story-light.html 은 건드리지 않는다."""
    print(f"[STEP] 블루프린트 템플릿 채우기 시작")
    try:
        if story is None:
            story = build_story()

        accent_hex = BLUEPRINT_RED
        htmls = [
            render_cover_blueprint_html(story, accent_hex=accent_hex, page_num=1),
            render_loss_causes_blueprint_html(story, accent_hex=accent_hex, page_num=2),
            render_target_confirm_blueprint_html(story, accent_hex=accent_hex, page_num=3),
            render_benefit_preview_blueprint_html(story, accent_hex=accent_hex, page_num=4),
            render_method_steps_blueprint_html(story, accent_hex=accent_hex, page_num=5),
            render_compare_blueprint_html(story, accent_hex=accent_hex, page_num=6),
            render_tips_blueprint_html(story, accent_hex=accent_hex, page_num=7),
            render_cta_blueprint_html(story, accent_hex=accent_hex, page_num=8),
        ]
        OUT_DIR.mkdir(exist_ok=True)
        outputs = []
        truncated_slides = []
        print(f"[STEP] Playwright 캡처 시작")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    timeout=30000,
                    args=["--allow-file-access-from-files", "--disable-web-security"],
                )
                try:
                    for index, html in enumerate(htmls, 1):
                        if "…" in html or "..." in html:
                            truncated_slides.append(index)
                        out_path = OUT_DIR / f"{out_prefix}_{index}.png"
                        html_path = OUT_DIR / f"{out_prefix}_{index}.html"
                        html_path.write_text(html, encoding="utf-8")
                        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
                        try:
                            page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded", timeout=30000)
                        except Exception as exc:
                            raise RuntimeError(f"Playwright file load timed out for slide {index}: {html_path}") from exc
                        try:
                            page.evaluate("document.fonts.ready")
                        except Exception as exc:
                            log_line(f"document.fonts.ready wait failed for slide {index}: {type(exc).__name__}: {exc}")
                        try:
                            page.screenshot(path=str(out_path), full_page=False, timeout=30000)
                        except Exception as exc:
                            raise RuntimeError(f"Playwright screenshot timed out for slide {index}: {out_path}") from exc
                        outputs.append((html, out_path))
                finally:
                    browser.close()
        except Exception as exc:
            raise RuntimeError(f"Playwright capture failed: {exc}") from exc
        finally:
            print(f"[STEP] Playwright 캡처 종료")
        if truncated_slides:
            print(f"[TRUNCATION CHECK] '…'로 잘린 슬라이드 발견: {truncated_slides} (prefix={out_prefix})")
        else:
            print(f"[TRUNCATION CHECK] 잘린 슬라이드 없음 (prefix={out_prefix})")
        print(f"[STEP] 블루프린트 템플릿 채우기 종료")
        return outputs
    except Exception:
        print(f"[STEP] 블루프린트 템플릿 채우기 실패")
        raise


def render_slides(
    story: dict | None = None,
    handwriting_font: str = "Gaegu",
    out_prefix: str = "slide",
    accent_hex: str | None = None,
    accent_rgb: str | None = None,
) -> list[tuple[str, Path]]:
    print(f"[STEP] HTML 템플릿 채우기 시작")
    try:
        if story is None:
            story = build_story()

        if accent_hex is None or accent_rgb is None:
            accent_hex, accent_rgb = pick_accent_color()
        print(f"[STEP] 포인트 컬러 선택: {accent_hex}")
        print(f"[STEP] 손글씨 폰트 선택: {handwriting_font}")
        kw = {"accent_hex": accent_hex, "accent_rgb": accent_rgb, "handwriting_font": handwriting_font}
        htmls = [
            render_cover_light_html(story, page_num=1, **kw),
            render_loss_causes_html(story, page_num=2, **kw),
            render_target_confirm_html(story, page_num=3, **kw),
            render_benefit_preview_html(story, page_num=4, **kw),
            render_method_steps_html(story, page_num=5, **kw),
            render_compare_light_html(story, page_num=6, **kw),
            render_tips_light_html(story, page_num=7, **kw),
            render_cta_dm_html(story, page_num=8, **kw),
        ]
        OUT_DIR.mkdir(exist_ok=True)
        outputs = []
        truncated_slides = []
        print(f"[STEP] Playwright 캡처 시작")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    timeout=30000,
                    args=["--allow-file-access-from-files", "--disable-web-security"],
                )
                try:
                    for index, html in enumerate(htmls, 1):
                        if "…" in html or "..." in html:
                            truncated_slides.append(index)
                        out_path = OUT_DIR / f"{out_prefix}_{index}.png"
                        html_path = OUT_DIR / f"{out_prefix}_{index}.html"
                        html_path.write_text(html, encoding="utf-8")
                        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
                        try:
                            page.goto(html_path.resolve().as_uri(), wait_until="domcontentloaded", timeout=30000)
                        except Exception as exc:
                            raise RuntimeError(f"Playwright file load timed out for slide {index}: {html_path}") from exc
                        try:
                            page.evaluate("document.fonts.ready")
                        except Exception as exc:
                            log_line(f"document.fonts.ready wait failed for slide {index}: {type(exc).__name__}: {exc}")
                        try:
                            page.screenshot(path=str(out_path), full_page=False, timeout=30000)
                        except Exception as exc:
                            raise RuntimeError(f"Playwright screenshot timed out for slide {index}: {out_path}") from exc
                        outputs.append((html, out_path))
                finally:
                    browser.close()
        except Exception as exc:
            raise RuntimeError(f"Playwright capture failed: {exc}") from exc
        finally:
            print(f"[STEP] Playwright 캡처 종료")
        if truncated_slides:
            print(f"[TRUNCATION CHECK] '…'로 잘린 슬라이드 발견: {truncated_slides} (prefix={out_prefix})")
        else:
            print(f"[TRUNCATION CHECK] 잘린 슬라이드 없음 (prefix={out_prefix})")
        print(f"[STEP] HTML 템플릿 채우기 종료")
        return outputs
    except Exception:
        print(f"[STEP] HTML 템플릿 채우기 실패")
        raise


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
    except Exception:
        return None
    if not isinstance(history, list):
        return None

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


def main():
    parser = argparse.ArgumentParser(description="정부 지원금 카드뉴스 생성 및 발행")
    parser.add_argument("--keyword", help="Claude Code CLI로 검색할 지원금 키워드")
    args = parser.parse_args()
    try:
        log_line("START publish_pipeline")
        step_log("지원금 정보 정리", "시작")
        story = build_story(args.keyword)
        safe_console_print(json.dumps(story, ensure_ascii=False, indent=2))
        step_log("지원금 정보 정리", "종료")
        auto_publish = os.environ.get("IG_AUTO_PUBLISH") == "1" or not sys.stdin.isatty()
        if auto_publish:
            log_line("자동 발행 모드(예약 실행 또는 IG_AUTO_PUBLISH=1): 확인 프롬프트 생략하고 진행")
        else:
            answer = input("발행하시겠습니까? (y/n) ").strip().lower()
            if answer != "y":
                log_line("사용자 취소: 발행하지 않음")
                return
        if story.get("publishable") is False:
            log_line("발행 중단: 적합한 지원금 후보가 없어 안전한 fallback으로 종료")
            return

        duplicate = find_recent_duplicate_publish(story.get("caption", ""))
        if duplicate:
            log_line(
                f"발행 중단: 최근 24시간 이내 사실상 동일한 내용으로 이미 발행됨 "
                f"(이전 발행: {duplicate.get('created_at', '?')}, post_id={duplicate.get('published_post_id', '?')})"
            )
            return

        ensure_config()
        step_log("HTML 템플릿 채우기", "시작")
        slide_outputs = render_slides_blueprint(story)
        step_log("HTML 템플릿 채우기", "종료")
        log_line(f"Rendered {len(slide_outputs)} slide PNGs to {OUT_DIR}")
        uploaded_urls = []
        for _, slide_path in slide_outputs:
            image_url = sign_cloudinary_upload(slide_path)
            uploaded_urls.append(image_url)
            log_line(f"Cloudinary uploaded {slide_path.name}: {image_url}")

        step_log("Instagram 발행", "시작")
        caption = story["caption"]
        item_ids = [create_item_container(url, caption=caption) for url in uploaded_urls]
        log_line(f"Created item containers: {item_ids}")

        carousel_id = create_carousel_container(item_ids, caption)
        log_line(f"Created carousel container ID: {carousel_id}")

        published_post_id = publish_container(carousel_id, caption=caption)
        log_line(f"PUBLISHED POST ID: {published_post_id}")
        step_log("Instagram 발행", "종료")

        # 여기 도달했다면 실제로 게시가 완료된 것이다(publish_container가 에러 응답을
        # 받아도 재확인 후 실제 게시가 확인되면 예외 없이 반환한다). 기록 저장 실패는
        # 발행 자체의 실패와 분리해서 다룬다.
        try:
            entry = {
                "created_at": datetime.utcnow().isoformat() + "Z",
                "title": story["title"],
                "caption": caption,
                "slides": [str(p) for _, p in slide_outputs],
                "cloudinary_urls": uploaded_urls,
                "item_ids": item_ids,
                "carousel_id": carousel_id,
                "published_post_id": published_post_id,
            }
            log_path = BASE_DIR / "published_log.json"
            history = []
            if log_path.exists():
                try:
                    history = json.loads(log_path.read_text(encoding="utf-8"))
                except Exception:
                    history = []
            history.append(entry)
            log_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            log_line(f"Wrote publish record to {log_path}")
        except Exception as log_exc:
            log_line(f"발행은 완료됐지만({published_post_id}) 기록 저장 실패: {type(log_exc).__name__}: {log_exc}")
        log_line("END publish_pipeline")
    except Exception as exc:
        log_line(f"ERROR: {type(exc).__name__}: {exc}")
        try:
            safe_console_print(traceback.format_exc())
        except Exception:
            safe_console_print(f"ERROR: {type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
