# AI 개발 인수인계

점검일 `2026-10-19`. 로컬 폴더 `SmartFactory-AD`. 대상 `biztalk72/SmartFactory-AD`.

## 현재 상태

- 작업 브랜치 `main`, 문서 작성 전 HEAD `ad1f3e1aa5ca7b76d85ecf605d351ab5617bec1e`.
- 프로젝트 목적. - **비전 기반 이상탐지 / Vision-based Anomaly Detection** — Anomalib (PatchCore / EfficientAD) 기반, MVTec AD 오픈데이터 사전학습 - **VLM 결함 설명 / VLM Defect Explanation** — 결함의 유형·위치·원인·권장조치를 자연어로 자동 생성 (GPT-4o / Qwen2.5-VL) - **HACCP 7원칙 자동화 / HACCP 7 Principles Automation** — CCP 모니터링, 감사 로그, 보고서 자동 생성 - **실시간 Alert / Real-time Alerts** — WebSocket 대시보드 + Webhook (Slack/Teams) + MQTT Andon 연동 - **대시보드 / Dashboard** — 실시간 모니터링, KPI 분석, HACCP 준수 현황 - **MES 연동 / MES Integration** — REST API 기반 양방향 데이터 교환
- 주요 디렉터리. `backend/` (28개 파일), `ml/` (3개 파일)
- 파일 형식 분포. `{".py": 25, ".md": 2, ".ini": 2, ".txt": 2, ".example": 1, ".mako": 1, ".yml": 1}`.
- 이전 결정·진행사항 근거. 별도 진행 문서 미발견.

## Claude 구독 해지 이후

- GPT/Codex 등은 먼저 기존 `AGENTS.md`, `CLAUDE.md` 또는 소문자 변형, `docs/REBUILD.md`를 읽는다. 기존 지침이 모델 전용이면 의미를 옮기되 도구 이름을 그대로 호출하지 않는다.
- Claude CLI 구독/로그인, Anthropic API 결제, OpenAI API 결제, ChatGPT/Codex 이용 권한은 별개다. 구독 해지가 애플리케이션의 API 키를 자동 대체하거나 API 사용을 보장하지 않는다.
- Claude 훅·슬래시 명령·플러그인·Agent tool은 다른 실행기에서 자동 호환되지 않는다. 공통 스킬은 SKILL.md와 참조 파일을 복원하고, 훅 이벤트와 MCP transport는 각 실행기의 형식으로 재설정한다.
- 제공자 SDK/모델이 앱 코드에 직접 연결되어 있으면 단순 환경변수 변경만으로 GPT 전환이 끝나지 않는다. 어댑터·응답 형식·도구 호출·스트리밍·캐시·테스트 호환성을 별도 확인한다.
- 발견한 AI 관련 의존성. `openai>=1.30.0`

## 이식성 검토 위치

아래는 자동 검토 후보이며 확정 버그가 아니다. 절대경로는 상대경로/환경변수로 복원 가능한지 확인하고, Claude 참조는 선택적 개발 도구인지 앱 실행에 필요한지 구분한다.
- 크기 제한 내 검사한 소스에서는 대상 패턴이 발견되지 않았다.

## 재개 순서

1. 커밋·브랜치와 이전 진행 문서의 상태가 일치하는지 확인한다.
2. 재빌드 가이드의 지원 런타임과 잠금 파일로 의존성을 복원한다.
3. 필요한 비밀값과 데이터를 별도로 주입한다. 실제 값은 대화나 Git에 넣지 않는다.
4. 단위 테스트부터 실행하고 외부 서비스·통합 테스트는 별도로 검증한다.
5. 미완료 작업과 검증 실패를 해결한 뒤 배포한다. 이번 문서를 기능 구현·운영 복원 완료의 증거로 사용하지 않는다.

공통 플러그인·스킬·환경 복원 자료. https://github.com/biztalk72/agent-harness/tree/backup/final-20261019-environment
