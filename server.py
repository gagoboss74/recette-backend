from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

import os
import uuid
import logging
import cloudinary
import cloudinary.uploader
import cloudinary.api

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recette-api")

# ===== ENV =====
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://recettes-61ab7.web.app"
).split(",")

if not all([
    MONGO_URL,
    DB_NAME,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
]):
    raise RuntimeError("❌ Variables d'environnement manquantes")

# ===== CLOUDINARY CONFIG =====
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

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

api = APIRouter(prefix="/api")

# ===== HEALTH =====
@api.get("/")
async def root():
    return {"status": "ok"}

# ===== UPLOAD IMAGE (CLOUDINARY) =====
@api.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image")

    try:
        result = cloudinary.uploader.upload(
            file.file,
            folder="recettes",
            public_id=str(uuid.uuid4()),
            resource_type="image"
        )

        logger.info(f"✅ Image uploaded: {result['secure_url']}")

        return {
            "imageUrl": result["secure_url"],
            "public_id": result["public_id"]
        }

    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

# ===== DELETE IMAGE (CLOUDINARY) =====
@api.delete("/delete-image")
async def delete_image(payload: dict):
    public_id = payload.get("public_id")
    if not public_id:
        raise HTTPException(status_code=400, detail="public_id manquant")

    try:
        cloudinary.uploader.destroy(public_id)
        logger.info(f"🗑️ Image deleted: {public_id}")
        return {"success": True}
    except Exception as e:
        logger.error(f"❌ Delete error: {e}")
        raise HTTPException(status_code=500, detail="Delete failed")

app.include_router(api)

@app.on_event("shutdown")
async def shutdown():
    client.close()
