# 4~6단계 상세 — 캐러셀 생성 및 발행

인스타그램 Graph API의 캐러셀 발행은 3단계 API 호출로 이루어진다. **컨테이너 생성(준비)과
발행(publish)은 분리되어 있다.** 발행 직전 **캡션 완성 가드**를 통과해야 하며, 3번(`media_publish`)
호출 시점은 발행 모드에 따라 다르다:
- **모드 A(예약, `IG_AUTO_PUBLISH=1`)**: 1~2번에 이어 3번까지 **확인 없이 자동** 호출.
- **모드 B(수동, 기본)**: 1~2번만 하고 멈춰서 미리보기 확인 → **사용자 승인 후에만** 3번 호출.

모든 API 호출은 bash/curl이 아니라 `mcp__Claude_in_Chrome__javascript_tool`의 `fetch()`로 실행한다
(샌드박스에서 외부 API 직접 호출이 막혀있기 때문 — gov-threads-publish 스킬과 동일한 이유).

**★호스트 주의: `graph.facebook.com`이 아니라 `graph.instagram.com`을 쓴다★** — 이 계정의
`IG_ACCESS_TOKEN`은 "Instagram API with Instagram Login"(Business Login for Instagram) 방식으로
발급된 `IGAA...` 형식 토큰이다. 이 토큰을 `graph.facebook.com`에 쓰면 `"Invalid OAuth access
token - Cannot parse access token"`(code 190) 에러가 난다 — 실제로 이 에러로 발행이 막혔다가
`graph.instagram.com`으로 바꾸자 바로 해결됐다. 아래 모든 엔드포인트는 `https://graph.instagram.com/v22.0/...`
형태로 호출한다.

**토큰이 만료/오류로 보일 때**: 바로 사용자에게 새 토큰 발급을 요청하기 전에, 먼저 refresh를
시도한다 (24시간 이상 지났고 아직 만료되지 않은 토큰이면 성공한다):
```javascript
const res = await fetch(
  `https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=${encodeURIComponent(TOKEN)}`
);
const data = await res.json();
// data.access_token 이 새 토큰 (약 60일 유효) — .env의 IG_ACCESS_TOKEN을 이 값으로 교체한다
```
이 refresh마저 실패하면(완전히 만료됨) 그때 사용자에게 Meta 앱 대시보드에서 재로그인/재인증을
요청한다.

## 1. 캐러셀 아이템(슬라이드별) 컨테이너 생성

각 슬라이드 이미지 URL마다 1번씩 호출 (순서대로):

```javascript
const res = await fetch(
  `https://graph.instagram.com/v22.0/__IG_BUSINESS_ACCOUNT_ID__/media?` +
  `image_url=${encodeURIComponent(slideImageUrl)}&is_carousel_item=true&access_token=${encodeURIComponent('__IG_ACCESS_TOKEN__')}`,
  { method: 'POST' }
);
const data = await res.json();
// data.id 가 이 슬라이드의 컨테이너 ID
```

모든 슬라이드의 컨테이너 ID를 순서대로 배열에 모은다.

## 2. 캐러셀 부모 컨테이너 생성

```javascript
const childrenParam = containerIds.join(',');
const res = await fetch(
  `https://graph.instagram.com/v22.0/__IG_BUSINESS_ACCOUNT_ID__/media?` +
  `media_type=CAROUSEL&children=${encodeURIComponent(childrenParam)}&caption=${encodeURIComponent(caption)}&access_token=${encodeURIComponent('__IG_ACCESS_TOKEN__')}`,
  { method: 'POST' }
);
const data = await res.json();
// data.id 가 캐러셀 부모 컨테이너 ID — 이것이 미리보기/발행에 쓰일 creation_id
```

**모드 B(수동)는 여기서 멈춘다.** 부모 컨테이너 ID·슬라이드 이미지 URL·캡션을 사용자에게 보여주고
승인을 기다린다. **모드 A(예약, `IG_AUTO_PUBLISH=1`)는 멈추지 않고 바로 3번으로 진행한다.**

## 3. 발행 (모드 A는 바로 / 모드 B는 사용자 확인 후)

모드 B는 사용자가 명확히 동의한 뒤에만, 모드 A(예약)는 곧바로 실행:

```javascript
const res = await fetch(
  `https://graph.instagram.com/v22.0/__IG_BUSINESS_ACCOUNT_ID__/media_publish?` +
  `creation_id=${parentContainerId}&access_token=${encodeURIComponent('__IG_ACCESS_TOKEN__')}`,
  { method: 'POST' }
);
const data = await res.json();
// data.id 가 발행된 게시물의 media ID
```

## 4. 퍼머링크 확인

```javascript
const res = await fetch(
  `https://graph.instagram.com/v22.0/${data.id}?fields=permalink&access_token=${encodeURIComponent('__IG_ACCESS_TOKEN__')}`
);
const info = await res.json();
// info.permalink
```

## 주의사항

- `media_publish` 호출은 **공개적이고 되돌릴 수 없는 행동**이다. **모드 B(수동)에서는**
  미리보기를 보여주고 명확한 동의를 받기 전까지 절대 호출하지 않는다. **모드 A(예약)에서만**
  사람이 미리 "매일 자동 발행"을 설정해둔 것이므로 확인 없이 호출한다.
- 발행 전 **캡션이 완성돼 있어야** 한다 — 비었거나 자리표시자(`...캡션 전문...`)면 발행 스크립트가
  `_assert_caption_ok`로 중단한다(두 모드 공통).
- 컨테이너 생성(1~2번)은 아직 비공개 상태이므로 자유롭게 재시도/재생성 가능하다 — 사용자가
  슬라이드나 캡션을 고치고 싶다고 하면 그냥 새로 만들면 된다.
- 컨테이너는 일정 시간 후 만료될 수 있으므로, 사용자 확인이 너무 오래 걸리면(예: 다음날)
  컨테이너를 다시 생성하는 것이 안전하다.
