# 1차 미션 제출용 AI 데이터 비서 API

영어 에세이 성장 아틀리에와 분리해 운영할 수 있는 FastAPI 어댑터입니다. 시계열 데이터 CRUD, 통계 요약, 대화 저장, 요약 주입형 채팅을 미션 명세에 맞춰 제공합니다.

## 실행

```bash
cd mission-api
python -m venv .venv
. .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

실행 후 Swagger: `http://localhost:8000/docs`

Render 배포는 저장소 루트의 `render.yaml`과 `mission-api/Dockerfile`을 사용합니다. Render 환경변수에는 `FIRESTORE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS_JSON`, `OPENAI_API_KEY`, `ALLOWED_ORIGINS`를 등록합니다. 서비스 계정 JSON 전체를 `GOOGLE_APPLICATION_CREDENTIALS_JSON`에 넣으면 서버가 임시 파일로 변환해 사용합니다.

Firestore를 연결하지 않으면 메모리 저장소로 즉시 시연할 수 있습니다. 제출 배포에서는 `FIRESTORE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, `OPENAI_API_KEY`를 서버 환경변수로 설정합니다.

## 엔드포인트

`POST/GET/PUT/DELETE /api/data`, `GET /api/data/summary`, `POST/GET/GET by id/DELETE /api/conversations`, `POST /api/chat`, `GET /api/health`를 제공합니다. `/api/chat`은 먼저 데이터 요약을 계산하고, OpenAI 키가 있으면 시스템 컨텍스트에 요약 JSON을 넣어 답변한 뒤 대화를 자동 저장합니다.

## 샘플 데이터 100개

Swagger에서 `POST /api/data`를 100회 호출하거나 아래처럼 날짜와 값을 바꾸어 반복 실행합니다.

```python
import requests
from datetime import date, timedelta
start = date(2026, 1, 1)
for i in range(100):
    requests.post("http://localhost:8000/api/data", json={"date": str(start + timedelta(days=i)), "value": 50 + i * .2, "memo": "demo"})
```

또는 API 서버가 실행 중일 때 `python seed_demo.py`를 실행합니다. 브라우저 시연 화면에서는 **100개 샘플 만들기** 버튼으로 같은 작업을 수행합니다.
