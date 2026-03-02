import os, time
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional
from app.services.audio_service import validate_audio, reduce_noise
from app.services.ai_service import analyze_report
from app.services.geo_service import get_location_name, get_coordinates
from app.db.models import insert_report

router = APIRouter()

@router.post("/report")
async def submit_report(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None)
):
    tmp_path = f"data/tmp_{int(time.time())}.webm"
    cleaned_path = f"data/clean_{int(time.time())}.wav"

    try:
        with open(tmp_path, "wb") as f:
            f.write(await file.read())

        validation = validate_audio(tmp_path)
        if not validation["valid"]:
            return {"status": "error", "error_type": validation["reason"], "message": "Audio tidak valid."}
        
        reduce_noise(tmp_path, cleaned_path)

        location_context = None
        if latitude and longitude:
            location_context = get_location_name(latitude, longitude)

        result = analyze_report(cleaned_path, location_context)

        if not result.get("is_disaster"):
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
    
    finally:
        for path in [tmp_path, cleaned_path]:
            if os.path.exists(path):
                os.remove(path)