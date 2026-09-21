# 3단계 상세 — 슬라이드 렌더링 + 이미지 생성

## 다크모드 카드 디자인 시스템 (현재 기본 템플릿)

`cover-dark.html` / `info-card-dark.html` / `cta-follow.html` **3종이 유일한 기본 템플릿**이다
(디자인 1종 고정, 카테고리별 포인트 색만 교체). 세 템플릿 모두 **배경에 사진 1장(`__BG_IMAGE__`)을
깔고 그 위에 검정 80% 오버레이(`rgba(0,0,0,0.80)`)를 덮는** 다크 무드다 — 사진은 어둡게 깔린
질감으로 보이고 텍스트 가독성은 유지된다. 배경 사진은 `get_bg_image_url()`이 A(기사썸네일)→
B(기사 본문 이미지, 언론사 저작권 이미지는 제외)→C(Pexels)→D(키리스 무료사진) 순으로 **항상 1장
확보**한다(SKILL.md 참고). 사진을 못 받는 극단적 경우에만 CSS 대체색 `#0a0a0a`(순검정)로 보인다.

### 폰트 — Pretendard 1종 + 숫자·날짜는 모노스페이스

**한글/일반 텍스트는 Pretendard 하나로 통일**한다 (이전엔 Paperozi를 썼지만, 정리된 디자인
스펙에서 Pretendard로 변경했다 — 폰트를 여러 개 쓰지 않고 같은 폰트의 "굵기"로만 위계를 만든다).

```html
<link rel="stylesheet" as="style" crossorigin
  href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap" />
```

| 용도 | 폰트 | 굵기 |
|------|------|------|
| 표지 TITLE / 정보 슬라이드 HEADING | Pretendard | **800~900 (ExtraBold~Black)** |
| 본문 항목 / 소제목 / 체크표·리스트 텍스트 | Pretendard | **600 (SemiBold)** |
| 보조 설명 / 면책(disclaimer) / 출처 | Pretendard | 400~500, 색은 회색 `#9CA3AF` |
| **숫자/금액/금리/날짜/영문 키워드** (예: `1,000만원`, `5.9%`, `06.29`) | **JetBrains Mono** | 500~700 |

숫자에 모노스페이스를 쓰는 이유는 "데이터" 느낌을 강조하기 위함이다 — `.mono` 클래스를 만들어
숫자/금액/날짜가 들어가는 자리마다 `<span class="mono">1,000만원</span>` 식으로 감싼다.

### 글씨 크기 확정값 (★절대 이보다 작게 쓰지 않는다★)

실제로 생성된 슬라이드를 확인해보니 글씨가 전반적으로 너무 작았다. 아래는 요소별 **최소** px
값이다 — 화면을 85% 이상 채우는 데도 도움이 되니, 빈 공간이 남으면 줄이지 말고 오히려 이 값보다
더 키운다(필요하면 110~120px까지):

| 요소 | 최소 크기 | 굵기 |
|------|----------|------|
| 썸네일(표지) 제목 (`cover-dark.html` `.title`) | **104px** | 800 |
| 본문 제목 (`info-card-dark.html` `.heading`) | **76px** | 900 |
| 부제 (`cover-dark.html` `.subtitle`) | **46px** | 500 |
| 체크리스트 / 번호리스트 / 예시 본문 텍스트 | **42px** | 600 |
| 표(`.table-card`) 항목 텍스트 | **40px** (강조 금액은 `48px`) | 800 |
| 비교박스(`.compare-box`) 수치(`.big`) | **54px** | 700 |
| 비교박스 박스 제목(`.tag`) | **38px** | 700 |
| 결론 배너(`.summary-bar`) | **40px** | 700 |
| 배지(`.badge`/`.label`) | **34px** | 600~700 |
| 페이지 번호(`.page-num`) | ~~30px~~ **display:none** — 모든 슬라이드에서 숨김 처리 | - |
| 면책·출처(`.disclaimer`/`.source-text`) | **24px** (이것만 작게 허용되는 예외) | 400 |

면책·출처를 제외한 모든 텍스트는 이 표의 값을 **하한선**으로 본다 — 표보다 작게 쓰면 안 되고,
공간이 남으면 더 키운다.

