---
name: ig-carousel-publish
description: 전체 Instagram 저장소 안에서만 사용하는 호환 진입점. Instagram 카드뉴스 제작·검토·발행을 루트 실행 프로그램으로 처리한다.
---

# Instagram 호환 진입점

실제 지침은 저장소 루트의 [SKILL.md](../../SKILL.md)이다. 먼저 그 파일을 읽고 따른다.

이 하위 폴더만 별도로 설치하지 않는다. `../../instagram_cli.py`, `../../lumistory_cards.py`, `../../lumistory_fonts/`를 포함한 전체 저장소가 필요하다. 누락 시 전체 ZIP을 요청한다. 현재 구현은 Pillow PNG 7장과 10개 테마이며, 필요한 Python 라이브러리는 루트 `requirements.txt`에 있다.
