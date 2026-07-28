# Discord-Native LLMWiki Architecture

## Outcome

Discord 전용 LLMWiki는 대화 전체를 모델 컨텍스트에 붙여 넣는 봇이 아니다. Discord를 지속적으로 동기화되는 원본 지식 소스로 취급하고, 답변 시점에는 검증 가능한 소량의 메시지만 검색한다.

```text
Historical REST backfill       Live Gateway dispatches
          │                              │
          └────────── normalize ─────────┘
                         │
                         ▼
             append-only SQLite journal
                         │
             ┌───────────┼────────────┐
             ▼           ▼            ▼
        Markdown       Search      Summary delta
        projection     context      + prior memory
             │           │            │
             └───────────┴────┬───────┘
                              ▼
                 Discord slash-command adapter
```

## Trust Boundaries

| Boundary | Rule |
|---|---|
| Discord → journal | 모든 메시지·편집·삭제를 원본 payload와 함께 새 이벤트로 추가한다. |
| Journal → projection | 동일 이벤트 순서는 동일 Markdown과 활성 메시지 집합을 만든다. |
| Search → model | `discord:<channel_id>:<message_id>` 인용을 유지한다. |
| Discord content → prompt | 본문과 첨부파일은 비신뢰 데이터이며 내부 지시를 실행하지 않는다. |
| Model → memory | 요약은 파생물이며 원본 이벤트를 수정하거나 삭제할 수 없다. |
| Secrets → process | 봇 토큰과 API 키는 환경변수로만 전달하고 로그·저널·Markdown에 쓰지 않는다. |

## Event Contract

`schemas/DiscordEvent.json`은 다음을 고정한다.

- `event_key`: 같은 REST 항목 또는 Gateway 재전송을 무해화하는 안정적 키
- `event_type`: 메시지 및 스레드의 생성·수정·삭제
- `occurred_at`: Discord에서 사건이 발생한 시간
- `received_at`: LLMWiki가 사건을 관측한 시간
- `payload`: Discord 원본 필드와 `_llmwiki` 어댑터 메타데이터

수정은 기존 행의 덮어쓰기가 아니며 `MESSAGE_UPDATE` 추가 이벤트다. 삭제 역시 `MESSAGE_DELETE` 묘비 이벤트다. 현재 상태는 순서대로 재생해 얻는다.

## Historical Import

`DiscordRestClient`는 채널 메시지 엔드포인트를 `limit=100`과 `before`로 반복한다. 일반 텍스트·공지 채널 외에 guild active threads와 공개 archived threads를 수집한다. 비공개 archived threads는 봇 멤버십과 권한에 따라 결과가 달라지므로 권한을 우회하지 않는다.

필수 권한은 Discord의 `VIEW_CHANNEL`, `READ_MESSAGE_HISTORY`이며, 본문·첨부·embed 필드를 받으려면 `MESSAGE_CONTENT` privileged intent가 필요하다.

## Live Synchronization

선택적 `discord.py` 어댑터가 다음 dispatch를 정규화한다.

```text
MESSAGE_CREATE
MESSAGE_UPDATE
MESSAGE_DELETE
THREAD_CREATE
THREAD_UPDATE
THREAD_DELETE
```

Gateway sequence와 Discord의 resume 처리는 라이브러리에 위임하지만, 중복 dispatch가 도착해도 `event_key` 유일성 때문에 저널 결과는 변하지 않는다. 백필과 라이브 수집이 겹쳐도 동일 생성 payload는 한 번만 기록된다.

## Derived Knowledge Tree

```text
.llmwiki-discord/
├─ discord-events.sqlite3       # durable truth
├─ discord/
│  ├─ channels/*.md             # deterministic projection
│  ├─ threads/*.md              # deterministic projection
│  └─ raw/events.jsonl          # audit/export copy
├─ summaries/
│  ├─ rolling-summary.md
│  ├─ decisions.md
│  ├─ tasks.md
│  └─ unresolved-questions.md
└─ DISCORD_MEMORY.md
```

채널명은 표시용일 뿐 파일 식별자는 채널 ID를 포함한다. 이름 변경이나 같은 이름의 채널 때문에 파일이 충돌하지 않는다.

