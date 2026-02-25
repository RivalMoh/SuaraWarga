import time
import os
import json
import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
import noisereduce as nr
import librosa
import soundfile as sf
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import sqlite3
from typing import Optional
import uvicorn
import uuid
import logging

# =============================================================================
# App Configuration
# =============================================================================
app = FastAPI(
    title="SuaraWarga API",
    description="Voice-based disaster reporting system for Indonesian citizens",
    version="1.0.0"
)

# Geolocator setup
geolocator = Nominatim(user_agent="suara_warga_disaster_app_v1")
reverse_geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)
forward_geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

# =============================================================================
# CORS Middleware
# =============================================================================
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve static files frontend (must be after CORS middleware)
app.mount("/static", StaticFiles(directory="static"), name="static")

# =============================================================================
# Gemini Client Setup
# =============================================================================
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = "gemini-2.5-flash-lite"


# Audio validation parameters
MIN_AUDIO_DURATION = 1.5
MIN_AUDIO_RMS = 0.01
SILENCE_THRESHOLD = 0.02

# =============================================================================
# Database Setup 
# =============================================================================
DB_NAME = "disaster_reports.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              transcription TEXT,
              location TEXT,
              hazard TEXT,
              severity TEXT,
              description TEXT,
              latitude REAL,
              longitude REAL,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
              )''')
    conn.commit()
    conn.close()

init_db()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# =============================================================================
# Audio Processing Functions
# =============================================================================

def validate_audio(file_path: str) -> dict:
    """
    Validate audio file format and properties.
    """
    try:
        # load audio file
        data, rate = librosa.load(file_path, sr=None)

        # duration
        duration = len(data)/rate

        # measure of volume (RMS)
        rms = np.sqrt(np.mean(data**2))

        # calculate percentage of non-silent frames
        frame_length = int(rate * 0.025)  # 25ms frames
        hop_length = int(rate * 0.010)    # 10ms hops

        # get RMS for each frame
        rms_frames = librosa.feature.rms(y=data, frame_length=frame_length, hop_length=hop_length)[0]

        # count frames above silence threshold
        non_silent_frames = np.sum(rms_frames > SILENCE_THRESHOLD)
        total_frames = len(rms_frames)
        speech_ratio = non_silent_frames / total_frames if total_frames > 0 else 0

        logging.info(f"Audio duration: {duration:.2f}s, RMS: {rms:.4f}, Speech ratio: {speech_ratio:.2%}")

        # validation checks
        if duration < MIN_AUDIO_DURATION:
            return {
                "valid": False,
                "reason": f"Rekaman terlalu pendek ({duration:.2f}s). Minimal durasi adalah {MIN_AUDIO_DURATION}s.",
                "duration": duration,
                "rms": rms,
                "speech_ratio": speech_ratio
            }
        
        if speech_ratio < 0.1: # less than 10% speech
            return {
                "valid": False,
                "reason": "Rekaman terlalu sunyi atau tidak ada suara bicara terdeteksi.",
                "duration": duration,
                "rms": rms,
                "speech_ratio": speech_ratio
            }

        return {
            "valid": True,
            "duration": duration,
            "reason": "Audio valid",
            "rms": rms,
            "speech_ratio": speech_ratio
        }
    
    except Exception as e:
        logging.error(f"Audio validation error: {e}")
        return {
            "valid": False,
            "reason": f"Gagal memvalidasi audio: {str(e)}",
            "duration": 0,
            "rms": 0,
            "speech_ratio": 0
        }

def clean_audio(input_path: str, output_path: str) -> str:
    """
    Remove background noise from audio file.
    """
    data, rate = librosa.load(input_path, sr=None)
    reduced_noise = nr.reduce_noise(y=data, sr=rate, prop_decrease=0.8)
    sf.write(output_path, reduced_noise, rate)
    return output_path


def upload_audio_to_gemini(file_path: str):
    """
    Upload audio file to Gemini and wait for processing.
    """
    logging.info(f"Uploading {file_path} to Gemini...")
    audio_file = client.files.upload(file=file_path)
    
    while audio_file.state.name == "PROCESSING":
        logging.info("Processing audio...")
        time.sleep(1)
        audio_file = client.files.get(name=audio_file.name)
    
    if audio_file.state.name == "FAILED":
        raise ValueError("Audio processing failed by Google.")
    
    return audio_file


def analyze_audio_with_gemini(audio_file, location_context: str) -> dict:
    """
    Send audio to Gemini for transcription and analysis.
    
    Args:
        audio_file: Uploaded audio file object from Gemini
        location_context: Location string from GPS for added context
        
    Returns:
        Parsed JSON response with transcription and extracted data
    """
    prompt = """
    Listen to this audio recording carefully. It is supposed to be a disaster report in Indonesian language.
    The audio is in Bahasa Indonesia. transcribe in indonesia, not in Japanese or other languages.
    The speaker might use local dialects, slang, or speak fast. There might be background noise.
    
    IMPORTANT RULES:
    1. If the audio is SILENT, contains only noise, or has NO CLEAR SPEECH, respond with:
       {"error": "NO_SPEECH", "message": "Tidak ada suara yang dapat dikenali"}
    
    2. If the audio contains speech but is NOT about a disaster/emergency, respond with:
       {"error": "NOT_DISASTER", "message": "Laporan tidak berkaitan dengan bencana"}
    
    3. If the speech is UNCLEAR or UNINTELLIGIBLE, respond with:
       {"error": "UNCLEAR", "message": "Suara tidak jelas, silakan ulangi"}
    
    4. ONLY if there is CLEAR SPEECH about a DISASTER, extract the data.
    
    CONTEXT: The reporter's GPS location is: LOCATION_CONTEXT_PLACEHOLDER
    Use this location as reference to help clarify ambiguous place names, especially if the speaker 
    doesn't mention a specific location or the place name is common/exists in multiple regions.
    
    For VALID disaster reports, extract:
    - "transcription": The exact words spoken by the user (must not be empty).
    - "location": The specific place mentioned. If not mentioned, use GPS context.
    - "hazard": The type of disaster (Banjir, Longsor, Gempa, Kebakaran, Tsunami, Angin Puting Beliung, Kekeringan, Erupsi Vulkanik, dan lain-lain).
    - "severity": Critical, High, Medium, or Low based on urgency.
    - "description": A brief summary of the incident in Indonesian.
    - "confidence": A number between 0 and 1 indicating how confident you are in the extraction (optional but helpful).
    
    Output ONLY valid JSON without markdown formatting.
    
    Valid report example:
    {"transcription": "Tolong ada banjir di jalan pemuda", "location": "Jalan Pemuda", "hazard": "Banjir", "severity": "High", "description": "Laporan banjir di Jalan Pemuda", "confidence": 0.95}
    
    Invalid/silent example:
    {"error": "NO_SPEECH", "message": "Tidak ada suara yang dapat dikenali"}
    """.replace("LOCATION_CONTEXT_PLACEHOLDER", location_context)

    try:
        logging.info(f"Analyzing audio with {GEMINI_MODEL}...")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[prompt, audio_file]
        )
        
        raw_text = response.text
        logging.info(f"Raw AI response: {raw_text}")
        
        # Clean up the response to get pure JSON
        json_text = raw_text.replace("```json", "").replace("```", "").strip()
        
        # Find JSON object in response (fallback)
        start_idx = json_text.find("{")
        end_idx = json_text.rfind("}") + 1
        if start_idx != -1 and end_idx > start_idx:
            json_text = json_text[start_idx:end_idx]
        
        return json.loads(json_text)
    
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error: {e}")
        return {
            "error": "JSON_PARSE_ERROR",
            "message": "Gagal memparsing respons AI, silahkan coba lagi."}


def cleanup_files(*file_paths: str) -> None:
    """Remove temporary files if they exist."""
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Cleaned up: {file_path}")


def get_location_from_coordinates(lat: float, lng: float) -> str:
    """
    Reverse geocode: Convert coordinates to location name.
    
    Args:
        lat: Latitude
        lng: Longitude
        
    Returns:
        Human-readable address string
    """
    try:
        logging.info(f"Reverse geocoding: ({lat}, {lng})")
        location = reverse_geocode((lat, lng), language="id")
        
        if location:
            return location.address
        return "Lokasi tidak diketahui"
        
    except Exception as e:
        logging.error(f"Reverse geocoding error: {e}")
        return "Lokasi tidak diketahui"


def get_coordinates_from_location(location_name: str) -> dict | None:
    """
    Forward geocode: Convert location name to coordinates.
    
    Args:
        location_name: Place name to search
        
    Returns:
        Dict with lat, long, address or None if not found
    """
    try:
        search_query = f"{location_name}, Indonesia"
        logging.info(f"Forward geocoding: {search_query}")
        
        location = forward_geocode(search_query)
        
        if location:
            return {
                "lat": location.latitude,
                "long": location.longitude,
                "address": location.address
            }
        return None
        
    except Exception as e:
        logging.error(f"Forward geocoding error: {e}")
        return None


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
def home():
    """Serve the frontend."""
    return FileResponse("static/index.html")


@app.get("/models")
def list_models():
    """List available Gemini models (for debugging)."""
    try:
        models = []
        for model in client.models.list():
            models.append(model.name)
        return {"available_models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports")
def get_reports(page: int = 1, limit: int = 20):
    """Get all disaster reports from database."""
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 20

    offset = (page - 1) * limit

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0]

    c.execute(
        "SELECT location, hazard, severity, latitude, longitude FROM reports LIMIT ? OFFSET ?", (limit, offset)
    )
    rows = c.fetchall()
    conn.close()
    
    data = []
    for r in rows:
        data.append({
            "location": r[0],
            "hazard": r[1],
            "severity": r[2],
            "lat": r[3],
            "long": r[4]
        })
        
    return {
        "data": data,
        "total": total_reports,
        "page": page,
        "limit": limit,
        "total_pages": (total_reports + limit - 1) // limit
    }


@app.post("/report")
async def report_incident(
    file: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None)
):
    """
    Process voice-based disaster report.

    Args:
        file: Uploaded audio file
        latitude: GPS latitude from frontend (optional)
        longitude: GPS longitude from frontend (optional)
    """
    # Validate file extension
    valid_extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".webm"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in valid_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Supported formats: {valid_extensions}"
        )

    temp_filename = f"temp_{uuid.uuid4().hex}{file_ext}"
    cleaned_filename = f"cleaned_{uuid.uuid4().hex}{file_ext}"

    try:
        # upload file to temporary location
        content = await file.read()
        
        # limit file size to 10MB
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File size exceeds 10MB limit.")
        
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)
        logging.info(f"Saved temporary file: {temp_filename}")

        # validate audio
        validation = validate_audio(temp_filename)
        if not validation["valid"]:
            logging.warning(f"Audio validation failed: {validation['reason']}")
            return {
                "status": "error",
                "error_type": "INVALID_AUDIO",
                "message": validation["reason"],
                "audio_stats":{
                    "duration": validation["duration"],
                    "speech_ratio": validation["speech_ratio"]
                }
            }
        
        # clean the audio
        clean_audio(temp_filename, cleaned_filename)
        logging.info(f"Audio cleaned: {cleaned_filename}")

        # Get location from GPS if provided
        location_context = "Tidak tersedia (GPS tidak aktif)"
        user_coords = None
        
        if latitude is not None and longitude is not None:
            user_coords = {"lat": latitude, "long": longitude}
            location_context = get_location_from_coordinates(latitude, longitude)
            logging.info(f"User location from GPS: {location_context}")
        else:
            logging.warning("No GPS coordinates provided")

        # Upload audio to Gemini
        audio_file = upload_audio_to_gemini(cleaned_filename)

        # Analyze audio with Gemini
        result = analyze_audio_with_gemini(audio_file, location_context)
        logging.info(f"Analysis result: {result}")

        if result.get("confidence") < 0.4:
            logging.warning(f"Low confidence in AI extraction: {result.get('confidence')}")
            return {
                "status": "error",
                "error_type": "LOW_CONFIDENCE",
                "message": "AI tidak yakin dengan hasil ekstraksi, silakan coba lagi dengan suara yang lebih jelas."
            }

        if "error" in result:
            logging.error(f"AI analysis error: {result['message']}")
            return {
                "status": "error",
                "error_type": result["error"],
                "message": result["message"]
            }

        # get coordinates for the location mentioned in report
        final_coords = None
        
        # First, try to geocode the location mentioned in the report
        if result.get("location"):
            final_coords = get_coordinates_from_location(result["location"])
        
        # Fallback to user's GPS coordinates if geocoding fails
        if not final_coords and user_coords:
            final_coords = {
                "lat": user_coords["lat"],
                "long": user_coords["long"],
                "address": location_context
            }
        
        # Add coordinates to result
        result["coordinates"] = final_coords

        # store report in database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO reports(transcription, location, hazard, severity, description, latitude, longitude)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (
                      result.get("transcription"),
                      result.get("location"),
                      result.get("hazard"),
                      result.get("severity"),
                      result.get("description"),
                      final_coords["lat"] if final_coords else None,
                      final_coords["long"] if final_coords else None
                  ))
        conn.commit()
        conn.close()
        logging.info("Report stored in database.")

        return {
            "status": "success",
            "data": result
        }
        
    except json.JSONDecodeError as e:
        logging.error(f"JSON parsing error: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to parse AI response as JSON"
        )
    except ValueError as e:
        logging.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred: {str(e)}"
        )
    finally:
        cleanup_files(temp_filename, cleaned_filename)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)