### 줄바꿈 — `word-break: keep-all` 전역 필수 (★재발방지★)

실측 결과 "주택 구입 금지 약정 필수"처럼 한글 어절 중간(예: "필/수", "상/품")에서 글자가 쪼개져
줄바꿈되는 버그가 발생했다 — 브라우저 기본 줄바꿈 동작이 한글을 글자 단위로 끊을 수 있기 때문이다.
이를 막기 위해 **모든 템플릿의 `#slide` 셀렉터에 아래 3줄을 반드시 넣는다** (`word-break`,
`line-break`, `overflow-wrap`은 상속 속성이라 `#slide`에 한 번만 선언하면 모든 자식 요소에 적용된다):

```css
#slide {
  word-break: keep-all;     /* 한글을 글자 단위로 쪼개지 않고 어절 단위로만 줄바꿈 */
  overflow-wrap: break-word; /* 단, 어절 자체가 박스보다 길면(긴 URL 등) 그 때만 강제 줄바꿈 */
  line-break: strict;
}
```

**`word-break: break-all` / `break-word`는 절대 쓰지 않는다** — 이 값들은 글자 중간을 쪼갠다.
표 셀(`.table-card td`)처럼 좁은 공간도 이 규칙을 그대로 적용하고, 셀이 좁아서 잘릴 것 같으면
셀 폭이나 표 행 높이를 늘려서 해결한다 (글자를 쪼개서 맞추지 않는다).

### 표지 TITLE 블록의 수직 위치 (중요 — 맨 위 배치 금지)

배지+제목+부제 블록은 슬라이드 맨 위가 아니라 **수직 중간 정도**에 떠 있어야 한다.
`cover-dark.html`은 `#slide`를 `display:flex; flex-direction:column; justify-content:center;`로
두고 `.content`는 큰 `padding-top`을 주지 않는다 — `.content`가 사실상 유일한 flow 안 요소
(`.footer`/`.corner-mark`는 `position:absolute`라 flex 레이아웃에 안 끼임)라서 자동으로 수직
중앙 근처에 배치된다. 표지를 수정할 때 다시 큰 `padding-top`을 주거나 `justify-content`를
`flex-start`로 바꾸면 "너무 위에" 붙는 예전 문제로 돌아가니 주의한다.

### 배경 — 항상 플랫 `#0a0a0a`

배경은 카테고리와 무관하게 항상 평평한 단색 `#0a0a0a`로 고정한다 (이전에 쓰던 radial-gradient
질감은 제거했다 — 정리된 스펙이 "배경 #0a0a0a 고정"을 명시했기 때문). CTA 슬라이드도 동일하게
플랫 배경을 쓴다 (이전엔 CTA만 radial-gradient를 썼는데, 통일성을 위해 다른 슬라이드와 맞춘다).

### 색상 — 카테고리 포인트 컬러 + 고정 의미색

배경은 `#0a0a0a`. 카테고리별 강조색(`__ACCENT_HEX__`/`__ACCENT_RGB__`)을 슬롯으로 두고
SKILL.md의 카테고리 표(청년=초록/여성=핑크/대출=파랑/기타=주황)에서 정한 값을 채운다.
`__ACCENT_RGB__`는 `rgba(__ACCENT_RGB__, 0.16)`처럼 투명도 합성에 쓰므로 `R,G,B` 숫자 형태로
채운다 (html2canvas가 `color-mix()`나 `filter: blur()`를 안정적으로 지원하지 않아서 rgba 합성
방식을 쓴다).

의미색(빨강 `#F87171` / 초록 `#34D399`)은 카테고리와 별개로 고정이며, BAD/GOOD 비교박스나 체크표의
✅/❌ 강조에 쓴다. 청년(초록) 카테고리에서 GOOD을 표시할 땐 카테고리색과 헷갈리지 않게 `#6EE7B7`
(보조 톤)을 대신 쓴다.

색 강조는 한 페이지에 **3~4곳 이내로 절제**한다 — 제목은 핵심 단어 1~2개만 칠하고 나머지는 흰색
유지.

### 정보 슬라이드 레이아웃 — "화면을 꽉 채운다" + "세로 중앙정렬" (★구조 변경★)

