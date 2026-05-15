# SmartFactory-AD

> 제조업 화상 기반 Anomaly Detection + HACCP SmartFactory 통합 시스템
> Manufacturing Visual Anomaly Detection + HACCP SmartFactory Integrated System

---

## 주요 기능 / Key Features

- **비전 기반 이상탐지 / Vision-based Anomaly Detection** — Anomalib (PatchCore / EfficientAD) 기반, MVTec AD 오픈데이터 사전학습
- **VLM 결함 설명 / VLM Defect Explanation** — 결함의 유형·위치·원인·권장조치를 자연어로 자동 생성 (GPT-4o / Qwen2.5-VL)
- **HACCP 7원칙 자동화 / HACCP 7 Principles Automation** — CCP 모니터링, 감사 로그, 보고서 자동 생성
- **실시간 Alert / Real-time Alerts** — WebSocket 대시보드 + Webhook (Slack/Teams) + MQTT Andon 연동
- **대시보드 / Dashboard** — 실시간 모니터링, KPI 분석, HACCP 준수 현황
- **MES 연동 / MES Integration** — REST API 기반 양방향 데이터 교환

---

## 기술 스택 / Tech Stack

| Layer | Technology |
|-------|------------|
| AD Engine | Python, PyTorch, Anomalib |
| VLM | Qwen2.5-VL (로컬/local) / OpenAI GPT-4o Vision API |
| Backend | FastAPI (Python 3.11+) |
| Frontend | React 18+ / TypeScript / TailwindCSS |
| Database | PostgreSQL 15+ (async via SQLAlchemy + asyncpg) |
| Storage | MinIO (S3 호환/compatible) |
| Cache/Queue | Redis |
| Deploy | Docker Compose |

---

## 프로젝트 구조 / Project Structure

```
SmartFactory-AD/
├── backend/              # FastAPI 백엔드 / Backend
│   ├── app/
│   │   ├── core/         # 설정, DB 연결 / Config, DB connection
│   │   ├── models/       # SQLAlchemy ORM 모델 / ORM models
│   │   ├── schemas/      # Pydantic 스키마 / Pydantic schemas
│   │   ├── routers/      # API 라우터 / API routers
│   │   ├── services/     # 비즈니스 로직 / Business logic (AD, VLM, Storage)
│   │   └── main.py       # 앱 엔트리포인트 / App entrypoint
│   ├── tests/            # 테스트 / Tests
│   ├── migrations/       # Alembic 마이그레이션 / DB migrations
│   └── Dockerfile
├── frontend/             # React 대시보드 / Dashboard (planned)
├── ml/                   # ML 파이프라인 / ML pipeline
│   ├── scripts/          # 학습/다운로드 스크립트 / Train & download scripts
│   └── data/             # 데이터셋 (gitignored)
├── docker/               # 추가 Docker 설정 / Additional Docker configs
├── docs/                 # 문서 / Documentation
├── docker-compose.yml
├── .env.example
└── .gitignore
```

---

## 사용 방법 / How to Use

### 사전 요구사항 / Prerequisites

- **Docker & Docker Compose** (인프라 실행용 / for infrastructure)
- **Python 3.11+** (백엔드 개발 / backend development)
- **Node.js 18+** (프론트엔드 개발 시 / frontend development, optional)

---

### 1단계: 환경 설정 / Step 1: Environment Setup

```bash
# 프로젝트 클론 / Clone the project
git clone https://github.com/biztalk72/SmartFactory-AD.git
cd SmartFactory-AD

# 환경변수 파일 복사 / Copy environment variables
cp .env.example .env
```

`.env` 파일을 열어 아래 항목을 필요에 따라 수정합니다:
Open `.env` and modify the following as needed:

| 변수 / Variable | 설명 / Description | 기본값 / Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 연결 문자열 / Connection string | `postgresql+asyncpg://sfadmin:sfadmin123@localhost:5432/smartfactory` |
| `VLM_PROVIDER` | VLM 백엔드 선택 / VLM backend | `local` (또는/or `openai`) |
| `OPENAI_API_KEY` | OpenAI API 키 (openai 모드 시) / Required if VLM_PROVIDER=openai | *(empty)* |
| `AD_MODEL` | 이상탐지 모델 / AD model | `patchcore` (또는/or `efficient_ad`) |
| `AD_DEVICE` | 추론 디바이스 / Inference device | `cpu` (또는/or `cuda`) |
| `AD_CHECKPOINT_PATH` | 학습된 모델 경로 / Trained model checkpoint path | *(empty — demo mode)* |

---

### 2단계: 인프라 실행 / Step 2: Start Infrastructure

Docker Compose로 PostgreSQL, Redis, MinIO를 실행합니다:
Start PostgreSQL, Redis, MinIO with Docker Compose:

```bash
docker compose up -d postgres redis minio
```

