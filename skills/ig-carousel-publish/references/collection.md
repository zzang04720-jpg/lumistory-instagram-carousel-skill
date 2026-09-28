# 글 수집

기본 SITE_URL은 `https://lumiestorytech.com`이다. `/rss.xml`의 `/skills/<slug>/` 글만 읽는다. `fetch_article()`은 `.skill-hero h1`, `.skill-hero .lead`, `section.easy .easy-one p`, easy-block의 “왜 필요한가요?”, “이럴 때 도움이 돼요” 설명을 사용한다. 필수 설명을 읽지 못하면 중단한다.

단계 목록은 본문 제목의 구간 안에서 목록 또는 하위 제목을 읽는다. 다음 동급·상위 제목을 넘어서 다른 구간의 목록을 가져오지 않는다. 다운로드는 `.skill-download a.file-button`의 `/downloads/` 링크가 실제 있을 때만 기록한다.

원문 구조가 다른 사이트는 SITE_URL 설정만으로 지원되지 않는다. 수집기를 수정하거나 `examples/article.json`과 동일한 Article 구조의 검증한 자료를 입력한다. JSON의 URL도 설정된 사이트의 `/skills/<slug>/` 주소여야 한다. 예제는 연습용이며 실제 게시 자료로 취급하지 않는다.
