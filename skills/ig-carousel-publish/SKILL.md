---
name: ig-carousel-publish
description: >
  사이트·블로그 글이나 검색으로 찾은 소재를 인스타그램 카드뉴스(캐러셀) 게시물로 만들어 발행하는
  워크플로우 스킬(뼈대). 소재 가져오기 → 카피 작성 → HTML/CSS 슬라이드 디자인 →
  Playwright Python으로 PNG 캡처·로컬 저장 → Cloudinary 업로드 →
  인스타그램 캐러셀 발행(미리보기 확인 후 1클릭) → (선택) 카카오톡 보고까지 한 번에 처리한다.
  소재를 가져오는 1단계만 용도에 맞게 바꿔 쓰는 구조다. 이 문서의 1~2단계 상세는 정부 지원금·정책
  공고 버전이 예시로 들어 있다.
  사용자가 "캐러셀 발행", "카드뉴스 만들어줘", "인스타 올려줘", "오늘 카드뉴스", "캐러셀 올려줘",
  "인스타그램 발행", "오늘 거 인스타에 올려줘", "○○ 검색해서 카드뉴스 만들어줘", "○○로 카드뉴스 만들어줘"
  (키워드 지정) 같은 말을 하면 반드시 이 스킬을 사용한다.
  insta_auto/.env 의 IG_ACCESS_TOKEN, IG_BUSINESS_ACCOUNT_ID, CLOUDINARY_* 값을 사용하므로
  최초 1회 설정 후 별도 설정 불필요. VS Code + Claude Code 환경에서 동작하도록 설계되었다.
---

# 인스타그램 카드뉴스(캐러셀) 자동 발행

> 처음 이 스킬을 받은 사람이면 `references/install.md`(폴더 만들기·스킬 설치·.env 준비)를 먼저
> 본다. 계정/토큰 설정만 따로 떼어 다루는 문서는 `references/setup.md`다.

소재(글·검색 결과·붙여 넣은 텍스트)를 입력받아 인스타그램 캐러셀(여러 장 슬라이드) 게시물로 만든다.

## 이 스킬은 뼈대다 (용도에 맞게 바꿔 쓴다)

완성된 앱이 아니라, 사용자의 상황에 맞게 AI가 고쳐 쓰는 뼈대다. **바뀌는 곳은 소재를 가져오는
1단계(와 그에 맞는 카피·분류 규칙)뿐이다.** 카드 이미지 만들기, Cloudinary 업로드, 인스타그램 발행,
중복 방지, 예약, 미리보기 후 승인은 어떤 소재든 그대로 쓴다.

| 용도 | 소재를 가져오는 방법 | 이 저장소에서 |
|---|---|---|
| 루미스토리 스킬 글 | 사이트 RSS(`/rss.xml`)의 `/skills/` 글을 읽음 | `app.py`, `lumistory_cards.py` (화면·예약 실행) |
| 정부 지원금·정책 공고 (예시 버전) | korea.kr·네이버 검색으로 공고 1건을 골라 읽음 | 이 문서의 1~2단계, `references/collection.md`, `publish_pipeline.py --keyword` |
| 내 블로그 (워드프레스·블로거 등) | 블로그 RSS(`/feed/` 등)의 글을 읽음 | 직접 추가 — `lumistory_cards.py`의 글 읽기 부분을 고친다 |
| 키워드 검색 (네이버 등) | 키워드로 검색해 후보를 보여 주고 1건을 고름 | 지원금 버전의 검색 함수를 참고해 직접 추가 |
| 붙여 넣은 글 | 사용자가 준 텍스트를 그대로 사용 | 직접 추가 |

사용자가 위 표에 없는 용도를 말하거나 "내 블로그(주소)에 맞춰줘"라고 하면, **1단계와 소재 읽기 코드만
그 용도에 맞게 바꾸고**, 카테고리 분류·컬러·카피·면책 규칙도 그 주제에 맞는 것으로 정한다.
발행 관련 코드(`lumistory_publish.py`, `publish_pipeline.py`의 업로드·발행 함수)는 건드리지 않는다.
바꾼 뒤에는 반드시 **미리보기까지만** 시험하고, 사용자가 승인해야 발행한다.
남의 글·검색 결과를 소재로 쓸 때는 원문을 그대로 옮기지 않고 핵심을 요약하며, 캡션에 출처를 적고,
타인의 사진은 쓰지 않는다.

> 아래 카테고리 분류·1~2단계 규칙은 **정부 지원금 버전(예시)**이다. 다른 용도에서는 이 부분을
> 그 주제에 맞게 바꿔 쓴다.

## 발행 모드 2가지 (★반드시 구분★)

| 모드 | 언제 | 캡션 | 발행 방식 |
|---|---|---|---|
| **A. 예약/자동** | launchd·작업스케줄러가 실행 (환경변수 `IG_AUTO_PUBLISH=1`) | **캡션까지 완성** | 사람 확인 없이 **수집→제작→발행→보고**까지 끝까지 자동 |
| **B. 수동(기본)** | 사람이 채팅으로 "오늘 카드뉴스 만들어줘" | 캡션까지 완성 | 발행 **직전에 멈춰** 슬라이드·캡션 미리보기 확인 → 승인 후 발행 → 보고 |

- **두 모드 공통: 캡션은 항상 완성해야 한다**(copywriting.md '캡션 공식'). 캡션이 비었거나
  자리표시자면 발행 스크립트가 **자동으로 발행을 중단**한다(오류 방지 가드).
- 모드 A(예약)는 중간에 멈추지 말고 끝까지 수행한다. 모드 B(수동)는 4단계 컨테이너 생성 후 반드시 멈춘다.

