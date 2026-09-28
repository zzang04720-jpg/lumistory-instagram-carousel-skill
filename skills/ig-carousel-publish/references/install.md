# 설치

전체 저장소를 받아 루트 README의 설치 명령을 따른다. Python 3.10 이상, 로컬 `.venv`, `requirements.txt`가 기준이다. Windows는 `.venv\Scripts\python`, macOS/Linux는 `.venv/bin/python`을 사용한다.

`python instagram_cli.py doctor`가 로컬 의존성과 10개 글꼴을 확인한다. `python instagram_cli.py preview --article-json examples/article.json --theme 1`은 네트워크 없이 첫 결과를 만든다. 미리보기에는 Instagram/Cloudinary 키가 필요하지 않다.

AI에게는 루트 SKILL.md를 읽으라고 요청한다. 스킬 폴더에 등록하는 경우도 전체 저장소를 넣어 실행 파일·글꼴·지침의 상대 경로를 유지한다. 이 references 폴더나 하위 SKILL.md만 복사하지 않는다.