이전엔 라벨/제목을 맨 위에 고정하고 `.content-area{flex:1}`로 남는 공간을 본문이 그냥 늘어나며
채우는 구조였다. 정리된 스펙은 여기서 한 단계 더 나간다 — **제목과 하단 사이에 큰 빈 공간이 생기지
않도록, 제목+본문+요약바를 하나의 덩어리로 묶어서 화면 안에서 세로로 "중앙정렬"하고, 남는 여백은
위/아래로 고르게 분산시킨다.**

`info-card-dark.html`의 구조:
- `#slide`는 `display:flex; flex-direction:column;` (배경/패딩 등은 기존과 동일)
- `.top-row`(라벨+페이지번호)는 그대로 최상단에 둔다 — 이건 중앙정렬 대상이 아니다.
- `.top-row` **아래** 나머지 전체(`.heading` + `.content-area` + `.summary-bar`)를 `.main-block`
  같은 래퍼 하나로 묶고, 그 래퍼에 `flex: 1; display:flex; flex-direction:column;
  justify-content:center;`를 준다. 이러면 `.top-row`를 제외한 나머지 공간 안에서 제목~요약바
  덩어리가 수직 중앙에 위치하고, 그 위/아래로 남는 빈 공간이 균등하게 나뉜다 (제목만 위에 붙고
  아래가 텅 빈 옛 문제를 막는다).
- `.content-area` 자체는 더 이상 `flex:1`을 가질 필요가 없다(부모인 `.main-block`이 이미 중앙정렬을
  책임지므로) — `gap`만 유지해서 컴포넌트 사이 여백을 준다.
- **각 페이지는 박스/표/리스트로 화면의 85% 이상이 채워져야 한다** (기존 70%에서 상향) — 부족하면
  ①인접 주제를 합치거나 ②박스 크기/내부 패딩을 키우거나 ③부연설명·요약 한 줄을 추가하거나 ④그래도
  안 차면 위 "글씨 크기 확정값" 표 이상으로 폰트 크기를 키워서 채운다. 합쳐도 계속 빈약하면 전체
  장수를 줄인다(예: 8장→6장).
- **`#slide` 패딩은 좌우 `72px`, 상하 `80px`로 고정**한다 (`padding: 80px 72px;`) — 기존
  `64px 64px 56px`보다 넉넉하게 키운 값이다. 글씨가 커진 만큼 가장자리 여백도 같이 키워야 답답해
  보이지 않는다.

`.summary-bar`는 모든 정보 슬라이드 맨 아래(즉 `.main-block` 안의 마지막 요소)에 항상 넣는다.
카피 작성 단계에서 슬라이드마다 `SUMMARY` 한 줄을 반드시 같이 써야 한다.

### 이모지 사용 규칙 (★신규·필수★)

배경 사진 위에 검정 오버레이가 덮여 톤이 차분하므로, 이모지가 시각적 포인트 역할을 한다 —
이모지를 아끼면 슬라이드가 텍스트만 가득한 문서처럼 보인다. **자리별로 아래 이모지를 적극적으로 쓴다** (없으면 채움 기준
85%를 못 채우는 원인이 되기도 한다):

| 자리 | 이모지 가이드 |
|------|--------------|
| 배지(`.badge`/`.label`) | 문구 앞에 상황에 맞는 1개 (예: 📌 ⚠️ 🔥 ✅) |
| 제목(`.title`/`.heading`) | 줄바꿈 지점이나 끝에 핵심을 받쳐주는 1개 (예: 💰 📍 ⏰) — 과하면 1개로 절제 |
| 표 항목(`.table-card th`) | 항목 성격에 맞는 1개를 텍스트 앞에 (예: 💵 한도, 📅 일정, 🏦 기관) |
| 체크리스트(`.checklist`) | ✅/❌는 이미 고정 — 추가로 항목 성격을 보여주는 이모지를 텍스트 안에 섞어도 된다 |
| 비교박스(`.compare-box`) | `.tag`에 기존(😟/📉)·인하(😊/📈)처럼 감정을 보여주는 이모지 |
| 결론 배너(`.summary-bar`) | 문장 끝에 강조 이모지 1개 (예: 👍 ✨ 💡) |
| 화살표/흐름 표시 | "A → B"류 비교·변화는 화살표 이모지(→, ➡️)나 화살표 텍스트로 시각적 흐름을 명확히 |

