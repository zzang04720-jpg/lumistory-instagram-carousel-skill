# 매일 자동 발행 예약 (로컬 방식 · Windows/Mac 공통)

> **이 방식은 클라우드도 git도 쓰지 않는다.** 사용자의 **컴퓨터가 켜져 있고**,
> **Claude Code에 로그인된 상태**일 때만 예약 시각에 이 컴퓨터에서 직접 실행된다.
> (컴퓨터가 꺼져 있거나 로그아웃 상태면 그 날은 실행되지 않는다. 클라우드에서 대신
> 돌려주지 않는다 — 그게 이 방식의 핵심이다.)

사용자가 아래처럼 말하면 이 문서대로 **예약을 자동으로 설치**한다. **시각은 사용자가 정한다**
(아래 11시는 예시일 뿐, 사용자가 말한 시각을 그대로 쓴다):

- `매일 오전 11시에 자동 발행해줘` → 11:00
- `매일 저녁 9시에 자동 발행 예약해줘` → 21:00
- `아침 8시 30분에 올려줘` → 08:30
- `자동 발행 예약 걸어줘` → **시각을 말 안 했으면 "몇 시에 올릴까요? (예: 오전 11시)"라고 한 번 물어본 뒤** 설치. 끝내 안 정하면 기본 11:00.

### 시각 결정 규칙 (설치 전에 반드시)
1. 사용자 문장에서 시/분을 파싱한다. "오전/아침"=AM, "오후/저녁/밤"=PM(12+시).
   "10시반"=10:30, "정오"=12:00, "자정"=00:00.
2. 24시간제 `HOUR`(0~23)·`MINUTE`(0~59) 두 값으로 변환한다.
3. 아래 설치 템플릿의 시각 자리(예시 11/0)에 이 `HOUR`/`MINUTE`를 넣는다.
4. 나중에 "자동 발행 시간 ○시로 바꿔줘"라고 하면 같은 규칙으로 재설정한다(4번 '시간변경' 참고).

---

## 0. 설치 전에 사용자에게 꼭 안내할 것 (아주 친절하게, 그대로 읽어주기)

예약을 걸기 전에 다음을 사람이 알아듣게 설명한다:

> 📌 **이 자동 발행은 "내 컴퓨터"에서 돌아갑니다 (클라우드 아님).**
> 그래서 매일 예약 시각(예: 오전 11시)에 아래 2가지가 지켜져야 자동으로 올라갑니다.
>
> 1. **컴퓨터가 켜져 있어야 해요.** (완전히 꺼두면 그 날은 건너뜁니다.
>    노트북 덮개를 닫아 잠자기 상태여도, 맥은 깨어날 때, 윈도우는 로그인할 때 이어서 실행돼요.)
> 2. **Claude Code에 로그인돼 있어야 해요.** (한 번 로그인해두면 계속 유지됩니다.
>    로그아웃했거나 토큰이 만료되면 다시 로그인만 하면 됩니다.)
>
> 이 2가지만 지키면 나머지는 컴퓨터가 알아서 매일 만들어 올립니다. 설정은 지금 1번만 하면 끝이에요.

그 다음, **사용자의 운영체제를 확인**한다 (모르면 물어보거나 아래 명령으로 감지).

---

## 1. 공통: Claude Code 실행 파일(claude) 경로 찾기

예약 스크립트는 이 컴퓨터에 설치된 **로컬 claude 실행 파일**을 직접 부른다. 아래 순서로 탐지한다.

**Mac / Linux:**
```bash
# 1순위: PATH에 등록된 claude
CLAUDE="$(command -v claude 2>/dev/null)"
# 2순위: VS Code 확장에 번들된 네이티브 바이너리
[ -z "$CLAUDE" ] && CLAUDE="$(ls ~/.vscode/extensions/anthropic.claude-code-*-darwin-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)"
[ -z "$CLAUDE" ] && CLAUDE="$(ls ~/.vscode/extensions/anthropic.claude-code-*-linux-*/resources/native-binary/claude 2>/dev/null | sort -V | tail -1)"
echo "$CLAUDE"
```

**Windows (PowerShell):**
```powershell
# 1순위: PATH의 claude
$claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
# 2순위: npm 전역 설치
if (-not $claude) { $claude = "$env:APPDATA\npm\claude.cmd"; if (-not (Test-Path $claude)) { $claude = $null } }
# 3순위: VS Code 확장 번들
if (-not $claude) {
  $claude = (Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*-win32-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1).FullName
}
$claude
```

