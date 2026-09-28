---
name: lumistory-instagram-carousel
description: Instagram 캐러셀 카드뉴스 제작, 사이트 글 기반 미리보기, 검토한 카드 발행, 예약 실행 또는 선택적 댓글 DM을 요청할 때 사용한다.
---

# 인스타그램 카드뉴스 제작

## 범위와 실행 위치

이 스킬은 **Instagram 전용**이다. 전체 저장소 폴더가 하나의 실행 단위다. 이 파일 옆 `instagram_cli.py`, `requirements.txt`, `lumistory_fonts/`가 있는지 먼저 확인한다. 파일이 없으면 전체 ZIP을 다시 받아야 한다. 다른 저장소에서 모듈을 가져오지 않는다.

원문을 발췌해 PNG 7장(1080×1350)과 캡션을 만들며 10개 테마를 제공한다. 생성 자체는 AI CLI를 호출하지 않는다. 기본 수집 대상은 `https://lumiestorytech.com`의 RSS와 스킬 소개 글이다. 임의 사이트·검색어를 지원한다고 약속하지 않는다. 자세한 입력 계약은 [수집 안내](skills/ig-carousel-publish/references/collection.md)를 읽는다.

## 실행 순서

1. 저장소 루트에서 Python 3.10 이상으로 `.venv`를 만들고 `python -m pip install -r requirements.txt`를 실행한다. 이후 명령의 `python`은 해당 가상환경 실행 파일이다. 이미 설치되어 있으면 재설치하지 말고 `python instagram_cli.py doctor`로 확인한다.
2. 첫 실행은 `python instagram_cli.py preview --article-json examples/article.json --theme 1`로 오프라인 예제를 만든다. 실제 원문은 `preview --url <원문 URL> --theme <1~10>`을 사용한다. 계정 설정 없이 가능하다.
3. 반환된 manifest의 이미지 7장과 캡션을 사용자에게 보여 준다. 파일 생성은 발행 성공이 아니다. 출처 사실·글자 잘림·표시 오류를 확인한다. 원문에 없는 효과·체험·숫자를 만들어 넣지 않는다.
4. 사용자가 게시할 내용을 승인하면 [계정 설정](skills/ig-carousel-publish/references/setup.md)을 확인하고 `python instagram_cli.py stage "<manifest.json>" --reviewed`로 외부 업로드와 미공개 준비를 한다. 이 단계의 Cloudinary 이미지는 공개 URL이다.
5. 공개 발행까지 승인된 경우 `python instagram_cli.py publish "<manifest.json>" --confirm`을 실행한다. manifest의 `published_post_id`/`permalink`와 실제 결과를 기준으로 보고한다. 미리보기 요청만으로 공개하지 않는다.

화면은 `python -m streamlit run app.py`로 연다. 저장된 preview/staged manifest를 다시 열어 이어서 검토할 수 있다.

## 선택적 자동화

사용자가 예약을 요청한 경우에만 [예약 안내](skills/ig-carousel-publish/references/schedule.md)를 따른다. `IG_AUTO_PUBLISH=1`은 이후 무인 공개 발행에 대한 선택이다. 기본 실행 파일은 이를 자동으로 설정하지 않는다.

댓글 DM은 별도 기능이다. `IG_AUTO_DM=1`과 계정 권한이 필요하다. DM 안내 문구는 `--include-dm` 또는 UI 옵션으로만 넣는다. 팔로우 확인 기능은 없으며, DM 지원·권한 검증 없이 전송을 약속하지 않는다. 자동 예약에서 DM 문구를 넣으려면 별도 `IG_INCLUDE_DM_CTA=1`을 설정한다.

## 유지보수

변경 후 `python -m unittest discover -s tests -v`로 오프라인 회귀 테스트를 실행한다. 새 원문 구조는 실제 HTML을 확인한 뒤 수집기와 테스트를 함께 수정한다. 출력물·계정 설정·기록은 Git에 넣지 않는다.