## Retrieval and Citation

참조 구현의 검색은 의존성 없는 결정적 lexical baseline이다. 운영 배포에서는 메시지를 LLMWiki SemanticUnit으로 투영해 BM25·vector·graph hybrid retrieval과 Evidence Gate를 그대로 적용한다.

각 결과는 `discord:<channel_id>:<message_id>` 인용을 가진다. 모델은 이 짧은 핸들만 보고, 호스트가 Discord 원문과 Markdown anchor로 역해결한다. WC/1을 사용할 때에도 메시지 본문은 축약하거나 재작성하지 않는다.

## Hierarchical Memory

요약 호출은 전체 Discord 기록을 다시 전송하지 않는다.

```text
previous project memory
+ events after summary checkpoint
+ explicitly retrieved supporting messages
→ refreshed project memory
```

성공적으로 파일을 기록한 뒤에만 `summary_sequence` 체크포인트를 전진시킨다. 모델 호출이 실패하면 같은 이벤트 집합을 재시도할 수 있다. 삭제·스레드 변경도 delta로 전달되어 체크포인트가 멈추지 않는다.

OpenAI 기본값은 고빈도 요약 비용을 고려한 `gpt-5.6-luna`, 낮은 reasoning effort, 낮은 verbosity, `store: false`다. 모델명은 `OPENAI_MODEL`로 교체 가능하며, 동일 `SummaryProvider` 인터페이스에 로컬 모델을 연결할 수 있다.

## Discord Commands

| Command | Behavior |
|---|---|
| `/context <query>` | 로컬 검색 결과와 안정적 메시지 인용을 반환 |
| `/summary` | 체크포인트 이후 delta만 사용해 프로젝트 메모리를 갱신 |
| `/decisions` | `DISCORD_MEMORY.md`의 Decisions Made 섹션 반환 |
| `/tasks` | Active Tasks 섹션 반환 |
| `/export-md` | 최신 결정적 Markdown 인덱스 반환 |

응답은 Discord 메시지 제한에 맞게 잘라 보내며, 원본 전체 export는 파일로 전송한다. 참조 구현은 교차채널 사용자별 ACL 필터가 완성되기 전까지 모든 slash command를 서버 관리자 권한으로 제한한다.

## Failure Semantics

| Failure | Required behavior |
|---|---|
| REST 429 | Discord가 제공한 `retry_after`만큼 대기 후 같은 요청 재시도 |
| Gateway reconnect | 라이브러리 resume 후 중복 이벤트를 저널에서 무해화 |
| Process crash | SQLite commit 이전 이벤트는 재전송, 이후 이벤트는 중복 무해화 |
| Markdown write crash | 임시 파일을 완성한 뒤 atomic replace |
| OpenAI failure | 요약 체크포인트를 전진시키지 않음 |
| Missing message content intent | 빈 본문을 사실로 요약하지 않고 운영 오류로 노출 |
| Deleted source | 저널에는 묘비가 남고 활성 Markdown·검색에서는 제외 |

## Privacy and Retention

채널 allowlist를 기본 정책으로 삼고 DM과 민감 채널은 명시적 승인 없이는 수집하지 않는다. 첨부파일은 기본적으로 다운로드하지 않는다. Discord 삭제 이벤트는 활성 projection에서 내용을 제거하지만 감사·법적 요구에 따라 raw retention을 어떻게 처리할지는 조직 정책으로 결정해야 한다. “삭제되었으나 raw journal에 남음”을 사용자에게 공개하지 않은 채 운영해서는 안 된다.

## Executable Surface

| Component | Status |
|---|---|
| Event normalization and idempotent SQLite journal | Implemented and tested |
| Deterministic Markdown/JSONL projection | Implemented and tested |
| REST channel and public-thread backfill | Implemented and tested |
| Search and stable citations | Implemented and tested |
| Incremental summary provider boundary | Implemented and tested with fake provider |
| OpenAI Responses API adapter | Implemented; live API call not exercised in CI |
| Discord Gateway and slash commands | Implemented as optional `discord.py` adapter; live guild not exercised in CI |
| LLMWiki hybrid index and Evidence Gate wiring | Architecture contract; not yet connected to the Rust production core |
