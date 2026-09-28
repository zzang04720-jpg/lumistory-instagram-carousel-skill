# 루미스토리 인스타그램 캐러셀

사이트의 스킬 소개 글을 **1080×1350 PNG 7장과 캡션**으로 만드는 Python 프로그램과 AI 작업 지침입니다. Pillow와 동봉 글꼴로 10가지 디자인을 제공합니다. 이 저장소 폴더만으로 설치·미리보기·검토 후 Instagram 발행을 실행할 수 있습니다.

기본 입력은 루미스토리 사이트입니다. 다른 사이트는 `SITE_URL`만 바꾸는 것으로 충분하지 않습니다. `/rss.xml`, `/skills/<slug>/` 주소와 본문 구조가 맞아야 하며, 구조가 다르면 `lumistory_cards.py`의 수집기를 수정해야 합니다. 임의의 키워드 검색이나 모든 블로그를 자동 수집하는 기능은 없습니다.

## 1. 설치 (Python 3.10 이상)

GitHub의 Code → Download ZIP으로 전체 저장소를 받아 압축을 풀거나 다음 명령을 실행하세요.

```powershell
git clone https://github.com/zzang04720-jpg/lumistory-instagram-carousel-skill.git
cd lumistory-instagram-carousel-skill
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python instagram_cli.py doctor
```

macOS/Linux는 `.venv\Scripts\python` 대신 `.venv/bin/python`을 사용하세요. `doctor`는 설치된 라이브러리와 글꼴만 확인하며 네트워크나 비밀키를 읽지 않습니다. AI CLI 로그인과 브라우저 설치는 카드 생성에 필요하지 않습니다.

## 2. 계정 없이 미리보기

```powershell
.venv\Scripts\python instagram_cli.py preview --article-json examples/article.json --theme 1
```

위 예제는 연습용 자료입니다. 외부 요청 없이 `out/lumistory/<실행별 폴더>/`에 `01.png`~`07.png`와 `manifest.json`을 만듭니다. 테마는 1~10번입니다. 실제 공개 글은 다음처럼 읽습니다.

```powershell
.venv\Scripts\python instagram_cli.py preview --url https://lumiestorytech.com/skills/lumistory-instagram-carousel/ --theme 1
.venv\Scripts\python -m streamlit run app.py
```

화면에서는 글 선택 → 디자인 선택 → 카드와 캡션 검토 → 발행 준비 → 공개 발행 순으로 진행합니다. `start_app.bat`으로도 화면을 열 수 있습니다. 저장된 미발행 카드도 다시 열 수 있습니다. 생성 문구는 원문 발췌이므로 전체 카드의 잘림과 사실 관계를 직접 확인하세요.

## 3. 검토 후 발행

`copy .env.example .env`로 설정 파일을 만들고 자신의 Instagram 계정 ID·토큰과 Cloudinary 설정을 채우세요. 미리보기에는 이 값이 필요하지 않습니다. `.env`나 발행/DM 기록을 공유하지 마세요.

```powershell
.venv\Scripts\python instagram_cli.py stage "out/lumistory/<실행별 폴더>/manifest.json" --reviewed
.venv\Scripts\python instagram_cli.py publish "out/lumistory/<실행별 폴더>/manifest.json" --confirm
```

`stage`는 Cloudinary에 이미지를 업로드하고 Instagram 미공개 컨테이너를 만듭니다. Cloudinary 파일은 공개 URL이므로 여기부터 외부 전송입니다. `publish`가 실제 게시합니다. 계정 권한·토큰·API 버전은 계정 환경에서 확인해야 합니다. 오류 후 다시 실행할 때는 먼저 manifest와 실제 게시 상태를 확인하세요.

최근 24시간의 유사 캡션 중복을 검사합니다. 자동 예약은 발행 이력의 원문 URL도 건너뜁니다. 모든 수동 재게시를 영구 차단하는 기능은 아닙니다. `published_log.json`을 지우면 중복 확인 정보도 사라집니다.

## 4. 선택 기능

- **댓글 DM**: 기본은 꺼짐. 실제 답장을 준비한 경우에만 화면의 DM 문구 옵션 또는 `preview --include-dm`을 사용하세요. 별도 실행기는 `lumistory_dm_auto.py`이며 `IG_AUTO_DM=1`일 때만 전송합니다. 계정 권한과 API 지원 여부를 확인해야 하며, 팔로우 여부를 확인하는 기능은 없습니다.
- **예약 발행**: `lumistory_auto.py`는 `IG_AUTO_PUBLISH=1`일 때만 실제 자동 발행합니다. Windows 실행 파일은 기본 비활성 상태를 유지합니다. 설정한 시각에 컴퓨터가 켜져 있어야 합니다. [예약 안내](skills/ig-carousel-publish/references/schedule.md)를 읽고 사용자가 요청한 주기로만 등록하세요.
- **AI 작업 지침**: 이 전체 폴더를 유지하고 AI에게 루트 `SKILL.md`를 읽도록 요청하세요. 스킬 등록 시에도 코드·글꼴을 포함한 전체 폴더를 사용하세요. `skills/ig-carousel-publish`만 복사하면 실행 파일이 빠집니다.

## 구성과 검증

| 파일 | 역할 |
|---|---|
| `lumistory_cards.py` | 수집·원문 발췌·7장 Pillow 렌더링 |
| `lumistory_publish.py` | manifest 검증·준비·공개·기록 |
| `publish_pipeline.py` | Cloudinary와 Instagram API 함수 |
| `instagram_cli.py` | doctor / preview / stage / publish |
| `app.py` | Streamlit 검토 화면 |
| `lumistory_auto.py`, `lumistory_dm_auto.py` | 각각 선택적 예약·댓글 DM |

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

테스트는 네트워크 없는 10개 테마 렌더링, 본문 구간 추출, 독립 import, 발행 상태 경계를 검증합니다. 실제 계정 발행과 DM 성공을 보증하는 테스트는 아닙니다. 코드는 MIT, 동봉 글꼴은 각각의 OFL 라이선스를 따릅니다.