서비스 상태 확인 / Verify services are running:

```bash
docker compose ps
```

> **MinIO 콘솔 / MinIO Console**: http://localhost:9001 (ID: `minioadmin` / PW: `minioadmin123`)

---

### 3단계: 백엔드 실행 / Step 3: Run Backend

#### 방법 A: 로컬 실행 / Option A: Run Locally

```bash
cd backend

# 가상환경 생성 및 활성화 / Create and activate virtualenv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치 / Install dependencies
pip install -r requirements.txt

# 서버 실행 / Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 방법 B: Docker로 실행 / Option B: Run with Docker

```bash
docker compose up -d backend
```

서버가 시작되면 자동으로 DB 테이블이 생성됩니다.
DB tables are created automatically on startup.

- **API 문서 / API Docs (Swagger)**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

---

### 4단계: API 사용 방법 / Step 4: How to Use the API

#### 4-1. 헬스체크 / Health Check

```bash
curl http://localhost:8000/health
```

응답 예시 / Example response:
```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "database": "connected",
    "ad_engine": "patchcore",
    "vlm_provider": "local"
  }
}
```

#### 4-2. 검사 스테이션 등록 / Register Inspection Station

검사 라인(스테이션)을 먼저 등록합니다. `is_ccp: true`로 설정하면 HACCP CCP 포인트로 지정됩니다.
Register an inspection station first. Set `is_ccp: true` to designate as a HACCP Critical Control Point.

```bash
curl -X POST http://localhost:8000/api/v1/stations/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Bottle Inspection #1",
    "description": "생산라인 A 병 외관 검사 / Line A bottle visual inspection",
    "line_name": "LINE-A",
    "is_ccp": true,
    "product_category": "bottle",
    "anomaly_threshold": 0.5
  }'
```

응답에서 반환되는 `id` (UUID)를 이후 검사 요청에 사용합니다.
Use the returned `id` (UUID) for subsequent inspection requests.

#### 4-3. 스테이션 목록 조회 / List Stations

```bash
# 전체 조회 / List all
curl http://localhost:8000/api/v1/stations/

# 라인별 필터 / Filter by line
curl "http://localhost:8000/api/v1/stations/?line_name=LINE-A"

# CCP 스테이션만 조회 / CCP stations only
curl "http://localhost:8000/api/v1/stations/?is_ccp=true"
```

#### 4-4. 이미지 검사 실행 (핵심 기능) / Run Inspection (Core Feature)

이미지를 업로드하면 AD 모델이 이상 여부를 판단하고, 이상이 감지되면 VLM이 자동으로 결함을 분석합니다.
Upload an image — the AD model detects anomalies, and if detected, VLM automatically analyzes the defect.

```bash
curl -X POST http://localhost:8000/api/v1/inspect/ \
  -F "file=@/path/to/inspection_image.jpg" \
  -F "station_id=<STATION_UUID>" \
  -F "threshold=0.5" \
  -F "category=bottle" \
  -F "lot_number=LOT-2025-001" \
  -F "serial_number=SN-00042"
```

**파라미터 설명 / Parameters:**

| 파라미터 / Parameter | 필수 / Required | 설명 / Description |
|---|---|---|
| `file` | ✅ | 검사 이미지 (JPEG/PNG) / Inspection image |
| `station_id` | ❌ | 스테이션 UUID / Station UUID |
| `threshold` | ❌ | 이상 판단 임계값 (기본 0.5) / Anomaly threshold (default: 0.5) |
| `category` | ❌ | 제품 카테고리 (기본 "unknown") / Product category |
| `lot_number` | ❌ | 로트 번호 / Lot number |
| `serial_number` | ❌ | 시리얼 번호 / Serial number |
| `skip_vlm` | ❌ | VLM 설명 생략 여부 (기본 false) / Skip VLM explanation |

**응답 예시 / Example Response (이상 감지 시 / when anomaly detected):**

```json
{
  "id": "a1b2c3d4-...",
  "station_id": "e5f6g7h8-...",
  "anomaly_score": 0.82,
  "is_anomaly": true,
  "image_path": "inspections/20250515/143022/a1b2c3d4-.../original.png",
  "heatmap_path": "inspections/20250515/143022/a1b2c3d4-.../heatmap.png",
  "inference_time_ms": 234.5,
  "model_name": "patchcore",
  "vlm_explanation": {
    "defect_type": "crack",
    "location": "center-right surface",
    "severity": "HIGH",
    "cause": "Thermal stress during molding process",
    "recommended_action": "Adjust mold temperature and cooling rate. Inspect mold for damage.",
    "full_explanation": "A crack defect was detected on the center-right surface of the bottle.",
    "vlm_model": "gpt-4o",
    "generation_time_ms": 1523.7
  },
  "created_at": "2025-05-15T14:30:22.000Z"
}
```

#### 4-5. 검사 결과 조회 / Query Inspection Results

```bash
# 전체 조회 (최근 50건) / List recent 50 results
curl http://localhost:8000/api/v1/inspections/

