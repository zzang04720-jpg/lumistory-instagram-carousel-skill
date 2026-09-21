# 인스타그램 카드뉴스 자동 발행 워크스페이스

사용자가 카드뉴스 제작·발행 관련 요청을 하면 반드시
`skills/ig-carousel-publish/SKILL.md` 를 읽고 그 단계대로 진행한다.

## 첫 실행 시 자동 실행

카드뉴스 요청이 오면 SKILL.md를 읽기 전에 아래를 먼저 실행한다 (Windows·Mac 공통):

```bash
pip install playwright httpx requests python-dotenv pillow
python -m playwright install chromium
```
(`pillow`는 배경 이미지 해상도 검사에 쓰인다 — 없으면 저해상도 필터가 관대하게 통과된다.)

## 디자인 = Blueprint 템플릿 1종 고정

표지·본문·CTA 모두 **Blueprint 템플릿 1종 고정** 구조다. 크림색(`#F7F3EC`) 배경에 검은 코너
브래킷 장식과 빨간 포인트 컬러(`BLUEPRINT_RED`, `#E63946`)로 숫자만 강조하는 순수 타이포그래피
카드이며, 사진 배경/오버레이는 쓰지 않는다. 실제로 쓰는 템플릿 파일은 3개뿐이고 8장을 아래처럼 나눠 채운다:

| 슬라이드 | 템플릿 파일 | 렌더 함수 (publish_pipeline.py) |
|---|---|---|
| 1. 표지 | `blueprint-cover.html` | `render_cover_blueprint_html:1604` |
| 2. 손실 이유 | `blueprint-content.html` | `render_loss_causes_blueprint_html:1621` |
| 3. 대상 확인 | `blueprint-content.html` | `render_target_confirm_blueprint_html:1639` |
| 4. 혜택 미리보기 | `blueprint-content.html` | `render_benefit_preview_blueprint_html:1655` |
| 5. 신청 방법 | `blueprint-content.html` | `render_method_steps_blueprint_html:1673` |
| 6. 비교 | `blueprint-content.html` | `render_compare_blueprint_html:1733` |
| 7. 팁 | `blueprint-content.html` | `render_tips_blueprint_html:1758` |
| 8. CTA | `blueprint-cta.html` | `render_cta_blueprint_html:1776` |

8장을 한 번에 렌더링하는 진입점은 `render_slides_blueprint()`(`publish_pipeline.py:1795`)이며,
`app.py`의 "콘텐츠 생성하기" 버튼과 `main()`(CLI/예약발행) 둘 다 이 함수를 호출한다. 결과물은
`out/bp_slide_1.png` ~ `bp_slide_8.png`로 저장된다.

## 주요 함수 위치 (publish_pipeline.py)

- `build_story()` — `985` — 지원금 정보를 검색해 카드뉴스용 story dict를 조립하는 최상위 함수.
- `choose_support_story()` — `860` — 키워드 유무·종류에 따라 검색 경로를 분기.
- `find_support_candidates()` — `613` — "정부지원금"처럼 포괄적인 키워드일 때, 마감임박 TOP5 /
  신규·시작 TOP5 후보를 찾아 반환 (사용자가 그중 하나를 선택하면 그 이름으로
  `search_support_by_keyword()`를 재사용).
- `render_slides_blueprint()` — `1795` — 8장 Blueprint 슬라이드를 렌더링하는 진입점.

## 사용 안 함 (죽은 코드)

아래 두 함수군은 정의만 남아있고 `app.py`/`main()` 어디에서도 호출되지 않는다. 과거 디자인
실험의 흔적이므로 새 기능은 여기에 얹지 말고 Blueprint 계열에 추가할 것.

- **다크 템플릿 계열** (`cover-dark.html` / `info-card-dark.html` / `cta-follow.html` 사용):
  `render_cover_html:1187`, `render_info_html:1209`, `render_benefit_html:1235`,
  `render_cta_html:1261`, `render_fact_slide_html:1286`, `render_loss_reason_html:1323`,
  `render_tips_html:1352`
- **Light 템플릿 계열** (`story-cover-light.html` / `story-light.html` / `story-cta-light.html` 사용):
  `render_cover_light_html:1376`, `render_loss_causes_html:1401`, `render_target_confirm_html:1426`,
  `render_benefit_preview_html:1447`, `render_method_steps_html:1473`,
  `render_compare_light_html:1502`, `render_tips_light_html:1546`, `render_cta_dm_html:1571`,
  그리고 이들을 묶어 호출하던 진입점 `render_slides():1863`

## 트리거 문구

- `인스타 API 발급부터 해줘` → SKILL.md 0단계 (최초 설정)
- `오늘 카드뉴스 만들어줘` → SKILL.md 전체 실행 (수집→생성→발행)
- `○○ 검색해서 카드뉴스 만들어줘` / `○○로 카드뉴스 만들어줘` → 그 키워드로 검색·수집 후
  전체 실행 (collection.md "0. 키워드 지정 수집"). 나머지 자동, **마지막에 미리보기 후 발행(모드 B)**
- `매일 ○○시에 자동 발행 예약해줘` → 예약 실행 모드. **클라우드/git 금지.**
  **시각은 사용자가 정한다**(11시는 예시). 이 컴퓨터의 로컬 스케줄러
  (Mac=launchd / Windows=작업 스케줄러)로만 설치한다.
  절차·시각파싱은 `skills/ig-carousel-publish/references/schedule.md`를 따른다.
  (조건: 예약 시각에 컴퓨터 켜짐 + Claude Code 로그인 상태)
