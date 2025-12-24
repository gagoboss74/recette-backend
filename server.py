from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

import os
import shutil
from pathlib import Path
import uuid
import logging

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recette-api")

# ===== ENV =====
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")

if not MONGO_URL or not DB_NAME:
    raise RuntimeError("Variables d'environnement manquantes")

# ✅ ORIGINES AUTORISÉES (LOCAL + PROD)
CORS_ORIGINS = [
    "http://localhost:3000",
    "https://recettes-61ab7.web.app",
    "https://recette-backend-vbhd.onrender.com",
]

# ===== PATHS =====
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ===== DB =====
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ===== APP =====
app = FastAPI(title="Recette API", version="1.0.0")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== STATIC =====
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

api = APIRouter(prefix="/api")

@api.get("/")
async def root():
    return {"status": "ok"}

@api.post("/upload-image")
async def upload_image(request: Request, file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image")

    ext = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}{ext}"
    path = UPLOAD_DIR / filename

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_url = f"{request.base_url}uploads/{filename}"
    logger.info(f"Image uploaded: {image_url}")

    return {"success": True, "imageUrl": image_url, "filename": filename}

app.include_router(api)

@app.on_event("shutdown")
async def shutdown():
    client.close()
