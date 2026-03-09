requirement
ffmpeg

problem to validate the sound is really record or just noise or blank record

# Production
pip install -r requirements.txt -r requirements-audio.txt

# Development
pip install -r requirements.txt -r requirements-audio.txt -r requirements-dev.txt


Flow:
    1. Receive audio file + GPS coordinates (optional) from frontend
    2. validate the audio from length and the noise
    3. Clean audio (noise reduction)
    4. If GPS provided: reverse geocode to get location name
    5. Upload audio to Gemini
    6. Analyze with AI (audio + location context)
    7. Get coordinates for the location mentioned in report
    8. Store in database
    9. Return result to frontend