from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

import os
import uuid
import logging
import cloudinary
import cloudinary.uploader

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recette-api")

# ===== ENV =====
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# ⚠️ FIREBASE A DEUX DOMAINES
CORS_ORIGINS = [
    "http://localhost:3000",
    "https://recettes-61ab7.web.app",
    "https://recettes-61ab7.firebaseapp.com"
]

if not all([
    MONGO_URL,
    DB_NAME,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
]):
    raise RuntimeError("Variables d'environnement manquantes")

# ===== CLOUDINARY =====
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

# ===== CORS (FIX FINAL) =====
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

# ===== UPLOAD IMAGE =====
@api.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image")

    result = cloudinary.uploader.upload(
        file.file,
        folder="recettes",
        public_id=str(uuid.uuid4()),
        resource_type="image"
    )

    return {
        "imageUrl": result["secure_url"],
        "public_id": result["public_id"]
    }

# ===== DELETE IMAGE =====
@api.delete("/delete-image")
async def delete_image(payload: dict = Body(...)):
    public_id = payload.get("public_id")
    if not public_id:
        raise HTTPException(status_code=400, detail="public_id manquant")

    cloudinary.uploader.destroy(public_id)
    return {"success": True}

app.include_router(api)

@app.on_event("shutdown")
async def shutdown():
    client.close()
