# univnotice_bot

대학 공지 페이지를 주기적으로 확인하고, 새 공지가 있으면 Discord로 알려 줍니다.

## Discord: 채널 만들기 & 웹훅 만들기

각 공지 출처(경제학부 / 인공지능 연합전공 / 경영대학)마다 **다른 텍스트 채널**로 보내려면, 채널마다 **Incoming Webhook**을 하나씩 만듭니다.

### 1) 채널 만들기

1. Discord 서버에서 **채널 추가** → **텍스트 채널** (예: `#공지-경제학부`, `#공지-인공지능`, `#공지-경영`).
2. 필요하면 카테고리로 묶어 두면 관리가 편합니다.

### 2) 웹훅 만들기 (채널마다 반복)

1. 해당 **텍스트 채널**에서 톱니바퀴(채널 설정) → **연동** → **웹후크** → **새 웹후크**.
2. 이름·아바타는 원하는 대로 설정합니다.
3. **웹후크 URL 복사** — 이 URL이 곧 `DISCORD_WEBHOOK_*` Secret에 넣을 값입니다.
4. 나머지 두 채널에도 동일하게 웹훅을 만들어 **채널마다 URL이 서로 다른지** 확인합니다.

> 웹훅 URL은 비밀과 같습니다. **공개 저장소나 채팅에 붙여 넣지 마세요.**

### 3) GitHub 저장소에 Secret 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

`crawler.py`의 `webhook_env`와 **이름이 정확히 같아야** 합니다.

| Secret 이름 | 용도 |
|-------------|------|
| `DISCORD_WEBHOOK_ECON` | 서울대 경제학부 공지 → 해당 채널 웹훅 URL |
| `DISCORD_WEBHOOK_IMAI` | 인공지능 연합전공 공지 |
| `DISCORD_WEBHOOK_CBA` | 경영대학 공지 |

선택 사항:

| Secret 이름 | 용도 |
|-------------|------|
| `DISCORD_WEBHOOK_URL` | 위 세 개 중 하나라도 비어 있을 때 **폴백**으로 쓰는 단일 웹훅 (없어도 됨) |

### 4) 로컬에서 테스트할 때

PowerShell 예시:

```powershell
$env:DISCORD_WEBHOOK_ECON = "https://discord.com/api/webhooks/..."
$env:DISCORD_WEBHOOK_IMAI = "https://discord.com/api/webhooks/..."
$env:DISCORD_WEBHOOK_CBA = "https://discord.com/api/webhooks/..."
python crawler.py
```

환경변수를 설정하지 않으면 **로컬 테스트 모드**로, 디스코드로는 보내지 않고 콘솔에만 메시지를 출력합니다.

## 동작 요약

- 스케줄/수동 실행은 `.github/workflows/main.yml`을 참고하세요.
- 상태는 `latest_links.json`에 저장되며, GitHub Actions가 변경 시 커밋할 수 있습니다.

## 지금 바로 “채널 라우팅”이 맞는지 확인하기 (새 공지 없어도 됨)

GitHub Actions를 수동 실행할 때 `test_webhooks=true`로 실행하면, **사이트별로 1개의 테스트 메시지**를 각 채널로 보냅니다.

로컬 테스트:

```powershell
$env:TEST_WEBHOOKS = \"1\"
python crawler.py
```
