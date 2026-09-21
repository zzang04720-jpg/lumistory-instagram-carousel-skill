# 루미스토리로 인스타 카드뉴스 자동발행 스킬

Claude Code 스킬 + 실행 프로그램. 사이트 글(또는 정부 지원금 정보)을 **인스타그램 카드뉴스(캐러셀)** 로 만들고,
미리보기 확인 후 발행까지 자동으로 처리합니다. 무료로 자유롭게 사용·수정·재배포할 수 있습니다 (MIT).

## 구성
| 경로 | 설명 |
|---|---|
| `skills/ig-carousel-publish/` | Claude Code 스킬 (SKILL.md + 템플릿 + 참고 문서) |
| `app.py` | Streamlit 화면 (글 선택 → 카드 생성 → 확인 → 발행, Claude/Codex 로그인 패널 포함) |
| `lumistory_*.py`, `publish_pipeline.py` | 카드 렌더링·캡션·업로드·발행·DM 자동응답 |
| `run_insta_daily.bat`, `run_insta_dm.bat` | Windows 작업 스케줄러용 예약 실행 |
| `start_app.bat` | 화면 실행 (더블클릭) |

## 설치
```bash
git clone <이 저장소 주소>
cd <폴더>
python -m venv .venv
.venv\Scripts\pip install streamlit playwright httpx requests beautifulsoup4 python-dotenv pillow   # Mac/Linux: .venv/bin/pip
.venv\Scripts\python -m playwright install chromium
copy .env.example .env      # Mac/Linux: cp .env.example .env
```
`.env`에 본인의 값을 채웁니다 (절대 커밋 금지, `.gitignore`에 포함됨):
`SITE_URL`(카드뉴스로 만들 글이 올라오는 본인 사이트, RSS `/rss.xml` 필요), `IG_ACCESS_TOKEN`, `IG_BUSINESS_ACCOUNT_ID`, `CLOUDINARY_*`, `PEXELS_API_KEY`(선택).
인스타 API 발급 절차는 `skills/ig-carousel-publish/references/setup.md` 참고.

## 사용
- **Claude Code 스킬로:** 스킬을 사용하려면 `skills/ig-carousel-publish` 폴더를 프로젝트의 `.claude/skills/` (또는 `~/.claude/skills/`)에 복사한 뒤
  "오늘 카드뉴스 만들어줘" 라고 말합니다.
- **화면으로:** `start_app.bat` 실행 → http://127.0.0.1:8501
- **예약 발행:** `skills/ig-carousel-publish/references/schedule.md` 참고.

## 주의
- 발행은 항상 미리보기 확인 후 진행합니다. 실제 게시는 되돌릴 수 없습니다.
- 인스타그램/Meta 정책과 API 사용 약관은 사용자 책임으로 준수하세요.
- `.env`의 `SITE_URL`에 본인 사이트 주소를 넣어야 실행됩니다 (`{SITE_URL}/rss.xml` 에서 글 목록을 읽습니다).
