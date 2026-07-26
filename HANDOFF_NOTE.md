# LLMWiki 기술 명세서 전달 노트

**전달자**: Jeoung Mingyu (jmkjmk1023@gmail.com)
**날짜**: 2026-07-27
**저장소**: https://github.com/Mingoomato/FOLDING_LLMWIKI_Technical
**최종 커밋**: `c44391c` (master, origin과 동기화 완료)
**산출물**: `LLMWiki.pdf` (159페이지)

---

## 1. 문서 개요

**LLMWiki**는 로컬 지식(코드, 문서, API 스펙 등)을 지속적으로 시맨틱 지식 공간으로 변환하는 "시맨틱 운영 레이어(Semantic Operating Layer)"에 대한 기술 명세서입니다. 단순 RAG(Retrieval-Augmented Generation) 프레임워크가 아니라, 검색된 근거를 교차 검증(Evidence Gate)한 뒤에만 답변 생성 단계로 넘기는 것이 핵심 차별점입니다.

전체 11개 볼륨(Volume) + 부록(Appendix)으로 구성되어 있으며, 아키텍처부터 특허 초안, 학술 논문 형식 요약까지 포함하는 완결된 기술 문서 세트입니다.

## 2. 문서 구성 (Volume I–XI)

| Vol. | 제목 | 내용 |
|---|---|---|
| 01 | Architecture | 3계층 아키텍처, 파일시스템/WAL, 시스템 불변식(invariants) |
| 02 | Semantic Parsing | 증분 파싱, 엔티티 추출/해석 |
| 03 | Knowledge Graph & Semantic Index | 그래프 저장소, 하이브리드 인덱스(HNSW/BM25/그래프) |
| 04 | Retrieval and Evidence Gate | 하이브리드 검색 파이프라인, Evidence Gate(교차 인코더 검증) |
| 05 | Agent Runtime | 쿼리 플랜 DAG, 실행 예산/타임아웃 관리 |
| 06 | Evaluation Framework | 벤치마크 프로토콜, 통계적 검증 방법론 |
| 07 | Deployment and Operations | 배포(Helm/K8s), 관측성(트레이싱/메트릭) |
| 08 | API Reference | REST API 전체 스펙 |
| 09 | Developer Guide | 개발자 온보딩 가이드 |
| 10 | Patent Draft | 특허 청구항 초안 (Vol. 01~07의 핵심 발명 요소 인용) |
| 11 | Research Paper | 학술 논문 형식 요약본 |

부록 A~G: 수학 표기법, 설정 스키마(config.toml 전체), API 스키마(OpenAPI), 평가 프로토콜, 용어집(Glossary) 등.

## 3. 이번 라운드에서 확인·수정한 사항

이번 작업은 "완성된 문서"를 실제로 빌드 가능하고 시각적으로 정상인 상태로 만드는 데 집중했습니다. 개발진이 알아야 할 변경 이력은 다음과 같습니다.

### 3.1 페이지 여백/오버플로우 (A4 폭 초과) 수정
- **문제**: JSON 스키마 리스팅(부록 B)과 `config.toml` 등 verbatim 블록의 긴 줄이 A4 페이지 폭을 최대 573pt(~20cm)까지 벗어남.
- **원인**: (1) `\lstdefinestyle`로 정의한 줄바꿈 스타일이 실제 호출부에 전혀 적용되지 않고 있었음(inert), (2) 기본 `verbatim` 환경은 줄바꿈을 지원하지 않으며, (3) `tcolorbox` 패키지가 내부적으로 `verbatim.sty`를 재로드하면서 앞서 시도한 수정을 덮어쓰고 있었음.
- **조치**: 전역 `\lstset`으로 전환하고, `fvextra`의 `Verbatim` 환경(줄바꿈 지원)으로 교체하되 모든 `\usepackage` 선언 **이후**에 배치하여 `tcolorbox`의 재정의를 우회.
- **결과**: 오버플로우 경고 112건(최대 573pt) → 18건(최대 약 57pt, 하이픈 제한이 있는 전문 용어로 인한 통상적 조판 노이즈 수준)으로 감소. 표/그림은 기존에 이미 `adjustbox`로 폭 제한 처리되어 있었음.

### 3.2 좌우 여백(안쪽/바깥쪽) 비대칭
- 문서가 `twoside` 인쇄/제본용으로 설계되어 있고(`documentclass[...,twoside]{book}`), `bindingoffset=10mm`이 설정되어 있어 안쪽(제본 쪽) 여백이 바깥쪽보다 10mm 더 넓게 나옵니다. **의도된 설정**이며 실제 인쇄·제본 시 표준적인 방식입니다. 화면 열람용으로만 쓸 경우 대칭 여백(25mm/25mm)으로 바꿀 수 있음 — 필요 시 요청.

