import time
import os
import json
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import noisereduce as nr
import librosa
import soundfile as sf
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import sqlite3
from pydantic import BaseModel
import uvicorn

# =============================================================================
# App Configuration
# =============================================================================
class GPSData(BaseModel):
    latitude: float
    longitude: float

app = FastAPI(
    title="SuaraWarga API",
    description="Voice-based disaster reporting system for Indonesian citizens",
    version="1.0.0"
)

# Geolocator setup
geolocator = Nominatim(user_agent="suara_warga_disaster_app_v1")

reverse_geocode = RateLimiter(geolocator.reverse, min_delay_seconds=1)

# serve static files frontend
app.mount("/static", StaticFiles(directory="static"), name="static")

# =============================================================================
# GPS Middleware
# =============================================================================
# Configure CORS
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "*" # Use "*" for development, restrict for production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Gemini Client Setup
# =============================================================================

# API Key and Client Initialization
GEMINI_API_KEY = "AIzaSyD0YsAOP6d3lRjN4TBp8OdUOx0dTy3eTEQ"
client = genai.Client(api_key=GEMINI_API_KEY)

# Model configuration
GEMINI_MODEL = "gemini-2.5-flash-lite" 

# =============================================================================
# Database Setup 
# =============================================================================
DB_NAME = "disaster_reports.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # create table if not exists
    c.execute('''CREATE TABLE IF NOT EXISTS reports(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              location TEXT,
              hazard TEXT,
              severity TEXT,
              latitude REAL,
              longitude REAL,
              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
              )''')
    conn.commit()
    conn.close()

# initialize database
init_db()

# =============================================================================
# Audio Processing Functions
# =============================================================================

def clean_audio(input_path: str, output_path: str) -> str:
    """
    Remove background noise from audio file.
    
    Args:
        input_path: Path to the input audio file
        output_path: Path to save the cleaned audio
        
    Returns:
        Path to the cleaned audio file
    """
    # Load the audio file
    data, rate = librosa.load(input_path, sr=None)
    
    # Perform noise reduction
    reduced_noise = nr.reduce_noise(y=data, sr=rate, prop_decrease=1.0)
    
    # Save the cleaned file
    sf.write(output_path, reduced_noise, rate)
    return output_path


def upload_audio_to_gemini(file_path: str):
    """
    Upload audio file to Gemini and wait for processing.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Processed audio file object from Gemini
        
    Raises:
        ValueError: If audio processing fails
    """
    print(f"Uploading {file_path} to Gemini...")
    audio_file = client.files.upload(file=file_path)
    
    # Wait for the file to be processed
    while audio_file.state.name == "PROCESSING":
        print("Processing audio...")
        time.sleep(1)
        audio_file = client.files.get(name=audio_file.name)
    
    if audio_file.state.name == "FAILED":
        raise ValueError("Audio processing failed by Google.")
    
    return audio_file


def analyze_audio_with_gemini(audio_file, location: str) -> dict:
    """
    Send audio to Gemini for transcription and analysis.
    
    Args:
        audio_file: Uploaded audio file object from Gemini
        location: Reverse geocoded location string
    Returns:
        Parsed JSON response with transcription and extracted data
    """
    prompt = """
    Listen to this audio recording carefully. It is a disaster report in Indonesian.
    The speaker might use local dialects, slang, or speak fast. There might be background noise.
    for the adding context, the reporter's location is in here based on GPS: {location}.
    
    Task 1: Transcribe exactly what the user said (improve clarity if needed).
    Task 2: Extract the following data into JSON:
    - "transcription": The exact words spoken by the user.
    - "location": The specific place mentioned (use null if not mentioned).
    - "hazard": The type of disaster (e.g., Banjir, Longsor, Gempa, Kebakaran).
    - "severity": Critical, High, Medium, or Low based on urgency.
    - "description": A brief summary of the incident in Indonesian.
    
    Output ONLY valid JSON without markdown formatting.
    Example format:
    {
        "transcription": "Tolong banjir di jalan pemuda...",
        "location": "Jalan Pemuda",
        "hazard": "Banjir",
        "severity": "High",
        "description": "Laporan banjir di Jalan Pemuda"
    }
    """
    
    print(f"Analyzing audio with {GEMINI_MODEL}...")
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt, audio_file]
    )
    
    # Clean up the response to get pure JSON
    raw_text = response.text
    json_text = raw_text.replace("```json", "").replace("```", "").strip()
    
    return json.loads(json_text)