이미 수집된 소재 정보(예: 지원금 정보)를 입력받을 수도 있다. 그 경우 1단계(정보 수집)는 건너뛰고 입력값을 그대로
쓴다. **정보가 부족한 필드는 비워두되, 절대 사실을 지어내지 않는다.** 특히 입력에 없는 구체 수치
(신용점수, 금액, 비율, 날짜, 기준점 등)를 '사실'로 단정해 만들거나 환산하지 않는다 — 예를 들어
입력에 "신용평점 하위 50% 이하"만 있으면 그 표현을 그대로 쓰고, "889점 이하(NICE)" 같은 구체
점수는 그 수치가 입력에 직접 명시돼 있을 때만 쓴다. (`references/credit-score-reference.md`의
NICE/KCB 변환표는 과거 버전 자료로, 입력에 변환된 점수가 이미 있는 경우가 아니면 기본 흐름에서
더 이상 자동 적용하지 않는다.) 단, 예시용 '가정 수치'는 가정임을 명시하면 허용한다 (2단계 본문
예시 규칙 참고).

---

## 0단계 — 최초 1회 설정 확인 (매 실행 시 가장 먼저 체크)

`insta_auto/.env` 파일을 확인한다.

- **파일이 없거나 5개 값(`IG_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`, `CLOUDINARY_CLOUD_NAME`,
  `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`) 중 하나라도 비어 있으면** →
  `references/setup.md`를 열어 그 안내대로 진행한다. **Cloudinary/Meta 계정 생성, 약관 동의,
  권한(OAuth) 수락처럼 본인 인증이 필요한 클릭은 반드시 수강생 본인이 직접 하게 한다 — 대신 클릭
  하거나 계정을 만들어주지 않는다.** 발급받은 토큰/키 값을 받아 `.env`에 정리해 넣는 일, API
  호출로 토큰 교환·계정ID 조회를 대행하는 일은 Claude가 한다 (자세한 역할 분담은
  `references/setup.md`의 "요약: 누가 무엇을 하는가" 표 참고).
- **이미 다 채워져 있으면** → Python으로 토큰 유효성을 한 번 점검하고 (만료 시 setup.md의 B-3~B-4
  재안내), 바로 1단계로 넘어간다.

**Python 패키지 점검 (최초 1회):**
```bash
pip install playwright requests python-dotenv
python -m playwright install chromium
```

**토큰 유효성 점검:**
```python
import os, requests
from dotenv import load_dotenv
load_dotenv("insta_auto/.env")
TOKEN = os.environ["IG_ACCESS_TOKEN"]
r = requests.get(f"https://graph.instagram.com/me?fields=id,username&access_token={TOKEN}")
print(r.json())  # username 보이면 OK, error_code 190 이면 토큰 만료 → setup.md B-3~B-4
```

**오늘 날짜 확인:**
```bash
date +%Y-%m-%d
```

### 중복 발행 방지 체크 (0단계 마지막)

1단계로 넘어가기 전에 `insta_auto/published_log.json`을 확인한다.
파일이 없으면 그냥 넘어간다. 있으면 이미 발행된 주제 목록을 읽는다.

```python
import json
from pathlib import Path

log_path = Path("insta_auto/published_log.json")
published_titles = []
if log_path.exists():
    published_titles = [e["title"] for e in json.loads(log_path.read_text())]

# 1단계에서 주제(제목)가 확정되면 아래 체크 실행
# if 제목 in published_titles:
#     print("이미 발행된 주제입니다. 건너뜁니다.")
#     → 종료
```

주제가 `published_titles`에 있으면 **그냥 종료**한다 — 재발행하지 않는다.
같은 날 다른 주제는 제한 없이 발행 가능하다.

### 카테고리 분류 & 컬러 테마 (가장 먼저 결정한다)

입력 정보의 제목/대상/내용을 보고 아래 4개 카테고리 중 하나로 분류한다. 배경은 카테고리와
무관하게 항상 `#0a0a0a`(거의 순검정) 고정이며, **포인트 컬러만** 카테고리에 따라 교체된다.

| 카테고리 | 판별 기준 | 포인트 컬러 | HEX | RGB | 보조(연한 톤) |
|---|---|---|---|---|---|
| 청년지원금 | 청년/2030/대학생/사회초년생 | 초록 | `#34D399` | `52,211,153` | `#6EE7B7` |
| 여성지원금 | 여성/임신/출산/육아(여성대상)/경력단절 | 핑크 | `#F472B6` | `244,114,182` | `#F9A8D4` |
| 대출 | 대출/융자/이자지원/보증/전세자금/버팀목 | 파랑 | `#60A5FA` | `96,165,250` | `#93C5FD` |
| 기타 지원금 | 위에 명확히 안 맞는 경우 | 주황 | `#FF5C35` | `255,92,53` | `#FF8A65` |

헷갈리는 경우(예: "청년 전세대출")는 더 핵심인 성격 1개만 선택하고, 완료 보고에 분류 결과를 남긴다.

**자동 분류 함수 (빌드 스크립트에 항상 포함):**
```python
def get_category(title: str, summary: str = "") -> tuple[str, str, str]:
    """(ACCENT_HEX, ACCENT_RGB, 카테고리명) 반환"""
    text = (title + " " + summary)
    youth = ["청년", "2030", "대학생", "사회초년생", "청년층"]
    women = ["여성", "임신", "출산", "육아", "경력단절", "모성"]
    loan  = ["대출", "융자", "이자지원", "전세자금", "버팀목", "보증"]
    if any(k in text for k in youth):
        return "#34D399", "52,211,153", "청년지원금"
    if any(k in text for k in women):
        return "#F472B6", "244,114,182", "여성지원금"
    if any(k in text for k in loan):
        return "#60A5FA", "96,165,250", "대출"
    return "#FF5C35", "255,92,53", "기타 지원금"
```

**의미색(빨강/초록)은 카테고리와 별개로 항상 고정**이며 모든 카테고리에서 동일하게 쓴다:
- 불리/기존/위험/주의 = 빨강 `#F87171`
- 유리/이득/혜택/정답 = 초록 `#34D399`
단, 청년(초록) 카테고리일 땐 의미색 초록과 헷갈리지 않게 GOOD 박스를 더 밝은 `#6EE7B7`로 처리한다.

---

## 1단계 — 정보 수집