# 이상만 조회 / Anomalies only
curl "http://localhost:8000/api/v1/inspections/?is_anomaly=true"

# 스테이션별 조회 / By station
curl "http://localhost:8000/api/v1/inspections/?station_id=<STATION_UUID>"

# 기간 필터 / Date range filter
curl "http://localhost:8000/api/v1/inspections/?start_date=2025-05-01T00:00:00&end_date=2025-05-15T23:59:59"

# 페이지네이션 / Pagination
curl "http://localhost:8000/api/v1/inspections/?limit=20&offset=40"

# 특정 결과 상세 조회 / Get specific result
curl http://localhost:8000/api/v1/inspections/<RESULT_UUID>
```

---

### 5단계: ML 모델 학습 / Step 5: Train ML Model (Optional)

사전 학습된 체크포인트 없이도 데모 모드로 동작하지만, 정확한 이상탐지를 위해 모델을 학습할 수 있습니다.
The system works in demo mode without a checkpoint, but you can train for accurate detection.

#### 5-1. 데이터셋 다운로드 / Download Dataset

```bash
# MVTec AD 전체 (15 카테고리, ~5K 이미지) / Full MVTec AD (15 categories, ~5K images)
python ml/scripts/download_dataset.py --dataset mvtec_ad --output ml/data

# 통계만 확인 / Check stats only
python ml/scripts/download_dataset.py --stats-only --output ml/data
```

**지원 카테고리 / Supported Categories:**
`bottle`, `cable`, `capsule`, `carpet`, `grid`, `hazelnut`, `leather`, `metal_nut`, `pill`, `screw`, `tile`, `toothbrush`, `transistor`, `wood`, `zipper`

#### 5-2. 모델 학습 / Train Model

```bash
# ML 의존성 설치 / Install ML dependencies
pip install -r ml/requirements.txt

# PatchCore 학습 (bottle 카테고리) / Train PatchCore
python ml/scripts/train.py --model patchcore --category bottle --data_root ml/data/mvtec_ad

# EfficientAD 학습 / Train EfficientAD
python ml/scripts/train.py --model efficient_ad --category bottle --data_root ml/data/mvtec_ad

# GPU 사용 / Use GPU
python ml/scripts/train.py --model patchcore --category bottle --data_root ml/data/mvtec_ad --accelerator gpu
```

#### 5-3. 학습된 모델 적용 / Apply Trained Model

학습 완료 후 출력되는 체크포인트 경로를 `.env`에 설정합니다:
Set the checkpoint path in `.env` after training:

```bash
# .env
AD_CHECKPOINT_PATH=ml/checkpoints/patchcore/bottle/lightning_logs/version_0/checkpoints/best.ckpt
```

서버를 재시작하면 학습된 모델이 자동 로드됩니다.
Restart the server to load the trained model.

---

### 6단계: 테스트 실행 / Step 6: Run Tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

---

## VLM 설정 가이드 / VLM Configuration Guide

### OpenAI GPT-4o (권장 / Recommended for production)

```bash
# .env
VLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-api-key-here
```

### 로컬 VLM / Local VLM (Qwen2.5-VL)

GPU (16GB+ VRAM) 환경에서 사용을 권장합니다.
Recommended with GPU (16GB+ VRAM).

```bash
# .env
VLM_PROVIDER=local

# ML 의존성 설치 필요 / Requires ML dependencies
pip install -r ml/requirements.txt
```

> **참고 / Note:** VLM이 설정되지 않으면 stub 모드로 동작하며, 기본 심각도만 반환됩니다.
> If VLM is not configured, the system runs in stub mode and returns basic severity only.

---

## API 엔드포인트 요약 / API Endpoints Summary

| Method | Path | 설명 / Description |
|--------|------|---------------------|
| `GET` | `/health` | 서비스 상태 확인 / Service health check |
| `POST` | `/api/v1/stations/` | 검사 스테이션 등록 / Register station |
| `GET` | `/api/v1/stations/` | 스테이션 목록 조회 / List stations |
| `GET` | `/api/v1/stations/{id}` | 스테이션 상세 조회 / Get station detail |
| `PATCH` | `/api/v1/stations/{id}` | 스테이션 수정 / Update station |
| `DELETE` | `/api/v1/stations/{id}` | 스테이션 비활성화 / Deactivate station |
| `POST` | `/api/v1/inspect/` | **이미지 검사 실행 / Run inspection** |
| `GET` | `/api/v1/inspections/` | 검사 결과 조회 / List inspection results |
| `GET` | `/api/v1/inspections/{id}` | 검사 결과 상세 / Get inspection detail |

---

## 라이선스 / License

MIT
