import numpy as np
import librosa
import soundfile as sf
import noisereduce as nr
from app.config import MIN_AUDIO_DURATION, MIN_AUDIO_RMS, SILENCE_THRESHOLD

def validate_audio(file_path: str) -> dict:
    try:
        data, rate = librosa.load(file_path, sr=None)
        duration = len(data) / rate
        rms = np.sqrt(np.mean(data**2))

        frame_length = int(rate * 0.025)
        hop_length = int(rate * 0.010)
        frames_rms = librosa.feature.rms(
            y=data, 
            frame_length=frame_length, hop_length=hop_length
        )[0]
        non_silent = np.sum(frames_rms > SILENCE_THRESHOLD) / len(frames_rms)

        if duration < MIN_AUDIO_DURATION:
            return {"valid": False, "reason": "Audio too short"}
        if rms < MIN_AUDIO_RMS or non_silent < 0.1:
            return {"valid": False, "reason": "Audio too quiet or mostly silent"}
        
        return {"valid": True, "duration": duration, "rms": float(rms)}
    
    except Exception as e:
        return {"valid": False, "reason": "Error processing audio: ", "error": str(e)}
    
def reduce_noise(file_path: str, output_path: str):
    data, rate = librosa.load(file_path, sr=None)
    reduced = nr.reduce_noise(y=data, sr=rate)
    sf.write(output_path, reduced, rate)