(이미 정보가 입력으로 주어졌다면 건너뛴다.)

**사용자가 키워드를 준 경우**(예: "**청년 월세 지원**으로 카드뉴스 만들어줘", "**소상공인 대출** 검색해서 만들어줘"):
그 키워드로 **바로 검색해서 최신·구체 공고 1건을 자동 선별**한 뒤 아래 추출로 이어간다.
korea.kr 목록 브라우징은 건너뛴다. 절차는 `references/collection.md`의 "0. 키워드 지정 수집" 참고.
→ 이후는 다른 요청과 똑같이 자동 진행되고, **마지막에 모드 B로 미리보기 확인 후 발행**한다.

자세한 절차는 `references/collection.md` 참고. (gov-threads-publish 스킬의 수집 단계와 동일한 방식)

키워드가 없으면 아래 기본 흐름:
1. Chrome으로 `https://www.korea.kr/news/policyNewsList.do?smenu=EDS01` 접속
2. 가장 최근 **지원금·정책 공고 1건** 선택 (회고성 기사 제외, 신규 지원 공고 우선)
3. 원문에서 `제목 / 한줄요약 / 대상 / 금액·혜택 / 신청기간 / 신청방법 / 출처URL / 유의사항` 추출
   — 슬라이드를 여러 장 채울 만큼 구체적으로 뽑아야 한다
4. `insta_auto/YYYY-MM-DD.txt` 로 저장

페이지가 차단되면 → 네이버 검색 MCP 폴백 사용 (references/collection.md 참고)

---

## 2단계 — 장수 결정 + 카피 작성

자세한 작성 공식과 컴포넌트별 카피 패턴은 `references/copywriting.md` 참고.

핵심 요약:
- **장수는 정보량을 보고 정한다 (총 3~10장, 표지 1 + 본문 1장 이상 + CTA 1).** 한 장에 들어갈 내용이
  빈약하거나 화면이 비어 보이면 인접한 2개 주제를 1장으로 합쳐서 꽉 차게 만들고, 반대로 정보가
  과한 주제는 2장으로 나눈다. **기준: 각 페이지는 박스/표/리스트로 화면이 85% 이상 채워져야 한다**
  (기존 70%에서 상향 — `references/design.md`의 "글씨 크기 확정값" 표대로 충분히 크게 쓰면 자연히
  채워진다).
- **1.5단계: 표지(썸네일) 후크 유형을 먼저 명시적으로 고른다.** 카피를 쓰기 전에 타겟호명/손해·FOMO/
  마감임박/숫자정리/신규 5유형 중 1개를 고르고, 고른 유형을 작업 로그에 남긴 다음 그 유형에 맞춰
  강한 제목·배지를 쓴다 (자세한 유형별 정의·예시·금지 기준은 `references/copywriting.md`의
  "1장: 썸네일(후크) 규칙" 참고 — "나랑 이거 같이 볼사람" 같은 밍밍한 즉흥 카피는 절대 금지).
  제목에는 **숫자를 적극 활용**한다. **신용점수·소득 등 구체 수치는 입력에 있는 표현을 그대로 쓴다**
  — 입력이 퍼센타일("하위 50% 이하")이면 퍼센타일 그대로 쓰고, 입력에 구체 점수가 직접 있을 때만
  그 점수를 쓴다 (임의 환산 금지 — 위 "1단계 — 정보 수집" 위 안내 참고).
- 본문 슬라이드: 슬라이드당 **핵심 정보 하나만** (욱여넣지 않기). 텍스트를 그대로 나열하지 말고
  텍스트/이모지/표/번호리스트/BAD·GOOD 비교박스로 구획화한다. 모든 본문 페이지는 콘텐츠를 **세로
  중앙정렬**한다 (제목과 하단 박스 사이에 큰 빈 공간이 생기지 않도록 — `references/design.md`의
  "세로 중앙정렬" 구조 참고).
