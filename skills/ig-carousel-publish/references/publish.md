# 미리보기에서 발행까지

1. `python instagram_cli.py preview --url <원문 주소> --theme 1` → 로컬 PNG 7장과 preview manifest.
2. 카드·캡션을 검토하고 승인 후 `python instagram_cli.py stage "<manifest.json>" --reviewed` → Cloudinary 외부 업로드와 Instagram 미공개 컨테이너.
3. 공개 승인 후 `python instagram_cli.py publish "<manifest.json>" --confirm` → 공개 게시 및 published manifest/이력.

stage는 외부 전송이며 Cloudinary 파일은 공개 URL이다. 이미 staged인 manifest는 재업로드하지 않는다. published manifest는 같은 게시물 ID 또는 링크를 돌려준다. 잘못된 상태·손상된 게시 이력은 중단한다.

최근 24시간의 같은/매우 유사한 캡션을 검사한다. 자동 실행기는 원문 URL 기록도 확인한다. 수동 재게시를 영구 차단하는 기능은 아니다. 오류나 타임아웃은 실제 게시 여부와 다를 수 있으므로 manifest와 계정을 확인하고 재시도한다. 로그와 manifest를 함께 보관한다.