이모지는 장식이 아니라 **정보 전달의 일부**다 — 같은 이모지를 같은 슬라이드에서 3번 이상 반복하지
않고, 본문 분위기(심각/긍정/긴급)에 맞는 톤으로 고른다.

### 카드 컴포넌트 (`info-card-dark.html`의 `BODY_HTML` 안에서 조합)

무료 버전이므로 아래 컴포넌트만 사용한다 (사진·복잡한 그래픽·외부 일러스트 금지):

- `.checklist` — ✅/❌ 한 줄씩, 가능/불가 체크표 (✅ 먼저, ❌ 나중)
- `.numbered-list` — 원형 숫자뱃지 + 텍스트, 순서/단계 설명용
- `.grid-cards` — 2x3 그리드, 상황별/기관별 비교용
- `.table-card` — 표(table) 형태로 대상·금액·기간·신청법 등을 정리할 때
- `.compare-box` — **BAD vs GOOD(BEFORE→AFTER) 비교박스.** 좌측은 빨강 톤(`#F87171`)으로 기존/불리,
  우측은 초록 톤(`#34D399`, 청년 카테고리면 `#6EE7B7`)으로 신규/유리를 보여준다 (예: 기존 최고금리
  16.51% vs 인하된 15.27%). *(이전 버전에서는 컬러 카드 비교를 금지하고 체크표만 쓰도록 했었지만,
  정리된 디자인 스펙에서 명시적으로 허용 컴포넌트로 다시 포함시켰다 — 손해회피 대비 효과를 보여줄 때
  체크표보다 비교박스가 더 직관적이기 때문이다.)*
  **★ 배경 opacity 기준: `rgba(..., 0.38)`, 테두리 `rgba(..., 0.70)` — 0.10처럼 낮게 쓰면 배경
  이미지가 비쳐 내용이 안 보임. 반드시 0.35 이상으로 쓴다 ★**
- `.example-box` — 점선 테두리 박스, 구체적 예시 전용 (`예를 들면` 태그 고정). **캐러셀마다 최소
  1장은 이 컴포넌트로 구체적 예시 슬라이드를 따로 만든다.** 체크표/번호리스트와 같은 슬라이드에
  합치면 1350px를 넘어가서 잘리니, **예시는 항상 단독 슬라이드로 분리**한다.
- `.disclaimer` — 면책 문구 전용, 작은 회색(`#9CA3AF`) 텍스트. 수치 예시가 있는 페이지엔 필수,
  대출 카테고리는 무조건 포함.
- `.source-text` — 출처 표기 전용, 더 작은 회색 텍스트. 마지막 본문 또는 CTA 직전 슬라이드에 둔다.
- `.summary-bar` — 모든 정보 슬라이드 하단에 쓰는 강조 한 줄 요약.
  **★ 배경 opacity: `rgba(__ACCENT_RGB__, 0.38)`, 테두리 `rgba(__ACCENT_RGB__, 0.70)` — 0.12처럼
  낮으면 배경 이미지에 묻힘. 0.35 이상 유지 ★**

이 환경(Cowork 샌드박스)에서는 헤드리스 브라우저나 시스템 패키지(wkhtmltopdf, puppeteer 등)를
설치할 수 없다는 것이 이미 확인되었다. **반드시 아래 방법대로** Claude in Chrome 확장을 통해
사용자의 실제 Chrome에서 렌더링한다.

또한 `mcp__Claude_in_Chrome__navigate`로 `file://` 경로를 여는 것은 동작하지 않는다
(URL이 `https://file:///...`로 망가짐). **로컬 HTML 파일을 직접 열려고 시도하지 않는다.**

## 검증된 방법

1. 실제 https 페이지를 하나 띄운다 (CSP가 낮은 페이지, 예: `https://example.com`)
   ```
   mcp__Claude_in_Chrome__navigate(url: "https://example.com")
   ```

