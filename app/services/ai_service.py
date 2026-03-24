import json
import re
from google import genai
from app.config import gemini_api_key, gemini_model

client = genai.Client(api_key=gemini_api_key)

def analyze_report(audio_path: str, location_context: str) -> dict:
    audio_file = client.files.upload(file=audio_path)

    prompt = """
    Listen to this audio recording carefully. It is supposed to be a disaster report in Indonesian language.
    The audio is in Bahasa Indonesia. transcribe in indonesia, not in Japanese or other languages.
    The speaker might use local dialects, slang, or speak fast. There might be background noise.
    
    CONTEXT: The reporter's GPS location is: LOCATION_CONTEXT_PLACEHOLDER
    Use this location as reference to help clarify ambiguous place names, especially if the speaker 
    doesn't mention a specific location or the place name is common/exists in multiple regions.
    
    For VALID disaster reports, extract:
    - "transcription": The exact words spoken by the user (must not be empty).
    - "location": The specific place mentioned in the audio but use the CONTEXT to clarify if needed like user just say "jalan Pemuda" but you should complete it with city and province be like "Jalan Pemuda, Kota Semarang, Jawa Tengah". If no location is mentioned, try use the location context to estimated it. for example if the location context is in Semarang, and the user just say "jalan Pemuda" you can estimated it to be "Jalan Pemuda, Kota Semarang, Jawa Tengah" or if like the user just say the name of building try to find the address by combine with context location for example user just say "masjid at takwa" and context location "Jalan Pemuda, Kota Semarang, Jawa Tengah" estimated the location address "Masjid at takwa, Jalan Pemuda, Kota Semarang, Jawa Tengah". If you can't find any location in the audio and also can't estimated it from the location context, just put "Unknown".
    - "hazard": The type of disaster (Banjir, Longsor, Gempa, Kebakaran, Tsunami, Angin Puting Beliung, Kekeringan, Erupsi Vulkanik, dan lain-lain).
    - "severity": Critical, High, Medium, or Low based on urgency.
    - "description": A brief summary of the incident in Indonesian language.
    - "confidence": A number between 0 and 1 indicating how confident you are in the extraction of the audio.
    - "validation": "OK" if it's a valid report about the disaster, otherwise one of the error codes above.
    
    Output ONLY valid JSON without markdown formatting. with this exact structure:
    {
        "transcription": "...",
        "location": "...",
        "hazard": "Banjir|Longsor|Gempa|Kebakaran|Tsunami|Angin Puting Beliung|Kekeringan|Erupsi Vulkanik|Lainnya",
        "severity": "Critical|High|Medium|Low",
        "description": "...",
        "confidence": 0.0,
        "validation": "OK|NO_SPEECH|NOT_DISASTER|UNCLEAR|INCOMPLETE_REPORT"
    }
    
    Valid report example:
    {
        "transcription": "Tolong ada banjir di jalan pemuda", 
        "location": "Jalan Pemuda", 
        "hazard": "Banjir",
        "severity": "High", 
        "description": "Laporan banjir di Jalan Pemuda", 
        "confidence": 0.95,
        "validation": "OK"
    }
    """.replace("LOCATION_CONTEXT_PLACEHOLDER", location_context)

    response = client.models.generate_content(
        model=gemini_model,
        contents=[
            audio_file,
            prompt
        ]
    )

    text = response.text.strip()
    # Try to extract JSON from markdown code block first
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:].strip()
    else:
        # Try to find a raw JSON object in the response
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            text = match.group(0)
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "transcription": "",
            "location": "Unknown",
            "hazard": "Lainnya",
            "severity": "Low",
            "description": "Gagal memproses laporan. Format respons tidak valid.",
            "confidence": 0.0,
            "validation": "INCOMPLETE_REPORT"
        }

