from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

import os
import shutil
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone
import logging

# ================= LOAD ENV =================
load_dotenv()

# ================= PATHS =================
ROOT_DIR = Path(__file__).parent
UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ================= ENV =================
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
BASE_URL = os.getenv("BASE_URL")  # Render only

if not MONGO_URL or not DB_NAME or not BASE_URL:
    raise RuntimeError("❌ Variables d'environnement manquantes")

# ================= DATABASE =================
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ================= APP =================
app = FastAPI()
api_router = APIRouter(prefix="/api")

# ================= STATIC FILES =================
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= MODELS =================
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# ================= ROUTES =================
@api_router.get("/")
async def root():
    return {"message": "API is running"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status = StatusCheck(client_name=input.client_name)
    doc = status.model_dump()
    doc["timestamp"] = doc["timestamp"].isoformat()
    await db.status_checks.insert_one(doc)
    return status

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    for c in checks:
        if isinstance(c["timestamp"], str):
            c["timestamp"] = datetime.fromisoformat(c["timestamp"])
    return checks

# ================= IMAGE UPLOAD =================
@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    extension = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}_{int(datetime.now().timestamp())}{extension}"
    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"{BASE_URL}/uploads/{filename}"

    logger.info(f"✅ Image uploaded: {image_url}")

    return {
        "success": True,
        "imageUrl": image_url,
        "filename": filename
    }

# ================= MIDDLEWARE =================
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown_db():
    client.close()
