# SuaraWarga — Voice-First Disaster Reporting

> **Tema:** *Small Apps for Big Preparedness: Solusi Digital untuk Kesiapsiagaan Bencana*

SuaraWarga is a Progressive Web App (PWA) that lets anyone report a disaster by simply holding a button and speaking. A multimodal AI pipeline converts the raw, noisy voice recording into structured, geocoded intelligence — displayed on a live map for rapid emergency response.

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Processing Pipeline](#3-processing-pipeline)
4. [Project Structure](#4-project-structure)
5. [Tech Stack](#5-tech-stack)
6. [Prerequisites](#6-prerequisites)
7. [Installation](#7-installation)
8. [Environment Variables](#8-environment-variables)
9. [Running the App](#9-running-the-app)
10. [API Reference](#10-api-reference)
11. [Key Innovations](#11-key-innovations)
12. [Technical Limitations & Mitigations](#12-technical-limitations--mitigations)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. Overview

### The Problem
Indonesia has a disaster vulnerability score of 43.5%. During crises, information spreads through chaotic WhatsApp chains — full of misinformation and delayed responses. Worse, victims in a state of panic, injury, or severe weather cannot easily type out detailed forms.

### The Solution
A **"Zero-Friction"** reporting tool. Hold one button, speak naturally, let the AI do the rest.

### Value Proposition
| Audience | Benefit |
|---|---|
| **General Public** | No app download required (PWA). Works on any browser. Minimal digital literacy needed. |
| **Authorities (BPBD / SAR)** | Raw panic audio → structured JSON (location, hazard type, severity, coordinates) on a live dashboard. |

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND (PWA)                   │
│   HTML5 + Vanilla JS + Leaflet.js                   │
│   MediaRecorder API  │  Geolocation API             │
└───────────────────┬─────────────────────────────────┘
                    │  POST /report  (audio + GPS)
                    ▼
┌─────────────────────────────────────────────────────┐
│                 BACKEND (FastAPI)                   │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ audio_service│  │  ai_service  │  │geo_service│ │
│  │  (validate + │  │   (Gemini    │  │ (Nominatim│ │
│  │ noise reduce)│  │  multimodal) │  │  geocode) │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│                  SQLite Database                    │
└─────────────────────────────────────────────────────┘
```

**Frontend** — Runs entirely in the browser; no app-store friction. Captures audio via `MediaRecorder`, obtains GPS via the `Geolocation API`, and renders reports on an interactive `Leaflet.js` map.

**Backend** — Python + FastAPI (async). Handles file validation, audio processing, AI analysis, geocoding, and persistence.

**AI Engine** — Google Gemini 2.5 Flash Lite (multimodal). Processes raw audio directly — transcription and structured extraction happen in a single inference step.

**Database** — SQLite; lightweight and file-based, suitable for MVP scale.

---

## 3. Processing Pipeline

```
Audio File + GPS (optional)
        │
        ▼
1. Input Validation
   ├─ Allowed extensions: .webm .wav .mp3 .m4a .ogg
   ├─ Max file size:       10 MB
   └─ Content-Type check

        │
        ▼
2. Audio Quality Validation  (librosa)
   ├─ Min duration:    2 seconds
   ├─ Min RMS energy:  0.01
   └─ Non-silent frames > 10%

        │
        ▼
3. Noise Reduction  (noisereduce + soundfile)
   └─ Outputs a clean .wav file

        │
        ▼
4. Reverse Geocoding  (geopy / Nominatim)  ← only if GPS provided
   └─ lat/lon → human-readable address (location_context)

        │
        ▼
5. AI Analysis  (Gemini 2.5 Flash Lite)
   └─ Returns JSON:
      {transcription, hazard, severity, location,
       description, is_disaster, validation}

        │
        ▼
6. Forward Geocoding  (geopy / Nominatim)
   └─ AI-extracted location name → lat/lon coordinates

        │
        ▼
7. Persist to Database  (SQLite)

        │
        ▼
8. Return structured response to frontend
```

---

## 4. Project Structure

```
SuaraWarga/
├── main.py                   # Entry point — runs Uvicorn server
├── requirements.txt          # Core dependencies
├── requirements-audio.txt    # Audio processing dependencies (needs ffmpeg)
├── requirements-dev.txt      # Development dependencies
│
├── app/
│   ├── __init__.py           # App factory (FastAPI, CORS, routers, static)
│   ├── config.py             # Config from env vars (.env)
│   │
│   ├── api/
│   │   ├── root.py           # GET /  → serves index.html
│   │   ├── report.py         # POST /report  → submit voice report
│   │   └── history.py        # GET /api/reports → paginated report list
│   │
│   ├── db/
│   │   ├── database.py       # SQLite connection & table initialisation
│   │   └── models.py         # insert_report(), get_reports()
│   │
│   └── services/
│       ├── audio_service.py  # validate_audio(), reduce_noise()
│       ├── ai_service.py     # analyze_report()  ← Gemini call
│       └── geo_service.py    # get_location_name(), get_coordinates()
│
├── static/
│   ├── index.html            # PWA shell
│   ├── manifest.json         # PWA manifest
│   ├── sw.js                 # Service Worker
│   ├── css/style.css
│   └── js/app.js             # All frontend logic
│
└── data/                     # Runtime: SQLite DB + temp audio files
```

---

## 5. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, Vanilla JS, Leaflet.js |
| Backend | Python 3, FastAPI, Uvicorn |
| AI | Google Gemini 2.5 Flash Lite (multimodal) |
| Audio Processing | librosa, noisereduce, soundfile, numpy |
| Geocoding | geopy (Nominatim / OpenStreetMap) |
| Database | SQLite |
| PWA | Web App Manifest, Service Worker |

---

## 6. Prerequisites

- **Python 3.10+**
- **ffmpeg** — required by librosa for audio decoding

```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (via Chocolatey)
choco install ffmpeg
```

---

## 7. Installation

```bash
# Clone the repository
git clone https://github.com/your-username/SuaraWarga.git
cd SuaraWarga

# Production
pip install -r requirements.txt -r requirements-audio.txt

# Development (adds dev tools)
pip install -r requirements.txt -r requirements-audio.txt -r requirements-dev.txt
```

---

## 8. Environment Variables

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_google_gemini_api_key_here
DB_NAME=data/disaster_reports.db   # optional, this is the default
HOST=0.0.0.0                        # optional
PORT=8000                           # optional
```

> Get a Gemini API key from [Google AI Studio](https://aistudio.google.com/).

---

## 9. Running the App

```bash
python main.py
```

The server starts at `http://localhost:8000`.  
Open the URL in a browser — the PWA interface loads automatically.

---

## 10. API Reference

### `POST /report`
Submit a voice disaster report.

**Form Data:**

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | audio file | ✅ | `.webm`, `.wav`, `.mp3`, `.m4a`, or `.ogg`; max 10 MB |
| `latitude` | float | ❌ | User's GPS latitude |
| `longitude` | float | ❌ | User's GPS longitude |

**Success Response `200`:**
```json
{
  "status": "success",
  "data": {
    "transcription": "Ada banjir di Jalan Pemuda...",
    "hazard": "Banjir",
    "severity": "high",
    "location": "Jalan Pemuda, Semarang",
    "description": "Banjir setinggi lutut, warga butuh evakuasi.",
    "is_disaster": true,
    "validation": "OK",
    "coordinates": { "lat": -6.9932, "long": 110.4203 }
  }
}
```

**Error Response `200`:**
```json
{
  "status": "error",
  "error_type": "Audio too short | Audio too quiet or mostly silent | invalid_file_type | file_too_large | NOT_DISASTER | ...",
  "message": "Human-readable error message."
}
```

---

### `GET /api/reports`
Retrieve paginated list of historical reports.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | `1` | Page number |
| `limit` | int | `5` | Reports per page |

**Response `200`:**
```json
{
  "reports": [
    {
      "id": 1,
      "hazard": "Banjir",
      "severity": "high",
      "location": "Jalan Pemuda, Semarang",
      "latitude": -6.9932,
      "longitude": 110.4203
    }
  ],
  "total_reports": 42,
  "total_pages": 9,
  "current_page": 1
}
```

---

### `GET /`
Serves the PWA frontend (`static/index.html`).

---

## 11. Key Innovations

**Multimodal Extraction (No STT Pipeline)**
Audio is uploaded directly to Gemini. Transcription and structured data extraction (hazard type, severity, location, description) happen in a single model inference — eliminating fragile Speech-to-Text pipeline dependencies.

**Context-Grounded AI**
GPS coordinates are reverse-geocoded and injected into the Gemini prompt as location context. This prevents hallucinations when the speaker is vague (e.g., *"di sini"* / "right here") by grounding the AI's understanding in the user's actual physical location.

**Audio Quality Gate**
Before calling the AI (which costs API quota), the backend validates every recording using `librosa`:
- Minimum duration: **2 seconds**
- Minimum RMS energy: **0.01**
- Non-silent frame ratio: **> 10%**

This rejects blank, noise-only, or accidental presses without wasting any API calls.

**Noise Reduction Pre-processing**
`noisereduce` cleans the audio before AI analysis, improving transcription accuracy in outdoor conditions (wind, rain, crowd noise).

**Disaster Classification Filter**
The AI returns `is_disaster: true/false` and a `validation` code (`OK | NO_SPEECH | NOT_DISASTER | UNCLEAR | INCOMPLETE_REPORT`). Non-disaster submissions are rejected before database storage.

---

## 12. Technical Limitations & Mitigations

### Network Dependency
**Bottleneck:** The app sends ~500 KB audio payloads to the Gemini API. In a total blackout or 2G-only zone, uploads will time out.

**Mitigation:** Future versions should fall back to a lightweight text-only HTML form when the audio upload times out (Graceful Degradation).

### SQLite Write Concurrency
**Bottleneck:** SQLite locks the entire database file on each write. A sudden surge of concurrent reports (e.g., 500 submissions at the same second during a major earthquake) will cause write-lock failures.

**Mitigation:** Migrate to PostgreSQL for concurrent write handling and add a message queue (RabbitMQ / Redis) to buffer incoming reports.

### Nominatim Rate Limiting
**Bottleneck:** OpenStreetMap's Nominatim is free but enforces a strict **1 request/second** limit. A surge in reports will result in geocoding failures.

**Mitigation:** Self-host a Nominatim instance, or switch to a paid geocoding provider (Google Maps, Mapbox) for production.

### Audio Quality Ceiling
**Bottleneck:** Heavy rain on a cheap smartphone microphone can completely drown out a human voice. `noisereduce` cannot recover signal that was never captured.

**Mitigation:** Add a visual confirmation step (photo upload) to provide a secondary evidence channel when audio quality is too poor.

---

## 13. Future Roadmap

| Feature | Description |
|---|---|
| **Visual Verification** | Allow users to attach a photo alongside the voice note. The multimodal AI cross-references the image (e.g., flood water visible) with the audio to confirm accuracy and severity. |
| **Offline-First PWA** | Enhanced Service Worker implementation: cache the full UI and queue audio reports locally, auto-uploading when connectivity is restored. |
| **Crowd-Sourced Validation** | A "Verification Layer" on the map where other users can click *Konfirmasi* or *Laporkan Palsu* on existing pins to crowd-filter hoaxes. |
| **PostgreSQL Migration** | Replace SQLite with PostgreSQL + a Redis message queue for production-scale concurrent write handling. |
| **Graceful Degradation** | Auto-fallback to a text-only form if the Gemini API is unreachable within a configurable timeout. |