탐지에 실패하면 → **3번 "안 될 때 자동 해결"** 로 간다.

`WORKDIR` 은 이 스킬이 설치된 사용자의 실제 `insta_auto` 폴더 절대경로다 (설치 시점에 Claude가 알고 있는 경로를 그대로 넣는다).

---

## 2-A. Mac 설치 (launchd)

### ① 실행 스크립트 생성 — `<WORKDIR>/run_insta_daily.sh`
```bash
#!/bin/bash
export HOME="/Users/<사용자>"
export PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
export IG_AUTO_PUBLISH=1     # ★모드 A(예약): 캡션까지 완성 후 확인 없이 끝까지 발행

CLAUDE="<위에서 탐지한 claude 절대경로>"
WORKDIR="<WORKDIR>"
LOG="$WORKDIR/auto_run.log"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 시작 ===" >> "$LOG"
"$CLAUDE" \
  --dangerously-skip-permissions \
  --print \
  -p "ig-carousel-publish 스킬로 오늘 정부 지원금 카드뉴스 만들어서 인스타에 자동 발행. <WORKDIR>/skills/ig-carousel-publish/SKILL.md 0~5단계 완전 자동 실행(모드 A). 캡션도 copywriting.md '캡션 공식'대로 반드시 완성할 것. 모든 경로는 절대경로(<WORKDIR>/...)로 작성." \
  "$WORKDIR" >> "$LOG" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') 완료 ===" >> "$LOG"
```
```bash
chmod +x "<WORKDIR>/run_insta_daily.sh"
```

### ② launchd 예약 등록 — `~/Library/LaunchAgents/com.insta_auto.daily.plist`
`Hour`/`Minute` 에 **사용자가 정한 `HOUR`/`MINUTE`**(아래는 11:00 예시)를 넣는다.
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.insta_auto.daily</string>
    <key>ProgramArguments</key>
    <array><string>/bin/bash</string><string><WORKDIR>/run_insta_daily.sh</string></array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string><WORKDIR>/launchd.log</string>
    <key>StandardErrorPath</key><string><WORKDIR>/launchd_err.log</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>
