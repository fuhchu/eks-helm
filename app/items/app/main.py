import os
import httpx
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
USERS_SERVICE_URL = os.environ["USERS_SERVICE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

app = FastAPI(title="items-service")


class Base(DeclarativeBase):
    pass


class ItemModel(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    user_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


Base.metadata.create_all(bind=engine)


class ItemCreate(BaseModel):
    name: str
    description: str = ""
    user_id: int


class ItemResponse(BaseModel):
    id: int
    name: str
    description: str
    user_id: int

    model_config = {"from_attributes": True}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_user_exists(user_id: int):
    try:
        resp = httpx.get(f"{USERS_SERVICE_URL}/users/{user_id}", timeout=5)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Users service unreachable")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Users service error")


@app.get("/health")
def health():
    return {"status": "ok", "service": "items"}


@app.post("/items", response_model=ItemResponse, status_code=201)
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    verify_user_exists(payload.user_id)
    item = ItemModel(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ItemModel, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.get("/items", response_model=list[ItemResponse])
def list_items(user_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(ItemModel)
    if user_id is not None:
        q = q.filter(ItemModel.user_id == user_id)
    return q.all()


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(ItemModel, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
