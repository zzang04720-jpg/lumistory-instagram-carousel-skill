# 발행 계정 설정

미리보기에는 계정이 필요하지 않다. 공개 발행을 준비할 때만 루트 `.env.example`을 `.env`로 복사해 자신의 값을 채운다.

| 이름 | 용도 |
|---|---|
| SITE_URL | 기본 `https://lumiestorytech.com`, 같은 HTML 구조를 가진 사이트만 대체 가능 |
| IG_USER_ID | 게시할 Instagram 계정 ID |
| IG_ACCESS_TOKEN | 해당 계정과 발행 권한을 가진 토큰 |
| GRAPH_VERSION | 사용할 Graph API 버전, 기본값 v21.0 |
| CLOUDINARY_CLOUD_NAME | 이미지 업로드 대상 |
| CLOUDINARY_API_KEY | Cloudinary API 키 |
| CLOUDINARY_API_SECRET | Cloudinary 서명 비밀값 |

이 코드는 `graph.instagram.com` 경로의 Instagram Login API 방식을 사용한다. 다른 로그인 방식의 토큰과 계정 ID를 임의로 혼합하지 않는다. 계정 종류·권한·앱 모드·승인 상태·토큰 만료와 API 버전은 Meta 개발자 화면에서 현재 계정에 맞게 확인한다. 댓글 DM에는 별도의 메시징 지원 및 권한이 필요하다.

참고: [Instagram Platform 공식 문서](https://developers.facebook.com/docs/instagram-platform/), [Cloudinary 업로드 문서](https://cloudinary.com/documentation/image_upload_api_reference).

토큰을 채팅·로그·스크린샷·Git에 남기지 않는다. doctor 성공은 토큰이나 발행 API 성공을 의미하지 않는다. 본 저장소의 자동 테스트는 실계정에 게시하지 않는다.