def cleanup_files(*file_paths: str) -> None:
    """
    Remove temporary files if they exist.
    
    Args:
        file_paths: Variable number of file paths to delete
    """
    for file_path in file_paths:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print(f"Cleaned up: {file_path}")

def get_coordinates(location_name):
    """
    Get latitude and longitude for a given location name using geopy.
    """
    try:
        # We append "Indonesia" to ensure we don't find a 'Semarang' in another country
        search_query = f"{location_name}, Indonesia"
        print(f"Searching map for: {search_query}")
        
        location = geolocator.geocode(search_query)
        
        if location:
            return {
                "lat": location.latitude,
                "long": location.longitude,
                "address": location.address
            }
        else:
            return None # Location not found
            
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/")
def home():
    """Health check endpoint."""
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
def get_reports():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT location, hazard, severity, lat, long FROM reports")
    rows = c.fetchall()
    conn.close()
    
    # Convert to JSON list
    data = []
    for r in rows:
        data.append({
            "location": r[0],
            "hazard": r[1],
            "severity": r[2],
            "lat": r[3],
            "long": r[4]
        })
    return data

@app.post("/receive-location")
async def receive_location(gps_data: GPSData):
    return {"status": "success", "data": gps_data}

@app.post("/report")
async def report_incident(file: UploadFile = File(...)):
    """
    Process voice-based disaster report.
    
    Accepts an audio file, cleans it, transcribes it using Gemini,
    and extracts structured disaster information.
    
    Args:
        file: Uploaded audio file (mp3, wav, m4a, flac, aac, ogg, webm)
        
    Returns:
        JSON with transcription, location, hazard type, and severity
    """
    # Validate file extension
    valid_extensions = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".webm"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in valid_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Supported formats: {valid_extensions}"
        )

    # Define temporary file paths
    temp_filename = f"temp_{file.filename}"
    cleaned_filename = f"cleaned_{file.filename}"

    try:
        # Step 1: Save uploaded file
        content = await file.read()
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)
        print(f"Saved temporary file: {temp_filename}")
        
        # Step 2: Clean the audio (noise reduction)
        clean_audio(temp_filename, cleaned_filename)
        print(f"Audio cleaned: {cleaned_filename}")

        # Step 3: Upload to Gemini
        audio_file = upload_audio_to_gemini(cleaned_filename)

        coords = get_coordinates("Indonesia")["data"]  
        location = reverse_geocode((coords["lat"], coords["long"]))
        print(f"Lokasi anda sesuai Map: {location}")

        # Step 4: Analyze with Gemini
        result = analyze_audio_with_gemini(audio_file, location)
        print(f"Analysis result: {result}")
        
        # Step 6: Store report in database
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO reports(location, hazard, severity, latitude, longitude)
                     VALUES (?, ?, ?, ?, ?)''',
                  (
                      result.get("location"),
                      result.get("hazard"),
                      result.get("severity"),
                      coords["latitude"] if coords else None,
                      coords["longitude"] if coords else None
                  ))
        conn.commit()
        conn.close()
        print ("Report stored in database.")

        return {
            "status": "success",
            "data": result
        }
        
    except json.JSONDecodeError as e:
        print(f"JSON parsing error: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to parse AI response as JSON"
        )
    except ValueError as e:
        print(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred: {str(e)}"
        )
    finally:
        # Always clean up temporary files
        cleanup_files(temp_filename, cleaned_filename)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