2. `javascript_tool`로 `document.open() / document.write(fullHtml) / document.close()`를 실행해서
   템플릿 HTML 전체(헤드의 `<link>`, `<script>` 포함)를 그 페이지에 주입한다. 이 방식이면
   `<script src="...html2canvas...">`와 폰트 `<link>`가 classic document.write 시맨틱대로
   정상 실행/로드된다.

   ```javascript
   document.open();
   document.write(`__FULL_HTML_STRING__`);
   document.close();
   ```
   `__FULL_HTML_STRING__`은 `assets/cover-dark.html` (또는 info-card-dark.html, cta-follow.html)의
   내용에서 `__PLACEHOLDER__` 들을 오늘의 카피로 치환한 최종 HTML 문자열이다.

3. html2canvas 로드 완료 + 폰트 로드 완료를 기다린다:
   ```javascript
   while (typeof window.html2canvas === 'undefined') {
     await new Promise(r => setTimeout(r, 200));
   }
   await document.fonts.ready;
   ```

4. `#slide` 엘리먼트(정확히 1080×1350)를 캡처한다:
   ```javascript
   const el = document.getElementById('slide');
   const canvas = await html2canvas(el, { width: 1080, height: 1350, scale: 1 });
   ```

5. 캔버스를 PNG blob으로 변환 후, Cloudinary에 **서명 업로드**로 직접 올린다
   (base64 문자열을 도구 호출 텍스트로 주고받지 않기 위해 — 페이지 JS 컨텍스트 안에서 끝낸다):

   ```javascript
   const blob = await new Promise(res => canvas.toBlob(res, 'image/png'));

   const timestamp = Math.floor(Date.now() / 1000);
   const apiSecret = '__CLOUDINARY_API_SECRET__';
   const toSign = `timestamp=${timestamp}${apiSecret}`;
   const hashBuffer = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(toSign));
   const signature = Array.from(new Uint8Array(hashBuffer))
     .map(b => b.toString(16).padStart(2, '0')).join('');

   const formData = new FormData();
   formData.append('file', blob, 'slide.png');
   formData.append('api_key', '__CLOUDINARY_API_KEY__');
   formData.append('timestamp', timestamp);
   formData.append('signature', signature);

   const res = await fetch(
     'https://api.cloudinary.com/v1_1/__CLOUDINARY_CLOUD_NAME__/image/upload',
     { method: 'POST', body: formData }
   );
   const data = await res.json();
   // data.secure_url 이 업로드된 이미지 URL
   ```

6. `data.secure_url`을 기록하고, 다음 슬라이드를 위해 2번부터 반복한다 (같은 탭을 재사용해도 되고,
   매번 `https://example.com`으로 다시 navigate해도 된다 — 매번 새 HTML을 document.write 하면
   이전 슬라이드의 DOM은 자동으로 사라진다).

7. **로컬 저장 (새 단계)** — 모든 슬라이드의 `secure_url`을 순서대로 모은 뒤, bash로 다운로드해서
   저장 규칙에 따른 폴더에 `01.png, 02.png, ...` 순서로 저장한다:
   ```bash
   # WORKDIR = 이 워크스페이스(insta_auto) 절대경로. 환경변수 있으면 그걸, 없으면 스킬 기준 상대경로.
   WORKDIR="${INSTA_AUTO_HOME:-$(cd "$(dirname "$0")/../../.." 2>/dev/null && pwd)}"
   mkdir -p "$WORKDIR/$(date +%F)"
   i=1
   for url in "URL1" "URL2" "URL3"; do
     n=$(printf "%02d" "$i")
     curl -sL "$url" -o "$WORKDIR/$(date +%F)/${n}.png"
     i=$((i+1))
   done
   ```
   (경로를 모르면 Claude가 이 워크스페이스의 실제 절대경로를 넣어 실행한다 — Win/Mac 공용.)
   (여러 건을 한 번에 작업하는 경우엔 `{날짜}/{순번_지원금제목}/` 하위폴더로 분리한다.)

## 주의사항

- 슬라이드 순서를 반드시 기억해서 secure_url 리스트를 **카드뉴스가 보여질 순서대로** 유지한다
  (4단계에서 컨테이너 생성 순서 = 캐러셀에 보일 순서가 된다. 로컬 저장 파일명 순서도 동일해야 한다).