- **반드시 '계산이 끝까지 된' 구체적 예시를 1개 이상 포함**한다 (`.example-box` 단독 슬라이드).
  - `.example-box`가 있는 슬라이드의 `HEADING`은 **`<br>` 없이 한 줄**로 작성한다. 본문이 길어서 오버플로우가 발생하기 쉬우므로 제목을 짧게 유지해야 한다 (예: `"실제로 <span class='accent'>어떻게</span> 쓰나요?"`).
  - 예시는 **"가정 → 적용 → 결과 숫자"가 완결**돼야 한다. 범위만 다시 말하는 건 예시가 아니다
    (❌ "금리는 5.9~15.27% 사이에서 정해져요" ← 계산이 없음).
  - 금리·기간 등 입력에 없는 값은 '가정'임을 명시하고, 범위의 **중간값 또는 대표값 1개**를 골라
    끝까지 계산한다 — 반드시 "~라고 가정하면"을 붙이고 결과 숫자(이자·총액 등)를 명시한다.
    (✅ "생활비로 500만원을 3년간 빌린다고 가정. 금리를 중간값 약 10%로 잡으면 → 연 이자 약 50만원,
    3년이면 약 150만원 수준(단리 단순계산 가정)")
  - 입력 정보 범위 안에서만 현실적으로 구성하고 과장·허위 수치는 금지.
- 각 본문 페이지 맨 아래엔 그 페이지 핵심을 한 줄로 못박는 **강조 요약 배너**(`SUMMARY`)가 항상 있다.
  - `SUMMARY` 텍스트는 **이모지 포함 한글 18자 이하**로 제한한다. 줄바꿈 없이 반드시 1줄에 끝나야 한다 (2줄 wrap 금지).
- 마지막 CTA 슬라이드: **`cta-follow.html` 하나로 고정**(댓글 유도형은 무료 버전에 넣지 않음).
  카피도 고정이므로 새로 짜지 않는다 (`copywriting.md`의 "CTA 슬라이드 카피 공식" 참고). 레이아웃도
  세로 중앙정렬.
- 캡션(본문 글): **스토리텔링형 공식**으로 쓴다 — 인용구 후크 제목 → 스토리 단락(전/후 대비 포함) →
  "📍 누가 받을 수 있나요?" 라벨 블록 → (마감/제약 있으면) "주의할 점!" → 캐주얼 해시태그 5개 →
  "* (토픽) 꿀팁, 정보를 놓치고 싶지 않다면 팔로우 버튼 꾸욱." 고정 패턴으로 마무리. 자세한 형식과
  실제 예시는 `references/copywriting.md`의 "캡션(본문 글) 공식" 절 참고 — 불릿(✅) 나열형 캡션은
  더 이상 쓰지 않는다.

### 줄바꿈 규칙 (매우 중요 — 모든 슬라이드 공통)

- 줄바꿈은 절대 화면에 글자로 그대로 보이는 `"\n"` 문자열로 넣지 않는다. 반드시 HTML `<br>` 태그 또는
  별도 블록 요소(`<div>`, `<p>`)로 처리한다.
- 줄바꿈은 반드시 **어절(띄어쓰기) 단위**로만 끊는다 — 단어 중간이나 조사 직전에서 끊지 않는다.
  좋은 예: "신용점수 낮으면 / 이 대출 모른다고?" · 나쁜 예: "신용점수 낮으면 이 대출 모 / 른다고?"
- **★모든 템플릿의 `#slide`에 `word-break: keep-all; overflow-wrap: break-word; line-break: strict;`를
  반드시 선언한다★** — 실측 결과 이 선언이 없으면 "주택 구입 금지 약정 필/수"처럼 한글 어절 중간이
  글자 단위로 쪼개져 줄바꿈되는 버그가 났다. `word-break: break-all`/`break-word`는 절대 쓰지 않는다
  (자세한 내용은 `references/design.md`).
- 한 줄 권장 길이: 제목 한글 12~16자, 소제목 18~24자. 끊는 위치는 의미 덩어리(구) 단위로
  ("최대 1,000만원 / 오늘부터 상시 신청").
- 고아 단어(1글자만 다음 줄로 넘어감)가 생기면 끊는 지점을 조정한다.
- 텍스트가 박스/캔버스를 넘치면 줄바꿈을 추가하거나 폰트 크기를 단계적으로 줄여 맞춘다.

### 면책(디스클레이머) 규칙 — 필수

- 금액·이자·절감액 등 수치 예시를 보여주는 페이지는 하단에 작은 회색 글씨로 면책 문구를 넣는다.
- **대출 카테고리는 면책 문구가 무조건 있어야 한다 (누락 금지).**
  기본 문구: "※ 가정 기준 단순계산이며 실제 이자는 금리·기간·상환방식에 따라 달라질 수 있습니다."
- 그 외 카테고리도 추정·예시 수치가 들어가면: "※ 실제 지원금액·자격은 개인 상황 및 기관 심사에
  따라 달라질 수 있습니다."
- 마지막 본문 또는 CTA 직전 슬라이드에 출처를 작게 표기한다: "출처: {출처URL의 기관/사이트명}"

---

## 3단계 — 배경 이미지 준비 + 슬라이드 생성 (Playwright Python)

자세한 디자인 시스템(폰트 위계, 글씨 크기 확정값, 컬러, 이모지 사용 규칙, 컴포넌트)은
`references/design.md` 참고. **글씨 크기는 `design.md`의 "글씨 크기 확정값" 표 이상으로 쓴다.**

### 배경 이미지 가져오기 (A → B → C 순서로 시도)

슬라이드 전체에 쓸 배경 이미지 1장을 아래 순서로 준비한다.
이미지를 OUT 폴더에 파일로 저장하고 `file://` URL을 반환한다.
(CSS `background-image: url("data:...")` 방식은 Playwright headless에서 렌더링 안 됨 — 반드시 파일 방식 사용)

```python
import httpx, os
from io import BytesIO
from pathlib import Path
from playwright.sync_api import sync_playwright
try:
    from PIL import Image          # 해상도 검사용 (CLAUDE.md 첫 실행에서 pillow 설치됨)
except Exception:
    Image = None

# 배경은 1080×1350으로 확대되므로, 이보다 작은 이미지를 쓰면 뿌옇게 깨진다.
# 기사 썸네일·본문 이미지가 이 최소치보다 작으면 사용하지 않고 C(Pexels)/D(picsum)로 넘어간다.
MIN_BG_W, MIN_BG_H = 800, 600

def _big_enough(content: bytes) -> bool:
    """다운로드한 이미지가 배경으로 쓸 만큼 큰지 검사. Pillow가 없으면 관대하게 통과."""
    if Image is None:
        return True
    try:
        w, h = Image.open(BytesIO(content)).size
        return w >= MIN_BG_W and h >= MIN_BG_H
    except Exception:
        return False

def get_bg_image_url(article_thumbnail_url: str, article_url: str,
                     keywords: list[str], out_dir: Path) -> str:
    """배경 이미지를 out_dir/_bg.jpg 에 저장하고 file:// URL 반환.
    A(기사썸네일)→B(기사본문 이미지)→C(Pexels)→D(키리스 무료사진) 순으로 시도하며,
    ★사진을 무조건 1장 확보한다★. 네트워크 완전 불통 등 극단적 상황에서만 빈 문자열(순검정)."""
    bg_path = out_dir / "_bg.jpg"

    # A. 기사 썸네일 직접 다운로드 (단, 너무 저해상도면 사용 안 함)
    if article_thumbnail_url:
        try:
            r = httpx.get(article_thumbnail_url, timeout=10, follow_redirects=True)
            if r.status_code == 200 and "image" in r.headers.get("content-type", "") and _big_enough(r.content):
                bg_path.write_bytes(r.content)
                return bg_path.as_uri()
        except Exception:
            pass

    # B. 기사 페이지에서 저작권 안전한 이미지 src를 직접 다운로드
    # ★ img.screenshot() 사용 금지 — 렌더링된 저해상도(수백px)를 캡처하므로
    #   1080×1350 배경으로 확대 시 극심한 블러 발생. 반드시 src URL로 직접 다운로드한다 ★
    #
    # ★ 저작권 필터링 규칙 (반드시 준수) ★
    # - 사용 금지: 이미지 근처(figcaption, alt, 인접 텍스트)에 "무단 전재", "재배포 금지"가
    #   있는 경우 → 언론사(뉴스1, 연합뉴스 등) 저작권 이미지이므로 절대 사용하지 않는다
    # - 사용 가능: 정부 부처·기관이 직접 제공한 자료 이미지 — 캡션에 "(자료=기획재정부)",
    #   "(사진=보건복지부)", "(제공=금융위원회)", "(출처=행정안전부)" 등 부처명이 명시된 경우,
    #   인포그래픽·표·정책 홍보 이미지 등은 사용해도 된다
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            pg = browser.new_page(viewport={"width": 1200, "height": 800})
            pg.goto(article_url, wait_until="networkidle", timeout=15000)
            best_src = pg.evaluate("""() => {
                // 저작권 금지 키워드
                const BLOCKED = ['무단 전재', '재배포 금지', '무단전재', '©'];
                // 정부 제공 허용 패턴
                const ALLOWED = ['자료=', '사진=', '제공=', '출처=', '자료사진'];

                function getNearbyText(img) {
                    const fig = img.closest('figure');
                    const caption = fig ? fig.querySelector('figcaption') : null;
                    const parent = img.parentElement;
                    return [
                        img.alt || '',
                        caption ? caption.innerText : '',
                        parent ? parent.innerText.slice(0, 200) : ''
                    ].join(' ');
                }

                const candidates = Array.from(document.querySelectorAll('img'))
                    .filter(i => i.naturalWidth > 600)
                    .map(i => ({ src: i.src, w: i.naturalWidth, h: i.naturalHeight, text: getNearbyText(i) }));

                // 1순위: 정부 제공 이미지
                const govImg = candidates
                    .filter(i => ALLOWED.some(k => i.text.includes(k)))
                    .sort((a, b) => b.w * b.h - a.w * a.h)[0];
                if (govImg) return govImg.src;

                // 2순위: 저작권 금지 문구 없는 이미지 중 가장 큰 것
                const safeImg = candidates
                    .filter(i => !BLOCKED.some(k => i.text.includes(k)))
                    .sort((a, b) => b.w * b.h - a.w * a.h)[0];
                if (safeImg) return safeImg.src;

                // 모두 금지 문구 있으면 null → C단계(Pexels)로 넘어감
                return null;
            }""")
            browser.close()
            if best_src:
                r = httpx.get(best_src, timeout=15, follow_redirects=True)
                if r.status_code == 200 and "image" in r.headers.get("content-type", "") and _big_enough(r.content):
                    bg_path.write_bytes(r.content)
                    return bg_path.as_uri()
    except Exception:
        pass

    # C. Pexels 무료 이미지 (portrait 비율) — 키가 있을 때만 시도
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    if pexels_key:
        query = " ".join(keywords[:2]) if keywords else "money korea"
        try:
            r = httpx.get("https://api.pexels.com/v1/search",
                headers={"Authorization": pexels_key},
                params={"query": query, "per_page": 1, "orientation": "portrait"},
                timeout=10)
            photos = r.json().get("photos", [])
            if photos:
                img_url = photos[0]["src"].get("portrait") or photos[0]["src"]["large"]
                img_r = httpx.get(img_url, timeout=15, follow_redirects=True)
                bg_path.write_bytes(img_r.content)
                return bg_path.as_uri()
        except Exception:
            pass

    # D. 키리스 무료 사진 보장 — ★사진 1장은 무조건 들어가게★
    #    A·B·C가 다 실패하거나 Pexels 키가 없어도 여기서 사진을 확보한다.
    #    Lorem Picsum(무료·API 키 불필요)에서 1080×1350 portrait 사진을 받는다.
    #    키워드로 seed를 고정해 같은 주제엔 같은 사진이 나오게 하고, 위 다크 오버레이(검정 80%)가
    #    덮이므로 어떤 사진이 와도 톤이 통일된다.
    try:
        import hashlib
        seed = hashlib.md5((" ".join(keywords) or "gov").encode("utf-8")).hexdigest()[:10]
        r = httpx.get(f"https://picsum.photos/seed/{seed}/1080/1350",
                      timeout=15, follow_redirects=True)
        if r.status_code == 200 and r.content:
            bg_path.write_bytes(r.content)
            return bg_path.as_uri()
    except Exception:
        pass

    # 여기까지 오면 네트워크 완전 불통 등 극단적 상황뿐 → 최후에만 순검정(#0a0a0a)
    return ""
```

**카테고리별 Pexels 검색 키워드:**
```python
PEXELS_KEYWORDS = {
    "청년지원금": ["youth", "young people korea"],
    "여성지원금": ["women empowerment", "mother family"],
    "대출":       ["money loan", "finance korea"],
    "기타 지원금": ["government money", "tax korea"],
}
```

**Pexels API 키 설정 (선택, 무료 — 사진 품질/주제적합성 ↑):**
- pexels.com/api 가입 → API 키 발급
- `.env`에 `PEXELS_API_KEY=your_key` 추가
- **키가 없어도 D단계(키리스 무료사진, picsum)가 사진을 무조건 확보**하므로 순검정으로 빠지지 않는다.
  (키를 넣으면 카테고리 키워드에 더 맞는 사진이 나온다.)

---

### 빌드 스크립트 구조 (insta_auto/build_{날짜}_{주제}.py 로 저장)

```python
from playwright.sync_api import sync_playwright
from pathlib import Path
import base64, os
from dotenv import load_dotenv

load_dotenv("insta_auto/.env")

ASSETS = Path("insta_auto/skills/ig-carousel-publish/assets")
OUT    = Path(f"insta_auto/{오늘날짜}_{주제약어}")
OUT.mkdir(exist_ok=True)

# 아바타: insta_auto/avatar.jpg (없으면 사진 파일 경로 변경)
with open("insta_auto/avatar.jpg", "rb") as f:
    AVATAR_B64 = base64.b64encode(f.read()).decode()

# 카테고리 자동 분류
ACCENT_HEX, ACCENT_RGB, CATEGORY = get_category(제목, 요약)
TOTAL = "N"  # 총 슬라이드 수

# 배경 이미지 준비 (A→B→C) — file:// URL 반환
BG_IMAGE = get_bg_image_url(
    article_thumbnail_url=기사_썸네일_URL,  # 없으면 ""
    article_url=기사_URL,
    keywords=PEXELS_KEYWORDS.get(CATEGORY, ["government", "korea"]),
    out_dir=OUT,
)

# 템플릿 로드
COVER_TPL = (ASSETS / "cover-dark.html").read_text(encoding="utf-8")
INFO_TPL  = (ASSETS / "info-card-dark.html").read_text(encoding="utf-8")
CTA_TPL   = (ASSETS / "cta-follow.html").read_text(encoding="utf-8")

def fill(tpl, mapping):
    for k, v in mapping.items():
        tpl = tpl.replace(f"__{k}__", v)
    return tpl

slides = []

# ── 슬라이드 채우기 예시 ──────────────────────────────
# 모든 슬라이드에 공통으로 들어가는 값
COMMON = {
    "ACCENT_HEX": ACCENT_HEX,
    "ACCENT_RGB": ACCENT_RGB,
    "BG_IMAGE": BG_IMAGE,
}

# 표지
slides.append(("01_cover", fill(COVER_TPL, {
    **COMMON,
    "BADGE_TEXT": "🔥 배지 텍스트",
    "TITLE": "제목<br><span class='accent'>강조 단어</span>",
    "SUBTITLE": "부제목",
    "FOOTER_TEXT": "스와이프해서 확인 →",
})))

# 정보 슬라이드 (반복)
slides.append(("02_info", fill(INFO_TPL, {
    **COMMON,
    "LABEL": "라벨명",
    "PAGE_NUM": "2", "TOTAL_PAGES": TOTAL,
    "HEADING": "소제목",
    "BODY_HTML": "<p class='body-text'>본문 내용</p>",
    "SUMMARY": "요약 한 줄",
})))

# CTA (항상 마지막, 고정 템플릿)
slides.append(("N_cta", fill(CTA_TPL, {
    **COMMON,
    "PAGE_NUM": f"{TOTAL} / {TOTAL}",
    "HEADLINE": "정책 지원금<br><span class='accent'>놓치고 싶지 않다면</span>",
    "AVATAR_HTML": f'<img src="data:image/jpeg;base64,{AVATAR_B64}">',
    "HANDLE": "@계정명",
    "GUIDE_TEXT": "팔로우하고 프로필 링크를 확인해 보세요",
    "SMALL_TEXT": "매일 놓치기 쉬운 <mark>지원금·정책</mark>, 가장 먼저 알려드려요",
})))
# ─────────────────────────────────────────────────────

# Playwright 렌더링 — file:// 방식 (set_content 대신 goto 사용, CSS background-image 정상 렌더링됨)
tmp_html = OUT / "_tmp_slide.html"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1080, "height": 1350})
    for i, (name, html) in enumerate(slides, 1):
        tmp_html.write_text(html, encoding="utf-8")
        page.goto(tmp_html.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(800)
        page.screenshot(
            path=str(OUT / f"{i:02d}.png"),
            clip={"x": 0, "y": 0, "width": 1080, "height": 1350}
        )
        print(f"  {i:02d}.png ✅")
    tmp_html.unlink(missing_ok=True)
    browser.close()
```

**스크립트 실행:**
```bash
python insta_auto/build_{날짜}_{주제}.py
```

**로컬 저장 경로 규칙:**
- 1건 → `insta_auto/{YYYY-MM-DD}_{주제}/01.png` ... `N장.png`
- 여러 건 → `insta_auto/{YYYY-MM-DD}/{순번_주제}/01.png` ...
- 폴더가 없으면 자동 생성 (`OUT.mkdir(exist_ok=True)` 처리됨)

### self-check (4단계로 넘어가기 전에 반드시 확인, 총 11개)

① 예시가 "가정→적용→결과 숫자"로 완결됐는가 (범위만 반복했으면 예시 아님 → 하나의 값으로 끝까지
   계산해 다시 작성)
② 수치 들어간 페이지에 면책 문구가 있는가 (대출이면 무조건 확인, 기본 문구는 위 "면책 규칙" 참고)
③ 휑한 페이지는 없는가 — 각 페이지 85% 이상 채움 + 콘텐츠가 세로 중앙정렬됐는가 (안 차면
   합치기/박스확대/폰트확대로 해결)
④ 제목 색강조가 핵심 단어 1~2개로 절제됐는가 (한 페이지 색강조 3~4곳 이내)
⑤ 텍스트에 `"\n"` 문자열이 그대로 노출된 곳은 없는가 (있으면 `<br>`로 교체)
⑥ 단어/조사 중간에서 줄이 끊긴 곳은 없는가 — "필/수", "상/품" 같은 글자 쪼개짐이 1곳이라도 있으면
   실패 (`word-break: keep-all` 선언 확인 + 어절 단위로 재조정)
⑦ 입력에 없는 구체 수치(신용점수 등)를 '사실'로 단정하지 않았는가 — 입력에 있으면 그대로 사용 OK,
   없으면 원문 표현(퍼센타일 등)으로 대체했는가. 예시 가정값은 "~라고 가정하면" 명시했는가
⑧ CTA 페이지가 세로 중앙정렬돼 무게중심이 아래로 처지지 않았는가
⑨ ★썸네일 후크가 5유형(타겟호명/FOMO/마감임박/숫자정리/신규) 중 하나에 명확히 해당하는가?
   밍밍·모호한 카피면 실패 → 5유형 중 골라 강한 카피로 다시 작성.
   핵심 키워드(금액·대상)가 카테고리 컬러로 강조됐는가? 배지도 강한 한마디인가?★
⑩ ★모든 텍스트가 `design.md`의 "글씨 크기 확정값" 표 이상인가? (썸네일제목104px/본문제목76px/
   부제46px/체크리스트·번호리스트·예시본문42px/표항목40px/비교박스수치54px·박스제목38px/결론배너
   40px/배지34px/페이지번호30px — 면책·출처 24px만 예외) 실제 캡처 이미지를 보고 작더라도 무조건
   더 키워서 다시 캡처한다★
⑪ 이모지를 자리별 가이드(배지/제목/표항목/체크리스트/비교박스/결론배너/화살표)대로 적극적으로
   썼는가 — 텍스트만 가득한 무미건조한 슬라이드는 실패
— 하나라도 미충족이면 그 슬라이드를 수정하고 다시 캡처한다.

---

## 4단계 — Cloudinary 업로드 + 캐러셀 생성/발행 (모드 분기)

- **모드 A(예약, `IG_AUTO_PUBLISH=1`)**: 업로드 → 컨테이너 → **발행 → 로그 → 보고**까지 자동.
- **모드 B(수동, 기본)**: 업로드 → 컨테이너까지만. **여기서 멈추고** 미리보기(슬라이드·캡션)를
  사용자에게 보여준 뒤, **승인받으면** `publish_carousel(cid)`로 발행 → 5단계 보고.
- 어느 모드든 발행 직전 **캡션 완성 가드**(`_assert_caption_ok`)를 통과해야 한다.

자세한 API 호출 방법은 `references/publish.md` 참고.

**Python 발행 스크립트 구조 (insta_auto/publish_{날짜}_{주제}.py 로 저장):**

```python
import hashlib, time, requests, json, os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("insta_auto/.env")
CLD_NAME   = os.environ["CLOUDINARY_CLOUD_NAME"]
CLD_KEY    = os.environ["CLOUDINARY_API_KEY"]
CLD_SECRET = os.environ["CLOUDINARY_API_SECRET"]
IG_TOKEN   = os.environ["IG_ACCESS_TOKEN"]
IG_ACCT    = os.environ["IG_BUSINESS_ACCOUNT_ID"]

SLIDES_DIR = Path(f"insta_auto/{오늘날짜}_{주제약어}")
TITLE      = "기사 제목"   # published_log.json 중복 체크용
CAPTION    = """...캡션 전문..."""

def cloudinary_upload(file_path: Path) -> str:
    ts  = str(int(time.time()))
    pub = f"carousel/{file_path.stem}_{ts}"
    sig = hashlib.sha1(
        f"public_id={pub}&timestamp={ts}{CLD_SECRET}".encode()
    ).hexdigest()
    with open(file_path, "rb") as f:
        r = requests.post(
            f"https://api.cloudinary.com/v1_1/{CLD_NAME}/image/upload",
            data={"api_key": CLD_KEY, "timestamp": ts,
                  "signature": sig, "public_id": pub},
            files={"file": f}, timeout=30,
        )
    r.raise_for_status()
    return r.json()["secure_url"]

def ig_create_item(image_url: str) -> str:
    r = requests.post(
        f"https://graph.instagram.com/v22.0/{IG_ACCT}/media",
        params={"image_url": image_url, "is_carousel_item": "true",
                "access_token": IG_TOKEN}, timeout=20,
    )
    r.raise_for_status()
    return r.json()["id"]

def ig_create_carousel(item_ids: list, caption: str) -> str:
    r = requests.post(
        f"https://graph.instagram.com/v22.0/{IG_ACCT}/media",
        params={"media_type": "CAROUSEL",
                "children": ",".join(item_ids),
                "caption": caption,
                "access_token": IG_TOKEN}, timeout=20,
    )
    r.raise_for_status()
    return r.json()["id"]

def ig_publish(creation_id: str) -> str:
    r = requests.post(
        f"https://graph.instagram.com/v22.0/{IG_ACCT}/media_publish",
        params={"creation_id": creation_id, "access_token": IG_TOKEN},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["id"]

def get_permalink(post_id: str) -> str:
    r = requests.get(
        f"https://graph.instagram.com/v22.0/{post_id}",
        params={"fields": "permalink", "access_token": IG_TOKEN}
    )
    return r.json().get("permalink", f"포스트 ID: {post_id}")

def save_log(title: str, date: str, permalink: str):
    log_path = Path("insta_auto/published_log.json")
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    log.append({"date": date, "title": title, "permalink": permalink})
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2))

def _assert_caption_ok(caption: str):
    """캡션이 비었거나 자리표시자면 발행을 막는다 (오류 방지 가드 — 두 모드 공통)."""
    c = (caption or "").strip()
    if (not c) or ("캡션 전문" in c) or (c.strip(". ") == "") or (len(c) < 40):
        raise SystemExit(
            "❌ 발행 중단: 캡션이 비었거나 자리표시자(...캡션 전문...)입니다.\n"
            "   copywriting.md '캡션(본문 글) 공식'대로 캡션을 먼저 작성해 CAPTION에 넣으세요."
        )

# 발행 모드 스위치: 예약/자동 실행은 IG_AUTO_PUBLISH=1 (launchd·작업스케줄러가 설정).
#   AUTO=True  → 확인 없이 끝까지 발행+보고 / AUTO=False → 컨테이너까지만 만들고 멈춤(사람 확인)
AUTO = os.environ.get("IG_AUTO_PUBLISH") == "1"

def stage_carousel() -> str:
    """업로드 → 슬라이드 컨테이너 → 캐러셀 부모 컨테이너. creation_id 반환 (아직 발행 안 함)."""
    _assert_caption_ok(CAPTION)
    slides = sorted(SLIDES_DIR.glob("*.png"))
    if not slides:
        raise SystemExit("❌ 발행 중단: 슬라이드 PNG가 없습니다. 3단계(렌더링)를 먼저 완료하세요.")
    image_urls  = [cloudinary_upload(s) for s in slides]
    item_ids    = [ig_create_item(url) for url in image_urls]
    time.sleep(2)
    carousel_id = ig_create_carousel(item_ids, CAPTION)
    print("―― 발행 미리보기 ――")
    print(f"슬라이드 {len(slides)}장:")
    for u in image_urls:
        print("  -", u)
    print("캡션:\n" + CAPTION)
    print(f"creation_id={carousel_id}")
    return carousel_id

def publish_carousel(carousel_id: str) -> str:
    """실제 발행(공개·되돌릴 수 없음) → 퍼머링크 → 로그. AUTO거나 사용자 승인 후에만 호출."""
    time.sleep(2)
    post_id   = ig_publish(carousel_id)
    permalink = get_permalink(post_id)
    save_log(TITLE, 오늘날짜, permalink)
    print(f"✅ 발행 완료: {permalink}")
    return permalink

if __name__ == "__main__":
    cid = stage_carousel()               # 공통: 업로드+컨테이너+캡션가드
    if AUTO:
        publish_carousel(cid)            # 모드 A(예약): 확인 없이 끝까지 → 이후 5단계 카톡 보고
    else:
        print("\n⏸  모드 B(수동): 여기서 멈춤. 위 미리보기(슬라이드·캡션)를 사용자에게 보여주고,")
        print("   사용자가 '발행'을 승인하면 그때 publish_carousel(cid) 만 실행하세요.")
```

**스크립트 실행:**
```bash
python insta_auto/publish_{날짜}_{주제}.py
```

> ⚠️ Instagram API는 반드시 `graph.instagram.com` 을 사용한다.
> `graph.facebook.com` 은 IGAA 토큰 타입과 호환되지 않아 오류가 난다.

---

## 5단계 — 카카오톡 완료 알림

발행 완료 후 카카오톡 `나에게 보내기` (MCP 도구)로 전송.

**반드시 아래 순서로 실행:**
1. ToolSearch로 도구 로드: `select:mcp__claude_ai_PlayMCP__KakaotalkChat-MemoChat`
2. 로드된 도구로 아래 메시지 전송:
```
✅ 인스타 카드뉴스 자동 발행 완료

📌 주제: [기사 제목]
📂 카테고리: [카테고리명] ([ACCENT_HEX])
📲 게시물: [permalink]
```

---

## 예약 실행 모드 (매일 완전 자동 발행 · 로컬 방식)

매일 정한 시각에 전체 흐름(0~5단계)을 사람 없이 자동 실행한다.
확인 절차 없이 **수집 → 제작 → 발행 → 카카오 알림**까지 완전 자동이다.

> ⚠️ **이 예약은 클라우드도 git도 쓰지 않는다. 사용자의 이 컴퓨터에서 직접 돈다.**
> 그래서 예약 시각에 **① 컴퓨터가 켜져 있고 ② Claude Code에 로그인된 상태**여야 실행된다.
> 컴퓨터가 꺼져 있으면 그 날은 건너뛴다(클라우드가 대신 돌려주지 않음).
> **Windows·Mac 둘 다 지원**하며, 설치·문제해결 방법은 `references/schedule.md`에 있다.

**설정 방법** (최초 1회, 채팅에서 입력 — **시각은 원하는 대로**, 11시는 예시):
```
매일 오전 11시에 자동 발행 예약해줘      (또는 "저녁 9시에", "아침 8시반에" 등)
```
→ Claude가 **사용자가 말한 시각**과 OS를 확인하고, `references/schedule.md`대로 **로컬 스케줄러**
(Mac = launchd / Windows = 작업 스케줄러)를 **자동으로 설치**한다. 시각을 안 말하면 한 번 물어본다
(기본 11:00). 도중에 막히면 스스로 원인을 찾아 해결하고, 사용자가 직접 해야 할 일이 있으면 쉬운 말로 안내한다.
나중에 "자동 발행 시간 ○시로 바꿔줘"로 언제든 변경 가능.

**자동 실행 흐름:**
```
매일 정한 시각 (컴퓨터 켜짐 + Claude 로그인 상태) → 로컬 스케줄러가 claude 실행
  ↓
0단계: published_log.json 확인 → 이미 발행된 주제면 종료
  ↓
1~3단계: 정보 수집 → 카피 → 슬라이드 제작
  ↓
4단계: Cloudinary 업로드 → 캐러셀 발행 → published_log.json 기록
  ↓
5단계: 카카오 완료 알림
```

---

## 완료 보고 (채팅)

```
✅ 카테고리: [카테고리] / 컬러: [HEX]
✅ 수집 완료: [제목]
✅ 슬라이드 N장 제작 (Playwright 렌더링 / CTA: cta-follow.html 고정형)
✅ 썸네일 후크 유형: [타겟호명/FOMO/마감임박/숫자정리/신규 중 1개]
✅ 로컬 저장: insta_auto/YYYY-MM-DD_주제/
✅ Cloudinary 업로드: 완료 (N장)
✅ 캡션 작성: 완료 (스토리텔링 공식)
✅ 발행: [permalink]   (모드 A=자동 / 모드 B=사용자 승인 후)
✅ published_log.json 기록 완료
✅ 카톡 알림: 완료
```

> 모드 B(수동)에서는 위 "Cloudinary 업로드"까지 한 뒤 **미리보기(슬라이드·캡션)를 먼저 보여주고
> 멈춘다.** 사용자가 승인하면 그때 "발행 → 기록 → 카톡 알림"을 이어서 완료한다.

---

## 토큰 만료 시 (60일마다)

먼저 refresh를 시도한다:
```python
import requests, os
from dotenv import load_dotenv
load_dotenv("insta_auto/.env")
TOKEN = os.environ["IG_ACCESS_TOKEN"]
r = requests.get(
    "https://graph.instagram.com/refresh_access_token",
    params={"grant_type": "ig_refresh_token", "access_token": TOKEN}
)
print(r.json())
# 성공: new_token = r.json()["access_token"] → .env의 IG_ACCESS_TOKEN 교체
# 실패: setup.md B-3~B-4 재안내
```