### 3.3 깨진 글자(missing glyph) 수정
- **문제**: 3곳의 디렉토리/트레이스 트리 다이어그램(Vol. 03, Vol. 07 x2)에서 유니코드 박스 문자(`├`, `─`, `│`, `└`)가 기본 모노스페이스 폰트(Latin Modern Mono)에 없어 424건의 "missing character" 경고와 함께 빈 글자로 렌더링되고 있었음.
- **조치**: 순수 ASCII 트리 표기(`|--`, `` `-- ``)로 교체. 폰트 의존성 없이 어떤 환경에서도 동일하게 렌더링됨.

### 3.4 중복 참조 라벨(cross-reference) 수정
- LaTeX 빌드 로그에서 "multiply defined" 경고 3건 발견 — 서로 다른 두 위치가 동일한 `\label`을 사용하고 있어 `\ref`/`\cref`가 어느 쪽을 가리키는지 모호했음:
  - `app:config` → 부록 A와 부록 C가 공유 → 부록 C를 `app:config-reference`로 변경
  - `sec:retrieval:evidence-gate` → Vol.04 내 두 개의 하위 절이 공유 → Stage 3 절을 `sec:retrieval:evidence-gate-stage3`로 변경
  - `alg:entity-resolution` → Vol.02와 Vol.03의 알고리즘이 공유 → Vol.02를 `alg:entity-resolution-parsing`으로 변경
- 기존 외부 참조(`\ref`)는 모두 원래 남긴 쪽을 가리키고 있어 깨진 링크는 없음. 빌드 후 재검증 완료.

### 3.5 저자 정보 갱신
- 표지, 하단 footer, PDF 메타데이터(`pdfauthor`), 거버넌스 표에 있던 placeholder(`Jung Min-gyu` / `jungmingyu@example.com`)를 실제 저자 정보(**Jeoung Mingyu** / **jmkjmk1023@gmail.com**)로 교체.

### 3.6 CI(GitHub Actions) 빌드 파이프라인 수정
- **문제**: `.github/workflows/build-pdf.yml`이 매 push마다 실패하고 있었음(로컬 빌드는 정상이었지만 CI에서만 실패 → 로컬 결과물과 저장소 상태 사이 괴리가 있었음).
- **원인 1**: `xu-cheng/latex-action`이 이미 컨테이너 내부에서 전체 빌드를 완료하는데, 워크플로에 중복된 `latexmk` 실행 스텝이 있어 컨테이너 밖(베어 우분투 러너)에서 `latexmk`를 다시 호출 → "command not found"로 실패.
- **원인 2**: `extra_system_packages` 입력은 TeX Live/CTAN 패키지가 아니라 Alpine `apk` 시스템 패키지 설치용인데, `latexmk` 등 CTAN 패키지 이름을 나열해서 "no such package"로 실패. 실제로는 사용 중인 `texlive-full` 도커 이미지에 모든 패키지가 이미 포함되어 있어 이 입력 자체가 불필요했음.
- **조치**: 중복 빌드 스텝 제거, `extra_system_packages` 블록 전체 삭제.
- **결과**: CI 그린 확인 완료 (연속 2회 성공).

## 4. 최종 빌드 상태 (검증 완료)

- 총 159페이지, LuaLaTeX 엔진
- 에러 0건, undefined reference/citation 0건
- Missing character 0건, multiply-defined label 0건
- Overfull hbox 18건 (최대 ~57pt, 전문용어 하이픈 제약에 의한 통상적 조판 여유 — 실제 여백 침범 아님)
- 로컬 빌드와 CI 빌드 모두 그린 상태로 동일 커밋에서 재현 확인됨

## 5. 로컬에서 재빌드하는 방법 (참고)

```bash
export BIBINPUTS="<repo-root>;"
latexmk LLMWiki.tex   # .latexmkrc가 lualatex/bibtex/glossaries 설정을 자동 적용
cp build/LLMWiki.pdf ./LLMWiki.pdf
```

CI는 push/PR 시 `.github/workflows/build-pdf.yml`을 통해 자동 빌드되며, 빌드된 PDF는 GitHub Actions의 Artifact(`LLMWiki-PDF`)로 30일간 다운로드 가능합니다 (저장소에 자동 커밋되지는 않음 — 소스 변경 시 로컬에서 재빌드 후 커밋 필요).

## 6. 개발진 검토 요청 사항

- Vol. 10 (Patent Draft)의 청구항 문구는 법률 검토 미완료 상태(`Patent Attorney: TBD`) — 특허 대리인 검토 필요.
- 전체 내용에 대한 기술적 정확성 검토(특히 Vol. 03~05의 알고리즘 의사코드) 요청.
- 인쇄본 제작 예정 여부에 따라 여백 설정(3.2절) 유지/변경 결정 필요.
