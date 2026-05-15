# SmartFactory-AD: PRD (Product Requirements Document)
제조업 화상 기반 Anomaly Detection + HACCP/SmartFactory 통합 시스템
## 1. 프로젝트 개요
### 1.1 목적
제조 현장의 카메라 영상을 기반으로 이상(결함)을 자동 탐지하고, VLM(Vision-Language Model)을 활용하여 결함의 맥락을 자연어로 설명·저장하며, HACCP 및 SmartFactory 규정에 부합하는 알림·대시보드 시스템을 제공한다.
### 1.2 대상 사용자
* **품질관리 담당자 (QA Manager)** – 결함 판정, 보고서 확인
* **현장 오퍼레이터** – 실시간 알림 수신, 조치 기록
* **공장장/관리자** – 대시보드 KPI, HACCP 감사 대응
### 1.3 핵심 가치
* 오픈 데이터로 사전 학습 → 자체 데이터 Fine-tuning으로 빠른 적용
* VLM 기반 결함 설명으로 비전문가도 이해 가능한 맥락 제공
* HACCP 7원칙 준수 기록 자동화
## 2. 기능 요구사항
### 2.1 이상탐지 (Anomaly Detection) 엔진
**FR-AD-01**: MVTec AD 및 VisA 오픈 데이터셋으로 사전 학습된 Anomaly Detection 모델 제공
* 지원 모델: PatchCore, EfficientAD, 또는 Anomalib 프레임워크 기반
* 입력: 카메라 영상 프레임 (RGB, 최소 224×224)
* 출력: anomaly score (0~1), anomaly heatmap (pixel-level)
**FR-AD-02**: 자체 제조 데이터 Fine-tuning 파이프라인
* 정상 이미지만으로 비지도 학습 가능
* 새 제품/카테고리 추가 시 재학습 CLI/API 제공
**FR-AD-03**: 실시간 추론 지원
* 단일 이미지 추론 latency ≤ 200ms (GPU 기준)
* 배치 추론 모드 지원
### 2.2 VLM 기반 결함 맥락 설명
**FR-VLM-01**: 이상 탐지 시 VLM을 호출하여 결함의 자연어 설명 생성
* 입력: 원본 이미지 + anomaly heatmap + 제품 카테고리
* 출력: 결함 유형, 위치, 심각도, 추정 원인, 권장 조치
* 참조 모델: LLaVA, Qwen2.5-VL, 또는 GPT-4o API
**FR-VLM-02**: 결함 설명 이력 저장
* 이미지, heatmap, anomaly score, VLM 설명을 DB에 저장
* 검색·필터링 가능 (날짜, 제품, 결함 유형, 심각도)
**FR-VLM-03**: Few-shot 맥락 제공
* LogicQA/LogicAD 방식으로 정상 이미지 참조 기반 비교 설명 생성
### 2.3 Alert 시스템
**FR-ALT-01**: 임계값 기반 알림
* anomaly score > threshold 시 즉시 알림 발생
* 심각도 레벨: INFO / WARNING / CRITICAL
**FR-ALT-02**: 알림 채널
* 대시보드 실시간 푸시 (WebSocket)
* Webhook (Slack, Teams, 커스텀)
* 이메일 알림 (선택)
**FR-ALT-03**: Andon 보드 연동
* 라인 정지 트리거 연동 인터페이스 (MQTT/OPC-UA)
### 2.4 HACCP 준수 기능
**FR-HACCP-01**: CCP(Critical Control Point) 모니터링
* 각 검사 포인트를 CCP로 등록·관리
* CCP별 critical limit 설정 (anomaly score threshold)
**FR-HACCP-02**: HACCP 7원칙 기록 자동화
* Principle 1 (위해 분석): 결함 유형별 위해 분류 관리
* Principle 2 (CCP 결정): CCP 등록/변경 이력
* Principle 3 (한계 기준): threshold 설정 이력
* Principle 4 (모니터링): 검사 결과 타임스탬프 기록
* Principle 5 (시정 조치): 알림 후 조치 기록
* Principle 6 (검증): 모델 성능 검증 기록
* Principle 7 (문서화): 전체 감사 추적 로그
**FR-HACCP-03**: 감사 대응 보고서 자동 생성
* 기간별 CCP 모니터링 결과 보고서 (PDF/CSV)
* 변조 불가 감사 로그
### 2.5 대시보드
**FR-DASH-01**: 실시간 생산 모니터링
* 라인별/스테이션별 검사 현황
* 실시간 anomaly score 추이 차트
* 최근 결함 이미지 + VLM 설명 표시
**FR-DASH-02**: KPI 분석
* 불량률 추이 (시간/일/주/월)
* CCP 이탈 횟수 및 시정 조치 현황
* 결함 유형별 파레토 분석
**FR-DASH-03**: HACCP 준수 상태
* CCP별 상태 표시 (정상/주의/위반)
* HACCP 감사 체크리스트 진행률
### 2.6 MES 연동
**FR-MES-01**: 오픈 MES 데이터 연동
* 작업지시(Work Order) 연계: 검사 결과를 WO에 매핑
* REST API를 통한 양방향 데이터 교환
* 지원 대상: Carbon MES, OpenMES, 또는 커스텀 MES
**FR-MES-02**: 생산 이력 추적 (Traceability)
* LOT/Serial 단위 검사 이력 조회
* 원자재 LOT → 공정 → 검사 결과 → 출하 추적 체인
## 3. 비기능 요구사항
### 3.1 성능
* 단일 이미지 추론: ≤ 200ms (NVIDIA T4 이상)
* VLM 설명 생성: ≤ 3초 (비동기 처리)
* 대시보드 동시 접속: 50 사용자
### 3.2 확장성
* 다중 라인/공장 지원 (멀티테넌트)
* 카메라/검사포인트 수평 확장
### 3.3 보안
* 역할 기반 접근 제어 (RBAC): Admin, Supervisor, Operator
* 감사 로그 변조 불가 (append-only)
* API 인증 (JWT)
### 3.4 배포
* Docker Compose 기반 로컬 배포 (Colima 호환)
* ARM64/AMD64 지원
## 4. 기술 아키텍처
### 4.1 시스템 구성도
```warp-runnable-command
┌─────────────────────────────────────────────────┐
│                   Frontend                       │
│  React + TailwindCSS + Recharts Dashboard        │
│  (WebSocket for real-time updates)               │
└────────────────┬────────────────────────────────┘
                 │ REST / WebSocket
┌────────────────▼────────────────────────────────┐
│               Backend API (FastAPI)              │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐   │
│  │ AD Engine│ │VLM Service│ │ Alert Manager │   │
│  │(Anomalib)│ │(LLaVA/API)│ │(Webhook/MQTT) │   │
│  └──────────┘ └──────────┘ └────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐   │
│  │HACCP Svc │ │MES Bridge│ │ Report Engine │   │
│  └──────────┘ └──────────┘ └────────────────┘   │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│           Data Layer                             │
│  PostgreSQL (검사 이력, HACCP, 사용자)            │
│  MinIO/S3 (이미지, heatmap 저장)                 │
│  Redis (캐시, 실시간 알림 큐)                     │
└─────────────────────────────────────────────────┘
```
### 4.2 기술 스택
* **AD 엔진**: Python, PyTorch, Anomalib (PatchCore/EfficientAD)
* **VLM**: Qwen2.5-VL (로컬) 또는 OpenAI Vision API (클라우드)
* **Backend**: FastAPI (Python 3.11+)
* **Frontend**: React 18+ / TypeScript / TailwindCSS / Recharts
* **DB**: PostgreSQL 15+
* **Object Storage**: MinIO (S3 호환)
* **Message Queue**: Redis Streams
* **배포**: Docker Compose (Colima 호환)
### 4.3 오픈 데이터셋
* **MVTec AD**: 5,354 이미지, 15 카테고리, 73 결함 유형, pixel-level GT (CC BY-NC-SA 4.0)
* **MVTec LOCO AD**: 논리적 이상 포함 (물체 누락, 배치 오류)
* **VisA**: 12 카테고리, 10,821 이미지, 복잡한 구조
* **MVTec AD 2**: 8,000+ 이미지, 다양한 조명 조건
## 5. 데이터 모델 (핵심)
* **InspectionStation**: 검사 포인트 정의 (CCP 여부, 카메라 설정)
* **InspectionResult**: 검사 결과 (anomaly_score, is_anomaly, image_path, heatmap_path)
* **VLMExplanation**: VLM 생성 설명 (defect_type, location, severity, cause, action)
* **HACCPRecord**: HACCP 기록 (ccp_id, critical_limit, actual_value, corrective_action)
* **Alert**: 알림 이력 (severity, channel, acknowledged_at, resolved_at)
* **AuditLog**: 감사 로그 (user, action, timestamp, immutable)
## 6. 개발 로드맵
### Phase 1: Foundation (2주)
* 프로젝트 구조 및 개발환경 셋업
* Docker Compose 구성 (PostgreSQL, MinIO, Redis)
* FastAPI 프로젝트 골격 + DB 마이그레이션
* MVTec AD 데이터셋 다운로드 및 전처리 파이프라인
### Phase 2: AD Engine (2주)
* Anomalib 기반 PatchCore/EfficientAD 학습 파이프라인
* REST API: 이미지 업로드 → 추론 → 결과 반환
* 학습/평가 CLI 도구
### Phase 3: VLM Integration (2주)
* VLM 서비스 구현 (Qwen2.5-VL 로컬 or API 호출)
* 결함 설명 생성 프롬프트 엔지니어링
* 설명 이력 저장 및 조회 API
### Phase 4: HACCP & Alert (2주)
* CCP 등록/관리 API
* HACCP 7원칙 기록 자동화
* Alert Manager (WebSocket + Webhook)
* HACCP 보고서 생성
### Phase 5: Dashboard (2주)
* React 대시보드 구현
* 실시간 모니터링 뷰
* KPI 분석 차트
* HACCP 준수 현황 뷰
### Phase 6: MES 연동 & 통합 테스트 (2주)
* MES REST API 브릿지
* E2E 통합 테스트
* 문서화 및 배포 가이드
## 7. 참조 자료
* **MVTec AD**: Bergmann et al., CVPR 2019 – 5,354 이미지, 15 카테고리 산업 결함 데이터셋
* **LogicAD**: Jin et al., AAAI 2025 – VLM 기반 텍스트 피처 추출 이상탐지 (AUROC 86.0%)
* **LogicQA**: Kwon et al., ACL 2025 – VLM 질문 생성 기반 논리적 이상탐지 (AUROC 87.6%)
* **EIAD**: Zhang et al. – 설명 가능한 산업 이상탐지 멀티모달 LLM
* **HACCP Codex Alimentarius**: 식품 안전 7원칙
* **Carbon MES**: 오픈소스 ERP/MES/QMS (TypeScript/Supabase)
* **OpenMES**: MIT 라이선스 오픈소스 MES (Laravel/PHP)
* **Anomalib**: Intel 오픈소스 이상탐지 라이브러리
