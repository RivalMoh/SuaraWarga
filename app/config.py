import os
from dotenv import load_dotenv

load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")
gemini_model = "gemini-2.5-flash-lite"

# audio validation paramaters
MIN_AUDIO_DURATION = 2  # seconds
MIN_AUDIO_RMS = 0.01
SILENCE_THRESHOLD = 0.02

# database
DB_NAME = os.getenv("DB_NAME", "data/disaster_reports.db")

# server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",")