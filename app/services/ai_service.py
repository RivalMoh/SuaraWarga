import json
from google import genai
from app.config import gemini_api_key, gemini_model

client = genai.Client(api_key=gemini_api_key)

def analyze_report(audio_path: str, location_context: str) -> dict:
    audio_file = client.upload_file(path=audio_path)

    prompt = f"""
    Listen to this audio recording carefully. It is supposed to be a disaster report in Indonesian language.
    The audio is in Bahasa Indonesia. transcribe in indonesia, not in Japanese or other languages.
    The speaker might use local dialects, slang, or speak fast. There might be background noise.
    {"Location context: " + location_context if location_context else ""}
    The reporter's GPS location is: LOCATION_CONTEXT_PLACEHOLDER
    Use this location as reference to help clarify ambiguous place names, especially if the speaker 
    doesn't mention a specific location or the place name is common/exists in multiple regions.

    Return JSON with:
    {{
        "transcription": "...",
        "hazard": "...",
        "severity": "critical|high|medium|low",
        "location": "...",
        "description": "...",
        "is_disaster": true/false,
        "validation": "OK|NO_SPEECH|NOT_DISASTER|UNCLEAR|INCOMPLETE_REPORT"
    }}
    """

    response = client.models.generate_content(
        model=gemini_model,
        contents=[
            audio_file,
            prompt
        ]
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]  # Extract JSON from code block
        if text.startswith("json"):
            text = text[4:].strip()  # Remove "json" prefix if present
    
    return json.loads(text)