```

### ③ 로드(적용)
```bash
launchctl unload ~/Library/LaunchAgents/com.insta_auto.daily.plist 2>/dev/null
launchctl load  ~/Library/LaunchAgents/com.insta_auto.daily.plist
launchctl list | grep com.insta_auto.daily   # 목록에 뜨면 등록 성공
```

---

## 2-B. Windows 설치 (작업 스케줄러 / schtasks)

### ① 실행 스크립트 생성 — `<WORKDIR>\run_insta_daily.bat`
```bat
@echo off
set "WORKDIR=<WORKDIR>"
set "CLAUDE=<위에서 탐지한 claude 경로>"
set "IG_AUTO_PUBLISH=1"     REM ★모드 A(예약): 캡션까지 완성 후 확인 없이 끝까지 발행
echo === %date% %time% 시작 === >> "%WORKDIR%\auto_run.log"
"%CLAUDE%" --dangerously-skip-permissions --print -p "ig-carousel-publish 스킬로 오늘 정부 지원금 카드뉴스 만들어서 인스타에 자동 발행. %WORKDIR%\skills\ig-carousel-publish\SKILL.md 0~5단계 완전 자동 실행(모드 A). 캡션도 copywriting.md '캡션 공식'대로 반드시 완성할 것. 모든 경로는 절대경로로 작성." "%WORKDIR%" >> "%WORKDIR%\auto_run.log" 2>&1
echo === %date% %time% 완료 === >> "%WORKDIR%\auto_run.log"
```

### ② 작업 스케줄러 등록 (매일, 현재 로그인 사용자 세션에서 실행)
`/ST` 에 **사용자가 정한 `HH:MM`**(아래는 11:00 예시)를 넣는다.
```powershell
schtasks /Create /TN "InstaAutoDaily" /TR "cmd /c \"<WORKDIR>\run_insta_daily.bat\"" /SC DAILY /ST 11:00 /F
```
- `/SC DAILY /ST HH:MM` = 매일 그 시각(예: `/ST 21:00` = 저녁 9시).
- 이 형식은 **로그인한 사용자 세션에서만** 돈다 → "컴퓨터 켜짐 + 로그인 상태" 조건과 일치.
- 예약 시각에 컴퓨터가 꺼져 있었으면, 켜져서 로그인한 뒤 놓친 작업을 이어서 실행하게 하려면:
  ```powershell
  schtasks /Create /TN "InstaAutoDaily" /TR "cmd /c \"<WORKDIR>\run_insta_daily.bat\"" /SC DAILY /ST 11:00 /F /RU "%USERNAME%"
  ```
  등록 후 작업 스케줄러 GUI에서 해당 작업 → 설정 → "예약된 시작 시간을 놓친 경우 최대한 빨리 작업 시작" 체크를 권장.

### ③ 확인
```powershell
schtasks /Query /TN "InstaAutoDaily"      # 등록 확인
schtasks /Run   /TN "InstaAutoDaily"      # 지금 즉시 한 번 테스트 실행
```

---

## 3. 안 될 때 "알아서" 해결 (Claude가 스스로 진단)

설치·실행이 실패하면 아래를 순서대로 스스로 시도하고, 사용자가 직접 해야 하는 것만 골라 친절히 안내한다.

| 증상 | 원인 | 자동 조치 / 사용자 안내 |
|---|---|---|
| `claude` 경로를 못 찾음 | Claude Code 미설치 or PATH 미등록 | 1번의 3순위까지 재탐지 → 그래도 없으면 사용자에게: "Claude Code를 먼저 설치/로그인해 주세요. VS Code 확장 또는 `npm i -g @anthropic-ai/claude-code`로 설치돼요." |
| 등록은 됐는데 시간 돼도 안 올라감 | 그 시각에 컴퓨터 꺼짐/잠자기·로그아웃 | `auto_run.log`·`launchd.log`에 실행 흔적 있는지 확인. 없으면 사용자에게 "그 시각에 컴퓨터가 켜져 있고 로그인돼 있어야 해요"를 다시 안내. |
| 로그에 인증/토큰 오류 | Claude Code 로그아웃 or 토큰 만료 | 사용자에게 "Claude Code를 다시 한 번 로그인해 주세요"라고 안내. 인스타 토큰이면 SKILL.md '토큰 만료 시' 절차. |
| Mac: `launchctl load` 권한/Operation not permitted | plist 경로/형식 문제 | `plutil -lint <plist>`로 검증 → 형식 고쳐 재로드. |
| Windows: schtasks Access denied | 권한 부족 | 관리자 PowerShell에서 실행하도록 안내하거나, 사용자 계정 범위(`/RU %USERNAME%`)로 재등록. |
| 발행은 됐는데 중복 | published_log.json 미기록 | SKILL.md 0단계(중복 방지) 확인. |

**항상 먼저 로그부터 본다:** `<WORKDIR>/auto_run.log` (Mac은 `launchd.log`, `launchd_err.log`도).
지금 바로 한 번 테스트로 돌려보고(Mac: `launchctl start com.insta_auto.daily` / Win: `schtasks /Run /TN InstaAutoDaily`) 로그로 결과를 확인한 뒤 사용자에게 성공/실패를 알린다.

---

## 4. 설치 끝나고 사용자에게 보고할 문구 (예시)

> ✅ 매일 오전 11시 자동 발행 예약을 **이 컴퓨터에** 걸어뒀어요. (클라우드/깃 안 씁니다.)
> - 조건: **컴퓨터 켜짐 + Claude Code 로그인 상태** → 이 2가지만 지키면 매일 알아서 올라가요.
> - 시간 바꾸고 싶으면: "자동 발행 시간 9시로 바꿔줘" 라고 말해주세요.
> - 잠깐 멈추려면: "자동 발행 예약 꺼줘" / 다시 켜려면 "자동 발행 예약 켜줘"
> - 잘 됐는지 보려면: `insta_auto/auto_run.log` 파일을 열어보면 실행 기록이 있어요.

### 예약 끄기/켜기/시간변경
- **Mac 끄기:** `launchctl unload ~/Library/LaunchAgents/com.insta_auto.daily.plist`
  **켜기:** `launchctl load ...` / **시간변경:** plist의 Hour/Minute 수정 후 unload→load.
- **Windows 끄기:** `schtasks /Change /TN InstaAutoDaily /DISABLE`
  **켜기:** `/ENABLE` / **시간변경:** `schtasks /Change /TN InstaAutoDaily /ST 09:00`
