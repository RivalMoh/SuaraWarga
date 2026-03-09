import os, time
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
from app.services.audio_service import validate_audio, reduce_noise
from app.services.ai_service import analyze_report
from app.services.geo_service import get_location_name, get_coordinates
from app.db.models import insert_report
import uuid

router = APIRouter()

@router.post("/report")
async def submit_report(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None)
):
    # Define upload constraints
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
    ALLOWED_EXTENSIONS = {".webm", ".wav", ".mp3", ".m4a", ".ogg"}

    os.makedirs("data", exist_ok=True)
    unique_id = uuid.uuid4().hex[:12]
    tmp_path = f"data/tmp_{unique_id}.webm"
    cleaned_path = f"data/clean_{unique_id}.wav"

    # Basic file type validation before saving
    filename = file.filename or ""
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if ext not in ALLOWED_EXTENSIONS or not file.content_type or not file.content_type.startswith("audio/"):
        return {
            "status": "error",
            "error_type": "invalid_file_type",
            "message": "Format file tidak didukung. Harap unggah file audio."
        }

    try:
        total_size = 0
        chunk_size = 1024 * 1024  # 1 MB
        with open(tmp_path, "wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > MAX_UPLOAD_SIZE:
                    # Hentikan jika ukuran file melebihi batas
                    return {
                        "status": "error",
                        "error_type": "file_too_large",
                        "message": "Ukuran file melebihi batas maksimum yang diizinkan."
                    }
                f.write(chunk)

        validation = validate_audio(tmp_path)
        if not validation["valid"]:
            return {"status": "error", "error_type": validation["reason"], "message": "Audio tidak valid."}
        
        reduce_noise(tmp_path, cleaned_path)

        location_context = None
        if latitude and longitude:
            location_context = get_location_name(latitude, longitude)
            
        try:
            result = analyze_report(cleaned_path, location_context)

            if result.get("validation") != "OK":
                return {
                    "status": "error",
                    "error_type": result.get("validation"),
                    "message": "Laporan tidak teridentifikasi sebagai bencana."
                }

            coords = get_coordinates(result.get("location", ""))

            # save to DB
            insert_report({
                **result,
                "latitude": coords.get("lat"),
                "longitude": coords.get("long"),
            })

            return {
                "status": "success", 
                "data": {**result, "coordinates": coords}
            }
        except Exception as e:
            return {
                "status": "error",
                "error_type": "processing_error",
                "message": f"Terjadi kesalahan saat memproses laporan: {str(e)}"
            }
    
    finally:
        for path in [tmp_path, cleaned_path]:
            if os.path.exists(path):
                os.remove(path)