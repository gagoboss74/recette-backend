from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import shutil
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone

# ========================
# ENV & PATHS
# ========================

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

# ========================
# DATABASE
# ========================

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ========================
# UPLOADS DIRECTORY
# ========================

UPLOAD_DIR = ROOT_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ========================
# APP & ROUTER
# ========================

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ========================
# LOGGING
# ========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ========================
# MODELS
# ========================

class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

# ========================
# BASIC ROUTES
# ========================

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

# ========================
# IMAGE UPLOAD
# ========================

@api_router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    try:
        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        extension = Path(file.filename).suffix
        filename = f"{uuid.uuid4()}_{int(datetime.now().timestamp())}{extension}"
        file_path = UPLOAD_DIR / filename

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        image_url = f"{BASE_URL}/api/images/{filename}"

        logger.info(f"Image uploaded: {filename}")

        return {
            "success": True,
            "imageUrl": image_url,
            "filename": filename
        }

    except Exception as e:
        logger.error(str(e))
        raise HTTPException(status_code=500, detail="Upload failed")

@api_router.get("/images/{filename}")
async def get_image(filename: str):
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)

@api_router.delete("/images/{filename}")
async def delete_image(filename: str):
    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()
        return {"success": True}
    raise HTTPException(status_code=404, detail="Image not found")

# ========================
# MIDDLEWARE & ROUTES
# ========================

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db():
    client.close()
