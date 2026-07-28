# Discord LLMWiki

Discord를 채팅 기록이 아니라 **재생 가능한 LLMWiki 지식 소스**로 다루는 참조 구현입니다.

## 제공 기능

- REST API 기반 채널·활성 스레드·공개 보관 스레드 과거 기록 수집
- Gateway의 메시지 생성·수정·삭제와 스레드 이벤트 실시간 기록
- SQLite 불변 이벤트 저널과 중복 전달 무해화
- 채널·스레드별 Markdown, JSONL 감사 사본, 안정적 `discord:<channel>:<message>` 인용
- 증거 검색과 `/context`, `/decisions`, `/tasks`, `/summary`, `/export-md`
- OpenAI Responses API 또는 동일 인터페이스의 로컬 요약기 교체

## 설치

핵심 저장·투영·검색·REST 백필은 Python 표준 라이브러리만 사용합니다. Gateway 봇을 실행할 때만:

```powershell
python -m pip install -r integrations/discord_llmwiki/requirements.txt
```

Discord Developer Portal에서 봇을 생성하고 `MESSAGE_CONTENT` privileged intent를 활성화합니다. 서버에서는 읽을 채널에 `VIEW_CHANNEL`, `READ_MESSAGE_HISTORY` 권한을 부여합니다.

```powershell
$env:DISCORD_BOT_TOKEN = "..."
$env:DISCORD_CHANNEL_ALLOWLIST = "123456789,987654321"
$env:OPENAI_API_KEY = "..."
$env:OPENAI_MODEL = "gpt-5.6-luna"
```

`ChatGPT` 제품 세션을 Discord에 삽입하는 구조가 아닙니다. 봇이 OpenAI API를 선택적으로 호출하며, 원본·검색·인용·체크포인트는 로컬에 남습니다.

## 실행

```powershell
# 저장소 초기화
python -m integrations.discord_llmwiki --data-root .llmwiki-discord init

# 접근 가능한 과거 메시지 수집
python -m integrations.discord_llmwiki --data-root .llmwiki-discord backfill --guild-id 123456789

# Markdown 재생성
python -m integrations.discord_llmwiki --data-root .llmwiki-discord project

# 로컬 검색
python -m integrations.discord_llmwiki --data-root .llmwiki-discord search "conversion worker"

# Gateway 및 slash commands
python -m integrations.discord_llmwiki --data-root .llmwiki-discord run-bot
```

## 생성 구조

```text
.llmwiki-discord/
├─ discord-events.sqlite3
├─ discord/
│  ├─ README.md
│  ├─ channels/
│  ├─ threads/
│  └─ raw/events.jsonl
├─ summaries/
│  ├─ rolling-summary.md
│  ├─ decisions.md
│  ├─ tasks.md
│  └─ unresolved-questions.md
└─ DISCORD_MEMORY.md
```

SQLite 저널만 원본입니다. 나머지는 삭제 후 `project` 또는 `summarize`로 재생성할 수 있습니다.

## 운영 경계

- 비공개 보관 스레드는 봇의 멤버십과 Discord 권한에 따라 REST 결과가 달라지므로 자동 우회하지 않습니다.
- 첨부파일은 기본적으로 다운로드하지 않고 Discord CDN 메타데이터와 링크만 보존합니다.
- Discord 본문은 프롬프트 인젝션 가능성이 있는 비신뢰 데이터로 취급합니다.
- 채널 allowlist는 필수입니다. 모든 채널을 의도적으로 허용할 때만 `*`를 지정합니다.
- 참조 slash commands는 교차채널 ACL 필터가 완성될 때까지 서버 관리자 전용입니다.
- OpenAI 호출은 `store: false`를 사용하지만, 조직의 데이터 보존·지역 처리 정책은 별도로 검토해야 합니다.
- 봇 토큰과 API 키는 환경변수로만 전달하며 이벤트 저널에 기록하지 않습니다.

## 테스트

```powershell
python -m pytest integrations/discord_llmwiki/tests -q
```
