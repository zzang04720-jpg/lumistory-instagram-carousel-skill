"""LumiStory skill article -> reviewable Instagram carousel images.

This module never calls the Instagram API. Publishing is kept in
``lumistory_publish.py`` so previewing a card cannot accidentally post it.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
SITE = os.environ.get("SITE_URL", "").strip().rstrip("/")
if not SITE.startswith("https://"):
    raise RuntimeError("SITE_URL is not set. Add SITE_URL=https://your-site.example to .env (see .env.example).")
RSS = f"{SITE}/rss.xml"
OUTPUT = BASE_DIR / "out" / "lumistory"
FONT_DIR = BASE_DIR / "lumistory_fonts"
WIDTH, HEIGHT = 1080, 1350


@dataclass(frozen=True)
class Article:
    url: str
    slug: str
    title: str
    eyebrow: str
    description: str
    one_line: str
    why: str
    scenes: list[str]
    not_for: str
    steps: list[str]
    outcomes: list[str]
    download_url: str | None


@dataclass(frozen=True)
class Slide:
    kind: str
    kicker: str
    title: str
    lines: list[str]


THEMES = [
    ("마커 손그림", "nanumbrushscript", "#FFF8E9", "#151515", "#E24642", "#FFE15B"),
    ("다크 터미널", "dohyeon", "#101824", "#F5F7FA", "#6FE6A1", "#26384C"),
    ("포스트잇", "dongle", "#F2EBDC", "#1A1918", "#E84860", "#FFD65C"),
    ("만화 패널", "jua", "#FFFDF5", "#171717", "#F25B52", "#FFE052"),
    ("블루프린트", "gugi", "#10509A", "#FFFFFF", "#FFE052", "#1E65B6"),
    ("공책 필기", "gaegu-bold", "#FFFCF2", "#1D2734", "#E65050", "#D9EDFF"),
    ("영수증", "singleday", "#E75B4D", "#191919", "#E75B4D", "#FFFDF4"),
    ("채팅 대화", "himelody", "#EEE9FF", "#241958", "#5D43BA", "#FFE15C"),
    ("달력 플래너", "sunflower", "#F5F6F1", "#1A322D", "#289C72", "#D9F2E6"),
    ("매거진 타이포", "blackhansans", "#181818", "#FFFFFF", "#FFDA46", "#E9514A"),
]


def _normalize(value: str) -> str:
    # A few display fonts deliberately contain only Korean/Latin letter forms.
    # Normalise punctuation here so a missing glyph never becomes a □ on a card.
    value = (value or "").translate(str.maketrans({
        "“": "", "”": "", "‘": "", "’": "", "·": "/", "→": "다음",
    }))
    return " ".join(value.split())


def _article_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != urlparse(SITE).netloc:
        raise ValueError("루미스토리 사이트의 HTTPS 글 주소만 사용할 수 있습니다.")
    if not re.fullmatch(r"/skills/[a-z0-9-]+/", parsed.path):
        raise ValueError("/skills/ 아래의 스킬 소개 글만 사용할 수 있습니다.")
    return f"{SITE}{parsed.path}"


def list_articles(session: requests.Session | None = None) -> list[dict[str, str]]:
    client = session or requests.Session()
    response = client.get(RSS, timeout=20)
    response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    articles = []
    for item in root.findall("./channel/item"):
        url = _normalize(item.findtext("link") or "")
        try:
            url = _article_url(url)
        except ValueError:
            continue
        articles.append({
            "url": url,
            "title": _normalize(item.findtext("title") or ""),
            "description": _normalize(item.findtext("description") or ""),
        })
    return articles


def _section_items(soup: BeautifulSoup, heading: str) -> list[str]:
    for node in soup.select("article h2, article h3"):
        if _normalize(node.get_text(" ", strip=True)) != heading:
            continue
        parent = node.parent
        if parent is None:
            continue
        items = parent.find_all("li", recursive=False)
        if not items:
            ul = parent.find("ul", recursive=False) or parent.find("ol", recursive=False)
            items = ul.find_all("li", recursive=False) if ul else []
        return [_normalize(item.get_text(" ", strip=True)) for item in items]
    return []


def fetch_article(url: str, session: requests.Session | None = None) -> Article:
    url = _article_url(url)
    client = session or requests.Session()
    response = client.get(url, timeout=20)
    response.raise_for_status()
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    def one(selector: str) -> str:
        element = soup.select_one(selector)
        return _normalize(element.get_text(" ", strip=True)) if element else ""

    def easy_block(heading: str) -> tuple[str, list[str]]:
        for block in soup.select("section.easy .easy-block"):
            label = block.find("h3")
            if label and _normalize(label.get_text(" ", strip=True)) == heading:
                paragraph = block.find("p")
                items = block.select("li")
                return (
                    _normalize(paragraph.get_text(" ", strip=True)) if paragraph else "",
                    [_normalize(item.get_text(" ", strip=True)) for item in items],
                )
        return "", []

    why, _ = easy_block("왜 필요한가요?")
    _, scenes = easy_block("이럴 때 도움이 돼요")
    not_for, _ = easy_block("이런 분은 안 써도 괜찮아요")
    steps = _section_items(soup, "따라 하기")
    outcomes = _section_items(soup, "이렇게 되면 성공이에요")
    link = soup.select_one(".skill-download a.file-button")
    download = None
    if link and link.get("href", "").startswith("/downloads/"):
        download = SITE + link["href"]
    article = Article(
        url=url,
        slug=urlparse(url).path.strip("/").split("/")[-1],
        title=one(".skill-hero h1"),
        eyebrow=one(".skill-hero .kicker"),
        description=one(".skill-hero .lead"),
        one_line=one("section.easy .easy-one p"),
        why=why,
        scenes=scenes,
        not_for=not_for,
        steps=steps,
        outcomes=outcomes,
        download_url=download,
    )
    if not all([article.title, article.description, article.one_line, article.why, article.scenes]):
        raise ValueError("사이트 글의 필수 설명을 읽지 못했습니다. 게시하지 않고 중단합니다.")
    return article


def _short(value: str, limit: int = 86) -> str:
    value = _normalize(value)
    if len(value) <= limit:
        return value
    cut = value[:limit].rsplit(" ", 1)[0]
    return (cut or value[:limit]).rstrip("., ") + "…"


def build_slides(article: Article) -> list[Slide]:
    if article.slug == "automate-this":
        # The source page itself names report copy/paste, bulk file renaming,
        # and moving web data into tables. Lead with those recognisable pains
        # instead of a generic summary so the first card earns the swipe.
        return [
            Slide("cover", "STOP SCROLLING", "AI 쓰는데도\n아직 야근하세요?", [
                "ChatGPT를 켜도 일이 안 줄어드는 진짜 이유",
            ]),
            Slide("body", "01 / HARD TRUTH", "채팅만 하면\n자동화가 아닙니다", [
                "내 업무에 AI를 붙이지 못하면, 결국 내가 계속 복사하고 붙여넣게 됩니다.",
            ]),
            Slide("body", "02 / CHECK YOUR WORK", "이 3개 아직\n직접 하고 있어요?", [
                "보고서 파일 열고 복사·붙여넣기",
                "폴더 안 파일 이름 하나씩 바꾸기",
                "사이트 자료를 표에 옮겨 적기",
            ]),
            Slide("body", "03 / THE TURNING POINT", "설명하지 말고\n화면을 보여주세요", [
                "처음부터 끝까지 작업 화면을 한 번 녹화",
                "AI가 업무 순서를 먼저 읽도록 만들기",
                "자동화할 수 있는 작은 일부터 찾기",
            ]),
            Slide("body", "04 / START SMALL", "하나만 줄어도\n매주는 달라집니다", [
                "첫날부터 전부 바꾸지 마세요. 가장 자주 반복하는 한 작업부터 시험하면 됩니다.",
            ]),
            Slide("body", "05 / FREE GUIDE", "일 잘하는 사람은\n이렇게 시킵니다", [
                "AI에게 보여줄 업무 화면 고르기",
                "처음 보내는 요청 문장",
                "실행 전 확인할 체크포인트",
            ]),
            Slide("cta", "FREE SKILL GUIDE", "무료 가이드\n받는 방법", [
                "루미스토리 인스타그램 팔로우",
                "댓글에 무료파일이라고 남기기",
                "DM으로 가이드 링크 받기",
            ]),
        ]
    # Claims on cards are direct, shortened excerpts from the published page.
    # Headings are editorial signposts, not additional factual claims.
    source_title = article.eyebrow or article.title
    slides = [
        Slide("cover", "LUMIESTORY / AI SKILL", _short(source_title, 34), [_short(article.description, 86)]),
        Slide("body", "01 · WHY", "왜 이 스킬이 필요할까?", [_short(article.why, 170)]),
        Slide("body", "02 · FOR YOU", "이런 일을 한다면", [_short(x, 78) for x in article.scenes[:3]]),
        Slide("body", "03 · WHAT", "AI가 도와주는 부분", [_short(article.one_line, 150)]),
        Slide("body", "04 · HOW", "시작은 이렇게", [_short(x, 83) for x in article.steps[:3]] or [_short(article.one_line, 105)]),
        Slide("body", "05 · CHECK", "시작 전 꼭 확인", [_short(article.not_for, 155)] if article.not_for else [_short(article.description, 100)]),
    ]
    if article.download_url:
        slides.append(Slide("cta", "FREE SKILL GUIDE", "무료 가이드, 팔로우하고 댓글", [
            "루미스토리 인스타그램 팔로우",
            "댓글에 무료파일이라고 남기기",
            "DM으로 사이트 링크 받기",
        ]))
    else:
        slides.append(Slide("cta", "LUMIESTORY GUIDE", "설치·사용법은 사이트에서", [
            f"루미스토리에서 ‘{article.title}’ 글 열기",
            "이 글에는 무료 ZIP 보관본이 없습니다",
            "원본 링크와 설치 안내를 확인해 주세요",
        ]))
    return slides


def build_caption(article: Article) -> str:
    if article.slug == "automate-this":
        return (
            "AI를 쓰는데도 일이 안 줄어든다면, AI가 아니라 ‘사용 방식’이 문제일 수 있습니다.\n\n"
            "ChatGPT를 켜고 질문하는 것만으로는 반복 업무가 사라지지 않아요.\n"
            "내가 실제로 하는 작업을 AI가 볼 수 있어야, 어디부터 줄일지 함께 정리할 수 있습니다.\n\n"
            "긴 설명 대신 작업 화면을 처음부터 끝까지 한 번 녹화해 보세요.\n"
            "그다음 가장 작은 반복 작업 하나부터 자동화 가능성을 확인하면 됩니다.\n\n"
            "✓ 매주 보고서 파일 복사·붙여넣기\n"
            "✓ 폴더 안 파일 이름 바꾸기\n"
            "✓ 사이트 자료를 표에 옮겨 적기\n\n"
            "팔로우한 뒤 댓글에 무료파일이라고 남겨 주세요.\n"
            "DM으로 가이드 링크를 보내드려요.\n\n"
            "#루미스토리 #AI스킬 #업무자동화 #반복업무 #AI활용"
        )
    intro = _short(article.eyebrow or article.title, 70)
    scenes = "\n".join(f"• {_short(scene, 70)}" for scene in article.scenes[:3])
    action = (
        "무료 파일 안내와 설치 방법은 아래 루미스토리 글에서 확인할 수 있어요."
        if article.download_url else "이 글에는 사이트 ZIP 보관본이 없습니다. 설치 방법과 원본 링크를 확인해 주세요."
    )
    return (
        f"{intro}\n\n"
        f"이런 일에 도움이 되는 스킬입니다.\n{scenes}\n\n"
        f"{_short(article.one_line, 180)}\n\n"
        f"{action}\n{article.url}\n\n"
        "팔로우한 뒤 댓글에 무료파일이라고 남겨 주세요. DM으로 이 글 링크를 보내드려요.\n\n"
        "원문을 읽고 정리한 안내이며, 실제 실행 결과를 보장하지 않습니다.\n"
        "#루미스토리 #AI스킬 #업무자동화 #AI활용 #스킬가이드"
    )


def _font(theme_index: int, size: int, body: bool = False) -> ImageFont.FreeTypeFont:
    name = "jua" if body else THEMES[theme_index][1]
    path = FONT_DIR / f"{name}.ttf"
    if not path.exists():
        raise FileNotFoundError(f"글꼴 파일이 없습니다: {path}")
    return ImageFont.truetype(str(path), size)


def _wrap(draw: ImageDraw.ImageDraw, value: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(value).splitlines():
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=font) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines or [""]


def _fit(draw: ImageDraw.ImageDraw, value: str, theme: int, max_width: int, max_height: int,
         start_size: int, body: bool = False, min_size: int = 34) -> tuple[ImageFont.FreeTypeFont, list[str], int]:
    for size in range(start_size, min_size - 1, -2):
        font = _font(theme, size, body)
        lines = _wrap(draw, value, font, max_width)
        step = round(size * 1.28)
        if len(lines) * step <= max_height and max(draw.textlength(x, font=font) for x in lines) <= max_width:
            return font, lines, step
    raise ValueError("카드에 글이 너무 길어 들어가지 않습니다. 문구를 줄여 주세요.")


def _write(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str], font: ImageFont.FreeTypeFont,
           fill: str, step: int, stroke: int = 0) -> int:
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill, stroke_width=stroke, stroke_fill=fill)
        y += step
    return y


def _background(theme_index: int, slide_index: int) -> tuple[Image.Image, ImageDraw.ImageDraw, tuple]:
    _, _, bg, ink, accent, soft = THEMES[theme_index]
    im = Image.new("RGB", (WIDTH, HEIGHT), bg)
    d = ImageDraw.Draw(im)
    if theme_index == 0:  # marker / imperfect highlighter bars
        d.polygon([(58, 175), (1010, 163), (1021, 245), (69, 258)], fill=soft)
        for x, y in [(65, 55), (1015, 55), (65, 1295), (1015, 1295)]:
            dx = 70 if x < 500 else -70
            dy = 70 if y < 500 else -70
            d.line([(x + dx, y), (x, y), (x, y + dy)], fill=accent, width=9, joint="curve")
    elif theme_index == 1:  # terminal
        d.rounded_rectangle((48, 48, 1032, 1298), radius=34, fill="#182638", outline="#47617D", width=4)
        d.rounded_rectangle((48, 48, 1032, 145), radius=32, fill="#2B3D52")
        for x, color in [(105, "#FB6A62"), (151, "#FFD15C"), (197, "#63D7A0")]:
            d.ellipse((x-14, 84, x+14, 112), fill=color)
    elif theme_index == 2:  # sticky notes
        d.polygon([(75, 105), (995, 84), (1010, 1240), (98, 1263)], fill="#FFFDF2")
        d.polygon([(448, 79), (650, 74), (665, 135), (457, 139)], fill="#D9BD86")
    elif theme_index == 3:  # comic
        d.rectangle((52, 52, 1028, 1298), outline=ink, width=10)
        d.line((52, 276, 1028, 276), fill=ink, width=10)
        d.polygon([(925, 154), (955, 98), (977, 155), (1030, 180), (974, 204), (949, 260), (928, 205), (878, 180)], fill=accent)
    elif theme_index == 4:  # blueprint
        for x in range(0, WIDTH, 108):
            d.line((x, 0, x, HEIGHT), fill="#2869B0", width=2)
        for y in range(0, HEIGHT, 108):
            d.line((0, y, WIDTH, y), fill="#2869B0", width=2)
        d.rectangle((50, 50, 1030, 1300), outline="#AFDFFF", width=5)
    elif theme_index == 5:  # notebook
        for y in range(120, HEIGHT, 90):
            d.line((0, y, WIDTH, y), fill="#BED9F0", width=3)
        d.line((139, 0, 139, HEIGHT), fill=accent, width=6)
        for y in range(90, HEIGHT, 330):
            d.ellipse((54, y, 96, y+42), fill="#455A70")
    elif theme_index == 6:  # receipt
        d.rectangle((147, 40, 933, 1295), fill=soft)
        for x in range(158, 924, 45):
            d.polygon([(x, 1296), (x+22, 1265), (x+44, 1296)], fill=bg)
        d.line((200, 235, 882, 235), fill=ink, width=4)
        d.line((200, 1110, 882, 1110), fill=ink, width=4)
    elif theme_index == 7:  # chat
        d.rounded_rectangle((55, 52, 1025, 145), radius=46, fill=accent)
        d.ellipse((80, 73, 129, 122), fill=soft)
    elif theme_index == 8:  # calendar
        d.rounded_rectangle((62, 60, 1018, 1294), radius=30, fill="#FFFFFF", outline="#A4C9B9", width=4)
        d.rounded_rectangle((62, 60, 1018, 206), radius=30, fill=accent)
        for x in (230, 845):
            d.rounded_rectangle((x, 40, x+28, 104), radius=12, fill="#1A5B48")
    else:  # magazine
        d.rectangle((0, 0, 1080, 290), fill="#252525")
        d.rectangle((56, 323, 1024, 340), fill=accent)
        d.rectangle((56, 1195, 1024, 1212), fill=soft)
    return im, d, (bg, ink, accent, soft)


def render_slide(slide: Slide, theme_number: int, index: int, total: int) -> Image.Image:
    if not 1 <= theme_number <= 10:
        raise ValueError("템플릿 번호는 1~10이어야 합니다.")
    t = theme_number - 1
    im, d, (bg, ink, accent, soft) = _background(t, index)
    left = 205 if t == 6 else 192 if t == 5 else 100
    right = 866 if t == 6 else 946
    avail = right - left
    top = 298 if t in (3, 8, 9) else 210 if t == 1 else 235
    if t == 8:
        top = 325
    if t == 7:
        top = 245
    # Header, title, content and footer form the same reading order across
    # styles, while motif, palette and actual Korean headline face all rotate.
    label_fill = ink if t not in (4, 9) else accent
    d.text((left, top), slide.kicker, font=_font(3, 37, body=True), fill=label_fill)
    if t == 7:
        d.rounded_rectangle((left-20, top+76, right+13, top+507), radius=38, fill="#FFFFFF")
    title_top = top + 96
    title_max = 420 if slide.kind == "cover" else 380
    f, lines, step = _fit(d, slide.title, t, avail, title_max, 106 if slide.kind == "cover" else 86,
                          min_size=58 if slide.kind == "cover" else 48)
    title_bottom = _write(d, (left, title_top), lines, f, ink, step, 2 if t in (0, 2, 5, 7) else 1)
    line_y = title_bottom + 24
    d.line((left, line_y, right, line_y), fill=accent, width=11 if slide.kind == "cover" else 6)

    body_top = line_y + 55
    available_height = 1040 - body_top
    values = [v for v in slide.lines if _normalize(v)]
    if not values:
        raise ValueError("내용이 없는 슬라이드는 만들지 않습니다.")
    if len(values) == 1:
        body_text = values[0]
        bf, wrapped, bs = _fit(d, body_text, t, avail-50, available_height, 56 if slide.kind == "cover" else 55,
                               body=True, min_size=30)
        if t in (0, 2, 3, 5, 7, 8):
            d.rounded_rectangle((left-15, body_top-15, right+15, body_top+len(wrapped)*bs+26),
                                radius=27, fill=soft if t != 7 else "#FFE15C")
        _write(d, (left+17, body_top+5), wrapped, bf, ink, bs)
    else:
        gap = 19
        card_height = min(166, (available_height - (len(values)-1)*gap) // len(values))
        if card_height < 82:
            raise ValueError("항목이 너무 많아 카드에 들어가지 않습니다.")
        for j, value in enumerate(values):
            y = body_top + j * (card_height + gap)
            card_bg = ("#FFFFFF" if t in (1, 3, 7, 8) else soft)
            if t in (4, 9):
                card_bg = "#2464AB" if t == 4 else "#292929"
            d.rounded_rectangle((left, y, right, y+card_height), radius=24,
                                fill=card_bg, outline=accent if t in (3, 6, 9) else None, width=4)
            num_font = _font(3, 35, body=True)
            d.text((left+24, y+25), f"{j+1:02d}", font=num_font, fill=accent)
            bf, wrapped, bs = _fit(d, value, t, avail-140, card_height-22, 46, body=True, min_size=34)
            if len(wrapped)*bs > card_height-20:
                raise ValueError("항목 글이 카드 밖으로 넘칩니다.")
            card_text = "#172534" if t == 1 else ink
            _write(d, (left+108, y+max(15, (card_height-len(wrapped)*bs)//2)), wrapped, bf, card_text, bs)

    footer_y = 1180 if t != 6 else 1148
    if t == 7:
        footer_y = 1194
    d.line((left, footer_y, right, footer_y), fill=accent, width=3)
    foot_font = _font(3, 35, body=True)
    d.text((left, footer_y+28), "LUMIESTORY / AI SKILL", font=foot_font, fill=ink)
    page_text = f"{index:02d} / {total:02d}"
    bbox = d.textbbox((0, 0), page_text, font=foot_font)
    d.text((right-(bbox[2]-bbox[0]), footer_y+28), page_text, font=foot_font, fill=accent)
    return im


def render_carousel(article: Article, theme_number: int, output_root: Path = OUTPUT) -> Path:
    slides = build_slides(article)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = output_root / f"{stamp}-{article.slug}-t{theme_number:02d}"
    folder.mkdir(parents=True, exist_ok=False)
    image_paths = []
    for index, slide in enumerate(slides, 1):
        target = folder / f"{index:02d}.png"
        render_slide(slide, theme_number, index, len(slides)).save(target, format="PNG")
        image_paths.append(str(target))
    manifest = {
        "schema": 1,
        "created_at": datetime.now().astimezone().isoformat(),
        "article": asdict(article),
        "template_number": theme_number,
        "template_name": THEMES[theme_number-1][0],
        "slides": [asdict(slide) for slide in slides],
        "images": image_paths,
        "caption": build_caption(article),
        "status": "preview",
    }
    path = folder / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def published_urls(log_path: Path = BASE_DIR / "published_log.json") -> set[str]:
    if not log_path.exists():
        return set()
    try:
        entries = json.loads(log_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise ValueError("게시 기록을 읽을 수 없습니다. 중복 발행 방지를 위해 중단합니다.")
    if not isinstance(entries, list):
        raise ValueError("게시 기록 형식이 잘못됐습니다. 중복 발행 방지를 위해 중단합니다.")
    return {str(entry.get("source_url")) for entry in entries if isinstance(entry, dict) and entry.get("source_url")}


def next_template_number(log_path: Path = BASE_DIR / "published_log.json") -> int:
    if not log_path.exists():
        return 1
    entries = json.loads(log_path.read_text(encoding="utf-8"))
    count = sum(1 for entry in entries if isinstance(entry, dict) and entry.get("source_url", "").startswith(SITE + "/skills/"))
    return count % 10 + 1


def next_unpublished_article(session: requests.Session | None = None,
                             log_path: Path = BASE_DIR / "published_log.json") -> Article | None:
    seen = published_urls(log_path)
    for item in list_articles(session):
        if item["url"] in seen:
            continue
        article = fetch_article(item["url"], session)
        if article.download_url:
            return article
    return None