- `.env`의 Cloudinary 값(`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`)은
  절대 채팅이나 파일에 평문으로 다시 출력하지 않는다 — JS 코드 문자열 안에 직접 삽입해서만 사용한다.

## CTA 슬라이드 — 고정형 단일 디자인 (★A/B 선택 폐지★)

이전엔 `cta-follow.html`(팔로우 유도)과 `cta-comment.html`(댓글 유도) 중 상황에 맞춰 골랐지만,
무료 버전 정책 변경으로 **CTA는 이제 `cta-follow.html` 하나로 고정**한다 (댓글 유도형은 무료
버전에 넣지 않는다 — `cta-comment.html` 파일은 레거시로 남겨두되 기본 흐름에서는 더 이상 쓰지
않는다). 카피도 고정이라 매번 새로 쓰지 않는다 — `references/copywriting.md`의 CTA 절 참고.

레이아웃도 다른 정보 슬라이드와 같은 원칙으로 **세로 중앙정렬**한다 — 후크 문구 → 팔로우 카드 →
안내 문구 → 보조 문구 순서를 하나의 덩어리로 보고, `#slide`를
`display:flex; flex-direction:column; justify-content:center; align-items:center;`로 둬서
이 덩어리의 수직 중심이 캔버스 중앙(세로 약 50% 지점) 근처에 오게 한다. 무게중심이 아래로
처지지 않게 — 카드만 아래쪽에 붙고 위가 텅 비는 배치는 피한다.

**CTA 확정 크기(★개정★, 기존보다 전반적으로 키움)**: 상단 후크(`.headline`) `80px`/2줄/중앙,
원형 프로필(`.avatar`) `160px`, 핸들(`.handle`) `48px`/굵기 `900`, 카드 폭(`.card`)은 캔버스의
약 80%(`864px`), 팔로우 버튼 문구는 "팔로우"가 아니라 **"팔로우 +"**로 바꿔서 행동 유도를 더
명확히 한다, 카드 아래 안내문(`.guide-text`) `46px`, 가장 아래 보조문(`.small-text`) `30px`.

## CTA 슬라이드의 프로필 사진

`cta-follow.html`의 원형 아바타는 실제 사진(`~/Desktop/insta_auto/IMG_5586.jpg`)을 쓴다. 채팅에
첨부된 이미지는 파일로 직접 접근할 수 없으므로, 사용자가 미리 그 파일을 폴더에 저장해두고, 아래
순서로 임베드한다:

1. bash에서 PIL 등으로 정사각형 center-crop + 리사이즈(예: 256×256) + JPEG 압축
2. `base64 -w0`으로 인코딩
3. `<img src="data:image/jpeg;base64,...">`로 HTML 템플릿 문자열에 직접 삽입 (브라우저로부터 base64를
   *받아오는* 것은 차단되지만, 이렇게 *입력으로 주입*하는 것은 차단되지 않는다 — 입력/출력 경로가 다름)
4. 결과 데이터 URI가 너무 크면(수십만 자 이상) 압축률을 더 높인다 — 15,000자 전후면 안전하다

## 레거시 — 사진 배경 표지(`cover.html`)를 쓸 경우 주의사항

`cover.html`은 외부 사진(`picsum.photos`/`loremflickr`)을 배경으로 쓰는 템플릿이라 다른 슬라이드와
다른 문제가 생긴다 — CSS `background-image`로 넣으면 html2canvas가 로드를 기다려주지 않거나
cross-origin 이미지라 캡처에 빈 칸으로 나오는 경우가 있다. 현재 기본 흐름은 배경 사진을 **로컬
`_bg.jpg` 파일(file:// URL)로 먼저 내려받아** `cover-dark.html`에 넣으므로 cross-origin 문제가
없다 — 평소엔 이 legacy 주의사항을 신경 쓸 필요 없다. 사진 배경 표지를 굳이 써야 한다면, `<img id="bgimg"
crossorigin="anonymous">` 방식 + 로드 대기 + `useCORS:true` 옵션이 필요하다는 점만 기억해둔다
(예전 버전 기록 참고).
