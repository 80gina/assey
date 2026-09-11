"""1차 미션용 AI 데이터 비서 API.

Firestore와 OpenAI 키가 없을 때도 로컬 메모리 저장소로 시연할 수 있습니다.
배포 환경에서는 FIRESTORE_PROJECT_ID와 서비스 계정, OPENAI_API_KEY를 설정하세요.
"""
from __future__ import annotations

import os
import json
import statistics
import tempfile
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

try:
    from google.cloud import firestore
except Exception:  # pragma: no cover - optional local demo dependency
    firestore = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - optional local demo dependency
    OpenAI = None


class DataPoint(BaseModel):
    date: date
    value: float
    memo: str = Field(default="", max_length=500)


class DataCreate(DataPoint):
    pass


class DataUpdate(BaseModel):
    date: Optional[date] = None
    value: Optional[float] = None
    memo: Optional[str] = Field(default=None, max_length=500)


class ConversationCreate(BaseModel):
    title: str = Field(default="새 대화", max_length=120)
    messages: list[dict[str, Any]] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message is required")
        return value


class Store:
    def __init__(self) -> None:
        self.db = None
        self.data: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                path = os.path.join(tempfile.gettempdir(), "firestore-service-account.json")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(json.loads(credentials_json), handle)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            except (OSError, ValueError):
                pass
        if firestore and os.getenv("FIRESTORE_PROJECT_ID"):
            try:
                self.db = firestore.Client(project=os.getenv("FIRESTORE_PROJECT_ID"))
            except Exception:
                self.db = None

    def list_data(self) -> list[dict[str, Any]]:
        if self.db:
            rows = [{"id": doc.id, **doc.to_dict()} for doc in self.db.collection("data").stream()]
            return sorted(rows, key=lambda row: str(row.get("date", "")))
        return sorted(self.data.values(), key=lambda row: str(row["date"]))

    def get_data(self, item_id: str) -> Optional[dict[str, Any]]:
        if self.db:
            doc = self.db.collection("data").document(item_id).get()
            return {"id": doc.id, **doc.to_dict()} if doc.exists else None
        return self.data.get(item_id)

    def save_data(self, row: dict[str, Any], item_id: Optional[str] = None) -> dict[str, Any]:
        item_id = item_id or str(uuid.uuid4())
        row = {"id": item_id, **row}
        if self.db:
            self.db.collection("data").document(item_id).set({k: v for k, v in row.items() if k != "id"})
        else:
            self.data[item_id] = row
        return row

    def delete_data(self, item_id: str) -> None:
        if self.db:
            self.db.collection("data").document(item_id).delete()
        else:
            self.data.pop(item_id, None)

    def list_conversations(self) -> list[dict[str, Any]]:
        if self.db:
            rows = [{"id": doc.id, **doc.to_dict()} for doc in self.db.collection("conversations").stream()]
            return sorted(rows, key=lambda row: str(row.get("updated_at", "")), reverse=True)
        return sorted(self.conversations.values(), key=lambda row: row.get("updated_at", ""), reverse=True)

    def get_conversation(self, conversation_id: str) -> Optional[dict[str, Any]]:
        if self.db:
            doc = self.db.collection("conversations").document(conversation_id).get()
            return {"id": doc.id, **doc.to_dict()} if doc.exists else None
        return self.conversations.get(conversation_id)

    def save_conversation(self, row: dict[str, Any], conversation_id: Optional[str] = None) -> dict[str, Any]:
        conversation_id = conversation_id or str(uuid.uuid4())
        row = {"id": conversation_id, **row}
        if self.db:
            self.db.collection("conversations").document(conversation_id).set({k: v for k, v in row.items() if k != "id"})
        else:
            self.conversations[conversation_id] = row
        return row

    def delete_conversation(self, conversation_id: str) -> None:
        if self.db:
            self.db.collection("conversations").document(conversation_id).delete()
        else:
            self.conversations.pop(conversation_id, None)


store = Store()
app = FastAPI(title="AI Data Assistant API", version="1.0.0", description="1차 미션 제출용 시계열 데이터·대화 API")
origins = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def iso(value: date) -> str:
    return value.isoformat()


