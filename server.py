from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

import os
import uuid
import logging
import cloudinary
import cloudinary.uploader

import firebase_admin
from firebase_admin import credentials, auth

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recette-api")

# ===== ENV =====
MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME")
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://recettes-61ab7.web.app"
).split(",")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

if not all([
    MONGO_URL,
    DB_NAME,
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
]):
    raise RuntimeError("❌ Variables d'environnement manquantes")

# ===== CLOUDINARY =====
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True,
)

# ===== FIREBASE ADMIN =====
cred = credentials.Certificate("/etc/secrets/firebase_service_account.json")
firebase_admin.initialize_app(cred)

# ===== DB =====
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ===== APP =====
app = FastAPI(title="Recette API", version="2.0.0")

# ===== CORS =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")

# ===== AUTH DEPENDENCY =====
async def verify_firebase_token(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        decoded = auth.verify_id_token(token)
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# ===== HEALTH =====
@api.get("/")
async def root():
    return {"status": "ok"}

# ===== UPLOAD IMAGE (SECURED) =====
@api.post("/upload-image")
async def upload_image(
    file: UploadFile = File(...),
    user=Depends(verify_firebase_token),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image")

    result = cloudinary.uploader.upload(
        file.file,
        folder="recettes",
        public_id=str(uuid.uuid4()),
    )

    logger.info(f"Image uploaded by {user['uid']}")

    return {
        "success": True,
        "imageUrl": result["secure_url"],
        "public_id": result["public_id"],
        "uid": user["uid"],
    }

# ===== DELETE IMAGE =====
@api.delete("/delete-image")
async def delete_image(
    public_id: str,
    user=Depends(verify_firebase_token),
):
    cloudinary.uploader.destroy(public_id)
    logger.info(f"Image deleted by {user['uid']}")
    return {"success": True}

app.include_router(api)

@app.on_event("shutdown")
async def shutdown():
    client.close()
