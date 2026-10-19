# 재빌드 가이드

점검일 `2026-10-19`. 기준 체크아웃 `main`, 문서 작성 전 HEAD `ad1f3e1aa5ca7b76d85ecf605d351ab5617bec1e`. 이 문서는 실제 파일에서 추출한 근거이며 전체 빌드 성공을 뜻하지 않는다.

## 프로젝트 및 근거

- **비전 기반 이상탐지 / Vision-based Anomaly Detection** — Anomalib (PatchCore / EfficientAD) 기반, MVTec AD 오픈데이터 사전학습 - **VLM 결함 설명 / VLM Defect Explanation** — 결함의 유형·위치·원인·권장조치를 자연어로 자동 생성 (GPT-4o / Qwen2.5-VL) - **HACCP 7원칙 자동화 / HACCP 7 Principles Automation** — CCP 모니터링, 감사 로그, 보고서 자동 생성 - **실시간 Alert / Real-time Alerts** — WebSocket 대시보드 + Webhook (Slack/Teams) + MQTT Andon 연동 - **대시보드 / Dashboard** — 실시간 모니터링, KPI 분석, HACCP 준수 현황 - **MES 연동 / MES Integration** — REST API 기반 양방향 데이터 교환

- 설명 근거. `README.md`.
- 매니페스트. `backend/Dockerfile`, `backend/requirements.txt`, `docker-compose.yml`, `ml/requirements.txt`
- 잠금 파일. 발견되지 않음. 설치 시 의존성 변동 가능.

## 설치 및 지원 런타임

현재 호스트의 최신 런타임을 지원 버전으로 간주하지 않는다. 프로젝트의 버전 파일·매니페스트·CI가 우선이다. 아래 설치 명령은 복원용이며 이번 작업에서 일괄 실행하지 않았다. 설치 전 lifecycle/hook 스크립트를 검토한다.

- requirements 기반 Python 패키지는 별도 가상환경에서 설치한다. 각 `requirements.txt`의 버전 고정 여부와 README 명령을 확인한다.

## 저장소에 실제 선언된 실행·검증 명령

실행 위치가 `.`이 아니면 해당 하위 디렉터리에서 실행한다. 아래 항목은 선언 확인이며 실행 결과가 아니다.
- 공통 build/test/lint 스크립트를 찾지 못했다. 기존 README와 하위 매니페스트를 확인한다.

## 환경변수·서비스·데이터 복원

- 실제 `.env`와 인증정보는 Git에 보존하지 않는다. 프로젝트의 기존 예제와 비밀 저장소에서 재발급·주입한다.
- 코드 및 예제에서 발견한 환경변수 이름은 `env.required.example`에 있다. 모든 변수가 필수라는 뜻은 아니다.
- 마이그레이션은 적용 전 대상 DB·백업·복구 지점을 확인한다. 운영 DB에 자동 실행하지 않는다.
- DB/모델/업로드 문서는 소스 저장소만으로 복구되지 않을 수 있다. 아래 제외 항목과 기존 데이터 복원 절차를 확인한다.
- 서비스 이미지 `postgres:15-alpine` — `docker-compose.yml`. `latest` 또는 태그 미지정 이미지는 재현성 위험이다.
- 서비스 이미지 `redis:7-alpine` — `docker-compose.yml`. `latest` 또는 태그 미지정 이미지는 재현성 위험이다.
- 서비스 이미지 `minio/minio:latest` — `docker-compose.yml`. `latest` 또는 태그 미지정 이미지는 재현성 위험이다.
- 마이그레이션 관련 파일. `backend/migrations/env.py`, `backend/migrations/script.py.mako`.

## 이번 점검에서 실행한 검증

매니페스트 파싱 및 Python AST 구문 검사를 수행했다. 의존성 설치, 전체 테스트, 프런트엔드 프로덕션 빌드, 외부 API·DB·GPU·서명·배포 검증은 별도로 명시하지 않는 한 미실행이다.
- 상세 결과. `rebuild-validation.json`.
- 정적 검사 통과 `25`건, 실패 `0`건.

## 보존 제외·수동 복원

아래 목록은 안전 정책으로 선택하지 않은 파일이다. 이미 과거 이력에 들어 있는 파일을 삭제하거나 이력을 정리했다는 뜻은 아니다. 생성물은 재생성하고, 원본 데이터·모델·비밀값은 별도 복원한다.
- 선택 파일 목록에서 별도 제외 항목을 발견하지 않았다. gitignore된 실제 비밀·데이터가 없다는 뜻은 아니다.

공통 개발환경 복원 자료. https://github.com/biztalk72/agent-harness/tree/backup/final-20261019-environment