def summary() -> dict[str, Any]:
    rows = store.list_data()
    values = [float(row["value"]) for row in rows]
    if not values:
        return {"period": {"start": None, "end": None}, "count": 0, "average": 0, "max": None, "min": None, "trend": "no_data"}
    ordered = sorted(rows, key=lambda row: str(row["date"]))
    delta = values[-1] - values[0] if len(values) > 1 else 0
    return {
        "period": {"start": str(ordered[0]["date"]), "end": str(ordered[-1]["date"])},
        "count": len(values),
        "average": round(statistics.mean(values), 2),
        "max": max(values),
        "min": min(values),
        "trend": "up" if delta > 0 else "down" if delta < 0 else "flat",
        "change": round(delta, 2),
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "storage": "firestore" if store.db else "memory"}


@app.post("/api/data", status_code=201)
def create_data(payload: DataCreate) -> dict[str, Any]:
    return store.save_data({"date": iso(payload.date), "value": payload.value, "memo": payload.memo})


@app.get("/api/data")
def list_data(limit: int = Query(default=500, ge=1, le=1000)) -> list[dict[str, Any]]:
    return store.list_data()[:limit]


@app.put("/api/data/{item_id}")
def update_data(item_id: str, payload: DataUpdate) -> dict[str, Any]:
    current = store.get_data(item_id)
    if not current:
        raise HTTPException(404, "data not found")
    changes = payload.model_dump(exclude_none=True)
    if "date" in changes:
        changes["date"] = iso(changes["date"])
    return store.save_data({**current, **changes}, item_id)


@app.delete("/api/data/{item_id}")
def delete_data(item_id: str) -> dict[str, bool]:
    if not store.get_data(item_id):
        raise HTTPException(404, "data not found")
    store.delete_data(item_id)
    return {"deleted": True}


@app.get("/api/data/summary")
def get_summary() -> dict[str, Any]:
    return summary()


@app.post("/api/conversations", status_code=201)
def create_conversation(payload: ConversationCreate) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return store.save_conversation({"title": payload.title, "messages": payload.messages, "created_at": now, "updated_at": now})


@app.get("/api/conversations")
def list_conversations() -> list[dict[str, Any]]:
    return store.list_conversations()


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str) -> dict[str, Any]:
    row = store.get_conversation(conversation_id)
    if not row:
        raise HTTPException(404, "conversation not found")
    return row


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict[str, bool]:
    if not store.get_conversation(conversation_id):
        raise HTTPException(404, "conversation not found")
    store.delete_conversation(conversation_id)
    return {"deleted": True}


def fallback_answer(message: str, data_summary: dict[str, Any]) -> str:
    if not data_summary["count"]:
        return "아직 데이터가 없습니다. /api/data에 기록을 추가한 뒤 다시 질문해 주세요."
    return (f"현재 {data_summary['count']}개의 기록이 있습니다. "
            f"평균은 {data_summary['average']}, 최댓값은 {data_summary['max']}, "
            f"최솟값은 {data_summary['min']}이며 추세는 {data_summary['trend']}입니다. "
            f"질문하신 내용({message})을 이 요약과 함께 해석해 보세요.")


@app.post("/api/chat")
def chat(payload: ChatRequest) -> dict[str, Any]:
    data_summary = summary()
    conversation = store.get_conversation(payload.conversation_id) if payload.conversation_id else None
    messages = list(conversation["messages"]) if conversation else []
    messages.append({"role": "user", "content": payload.message})
    answer = fallback_answer(payload.message, data_summary)
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and OpenAI:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "You are a concise data assistant. Use the supplied summary and never invent data."},
                {"role": "system", "content": f"Data summary JSON: {data_summary}"},
                *messages,
            ],
        )
        answer = response.choices[0].message.content or answer
    messages.append({"role": "assistant", "content": answer})
    now = datetime.now(timezone.utc).isoformat()
    saved = store.save_conversation({"title": conversation["title"] if conversation else payload.message[:60], "messages": messages, "created_at": conversation["created_at"] if conversation else now, "updated_at": now}, payload.conversation_id)
    return {"answer": answer, "summary": data_summary, "conversation": saved}
