from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from contextlib import asynccontextmanager
from typing import List
import os
import uuid

# ---------- Database setup ----------

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "tasks")
DB_USER = os.environ.get("DB_USER", "tasks")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "tasks")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TaskModel(Base):
    __tablename__ = "tasks"
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, default="")
    completed = Column(Boolean, default=False)


# ---------- FastAPI app with lifespan ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Task Tracker API",
    description="A task manager built for learning Kubernetes",
    version=os.environ.get("APP_VERSION", "v1"),
    lifespan=lifespan
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Prometheus metrics ----------

tasks_created_total = Counter("tasks_created_total", "Total tasks created")
tasks_deleted_total = Counter("tasks_deleted_total", "Total tasks deleted")
requests_total = Counter("http_requests_total", "Total requests", ["endpoint"])


# ---------- Pydantic models ----------

class TaskCreate(BaseModel):
    title: str
    description: str = ""


class Task(BaseModel):
    id: str
    title: str
    description: str
    completed: bool

    class Config:
        from_attributes = True


# ---------- Routes ----------

@app.get("/")
def root():
    requests_total.labels(endpoint="/").inc()
    version = os.environ.get("APP_VERSION", "v1")
    messages = {
        "v1": "🟢 Stable v1 - Hello from production!",
        "v2": "🔵 NEW v2 - Canary deployment test!"
    }
    return {
        "app": "Task Tracker",
        "version": version,
        "message": messages.get(version, "Unknown version")
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/tasks", response_model=List[Task])
def list_tasks(db: Session = Depends(get_db)):
    requests_total.labels(endpoint="/tasks").inc()
    return db.query(TaskModel).all()


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    requests_total.labels(endpoint="/tasks").inc()
    task_id = str(uuid.uuid4())[:8]
    db_task = TaskModel(
        id=task_id,
        title=task.title,
        description=task.description,
        completed=False
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    tasks_created_total.inc()
    return db_task


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    requests_total.labels(endpoint="/tasks/{id}").inc()
    task = db.query(TaskModel).filter(TaskModel.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    tasks_deleted_total.inc()
    return None


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)