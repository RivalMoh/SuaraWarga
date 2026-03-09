// =============================================================================
// 1. GLOBAL STATE
// =============================================================================

let userCoords = null;
let gpsAvailable = false;
let userMarker = null;
let eventMarkers = [];
let mediaRecorder = null;
let audioChunks = [];
let deferredPrompt = null;

// Recording timer
let recordingStartTime = null;
let recordingTimerInterval = null;
const MIN_RECORDING_TIME = 1.5; // seconds

// =============================================================================
// 2. MAP SETUP
// =============================================================================

const map = L.map('map').setView([-6.9667, 110.4196], 13);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

const userIcon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

const eventIcon = L.icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41]
});

// =============================================================================
// 3. GPS HANDLING
// =============================================================================

function updateGpsStatus(active, text) {
    const statusEl = document.getElementById('gpsStatus');
    const textEl = document.getElementById('gpsText');
    statusEl.className = 'gps-status ' + (active ? 'active' : 'inactive');
    textEl.innerText = text;
    gpsAvailable = active;
}

function setUserMarker(lat, lng, popupText) {
    if (userMarker) {
        map.removeLayer(userMarker);
    }
    userMarker = L.marker([lat, lng], { icon: userIcon })
        .addTo(map)
        .bindPopup(popupText)
        .openPopup();
    userCoords = { lat, lng };
}

if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        position => {
            const lat = position.coords.latitude;
            const lng = position.coords.longitude;
            map.setView([lat, lng], 15);
            setUserMarker(lat, lng, "📍 Lokasi Saya (GPS)");
            updateGpsStatus(true, "GPS Aktif");
            setStatus("GPS aktif. Siap merekam laporan.", "success");
        },
        error => {
            console.log("GPS error:", error.message);
            updateGpsStatus(false, "GPS Tidak Aktif");
            setStatus("GPS tidak aktif. Ketuk peta untuk memilih lokasi.", "warning");
            showMapInstruction(true);
            enableMapClick();
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
} else {
    updateGpsStatus(false, "GPS Tidak Didukung");
    setStatus("GPS tidak didukung. Ketuk peta untuk memilih lokasi.", "warning");
    showMapInstruction(true);
    enableMapClick();
}

// =============================================================================
// 4. MAP CLICK
// =============================================================================

function showMapInstruction(show) {
    document.getElementById('mapInstruction').className = 'map-instruction' + (show ? ' show' : '');
}

function showConfirmButton(show) {
    document.getElementById('confirmLocationBtn').className = show ? 'show' : '';
}

function enableMapClick() {
    map.on('click', function(e) {
        setUserMarker(e.latlng.lat, e.latlng.lng, "📍 Lokasi Dipilih (Manual)");
        showMapInstruction(false);
        showConfirmButton(true);
        setStatus("Lokasi dipilih. Konfirmasi atau ketuk ulang untuk mengubah.", "");
    });
}

document.getElementById('confirmLocationBtn').addEventListener('click', function() {
    if (userCoords) {
        showConfirmButton(false);
        setStatus("Lokasi dikonfirmasi. Siap merekam laporan.", "success");
    }
});

// =============================================================================
// 5. UI HELPERS
// =============================================================================

function setStatus(message, type = "") {
    const statusEl = document.getElementById('status');
    statusEl.innerText = message;
    statusEl.className = type;
}

function showLoading(show) {
    document.getElementById('loading').className = 'loading' + (show ? ' show' : '');
}

function showResult(show) {
    document.getElementById('result').className = 'result-box' + (show ? ' show' : '');
}

function showErrorAlert(show, message = "", hint = "") {
    const alertEl = document.getElementById('errorAlert');
    alertEl.className = 'error-alert' + (show ? ' show' : '');
    if (show) {
        document.getElementById('errorMessage').innerText = message;
        document.getElementById('errorHint').innerText = hint;
    }
}

function showMinTimeWarning(show) {
    document.getElementById('minTimeWarning').className = 'min-time-warning' + (show ? ' show' : '');
}

function resetButton() {
    const btn = document.getElementById('recordBtn');
    btn.innerHTML = '🎤 Tahan untuk Bicara<div class="record-timer" id="recordTimer">0.0s</div>';
    btn.disabled = false;
    btn.classList.remove('recording');
}

function updateRecordingTimer() {
    if (recordingStartTime) {
        const elapsed = (Date.now() - recordingStartTime) / 1000;
        const timerEl = document.getElementById('recordTimer');
        if (timerEl) {
            timerEl.innerText = elapsed.toFixed(1) + 's';
            
            // Change color based on minimum time
            if (elapsed < MIN_RECORDING_TIME) {
                timerEl.style.color = '#f39c12';
            } else {
                timerEl.style.color = '#2ecc71';
            }
        }
    }
}

// =============================================================================
// 6. AUDIO RECORDING
// =============================================================================

const recordBtn = document.getElementById('recordBtn');

navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = event => {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async () => {
            // Check recording duration
            const recordingDuration = (Date.now() - recordingStartTime) / 1000;
            
            if (recordingDuration < MIN_RECORDING_TIME) {
                showMinTimeWarning(true);
                setStatus(`⚠️ Rekaman terlalu pendek (${recordingDuration.toFixed(1)}s). Tahan minimal ${MIN_RECORDING_TIME}s.`, "warning");
                audioChunks = [];
                resetButton();
                return;
            }
            
            showMinTimeWarning(false);
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            await sendReport(audioBlob);
            audioChunks = [];
        };
    })
    .catch(err => {
        setStatus("❌ Tidak dapat mengakses mikrofon: " + err.message, "error");
        recordBtn.disabled = true;
    });

function startRecording() {
    if (!userCoords) {
        setStatus("⚠️ Pilih lokasi di peta terlebih dahulu!", "warning");
        return;
    }
    
    if (mediaRecorder && mediaRecorder.state === "inactive") {
        // Hide previous results/errors
        showResult(false);
        showErrorAlert(false);
        showMinTimeWarning(false);
        
        mediaRecorder.start();
        recordingStartTime = Date.now();
        
        // Start timer
        recordingTimerInterval = setInterval(updateRecordingTimer, 100);
        
        recordBtn.innerHTML = '🛑 Sedang Merekam...<div class="record-timer" id="recordTimer">0.0s</div>';
        recordBtn.classList.add('recording');
        setStatus("🎙️ Bicara sekarang... (tahan minimal 2 detik)", "");
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        // Stop timer
        if (recordingTimerInterval) {
            clearInterval(recordingTimerInterval);
            recordingTimerInterval = null;
        }
        
        mediaRecorder.stop();
        recordBtn.innerHTML = '⏳ Menganalisis...';
        recordBtn.classList.remove('recording');
        recordBtn.disabled = true;
        showLoading(true);
    }
}

// Mouse events
recordBtn.addEventListener('mousedown', startRecording);
recordBtn.addEventListener('mouseup', stopRecording);
recordBtn.addEventListener('mouseleave', function() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        stopRecording();
    }
});

// Touch events
recordBtn.addEventListener('touchstart', function(e) {
    e.preventDefault();
    startRecording();
});
recordBtn.addEventListener('touchend', function(e) {
    e.preventDefault();
    stopRecording();
});

// =============================================================================
// 7. SEND REPORT
// =============================================================================

async function sendReport(audioBlob) {
    const formData = new FormData();
    formData.append("file", audioBlob, "report.webm");
    
    if (userCoords) {
        formData.append("latitude", userCoords.lat);
        formData.append("longitude", userCoords.lng);
    }

    try {
        const response = await fetch('/report', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        // Handle different response types
        if (result.status === "success") {
            displayResult(result.data);
            loadHistory();
        } else if (result.status === "error") {
            handleError(result);
        } else if (!response.ok) {
            throw new Error(result.detail || "Server error");
        }
        
    } catch (error) {
        console.error("Error:", error);
        showErrorAlert(true, "Terjadi kesalahan", error.message);
        setStatus("❌ Error: " + error.message, "error");
    } finally {
        showLoading(false);
        resetButton();
    }
}

function handleError(result) {
    const errorHints = {
        "INVALID_AUDIO": "Pastikan berbicara dengan jelas dan dekat dengan mikrofon.",
        "NO_SPEECH": "Coba rekam ulang dan pastikan berbicara dengan jelas.",
        "NOT_DISASTER": "Aplikasi ini khusus untuk melaporkan bencana atau keadaan darurat.",
        "UNCLEAR": "Coba bicara lebih keras dan pelan-pelan.",
        "INCOMPLETE_REPORT": "Sebutkan jenis bencana seperti: banjir, longsor, kebakaran, dll."
    };
    
    const hint = errorHints[result.error_type] || "Silakan coba lagi.";
    
    showErrorAlert(true, result.message, hint);
    setStatus("⚠️ " + result.message, "warning");
}

// =============================================================================
// 8. DISPLAY RESULT
// =============================================================================

function displayResult(data) {
    setStatus("✅ Laporan berhasil dianalisis!", "success");
    showResult(true);
    showErrorAlert(false);
    
    document.getElementById('resHazard').innerText = "⚠️ " + (data.hazard || "Tidak diketahui");
    
    const severityEl = document.getElementById('resSeverity');
    const severity = (data.severity || "unknown").toLowerCase();
    severityEl.innerText = data.severity || "?";
    severityEl.className = "severity-badge severity-" + severity;
    
    document.getElementById('resLocation').innerText = data.location || "Tidak disebutkan";
    document.getElementById('resDescription').innerText = data.description || "-";
    document.getElementById('resTranscription').innerText = data.transcription || "-";
    
    if (data.coordinates && data.coordinates.lat && data.coordinates.long) {
        addEventMarker(data.coordinates.lat, data.coordinates.long, data.hazard, data.location);
    }
}

function addEventMarker(lat, lng, hazard, location) {
    const marker = L.marker([lat, lng], { icon: eventIcon })
        .addTo(map)
        .bindPopup(`<b>⚠️ ${hazard || "Bencana"}</b><br>📍 ${location || "Lokasi"}`)
        .openPopup();
    eventMarkers.push(marker);
    map.flyTo([lat, lng], 15);
}

// =============================================================================
// 9. LOAD HISTORY
// =============================================================================
let currentPage = 1;
const pageLimit = 5;

async function loadHistory(page = 1) {
    try {
        const response = await fetch(`/api/reports?page=${page}&limit=${pageLimit}`);
        const data = await response.json();
        
        const historyList = document.getElementById('historyList');
        const pagination = document.getElementById('pagination');
        
        if (data.length === 0) {
            historyList.innerHTML = '<p style="color: #999; text-align: center; font-size: 0.9em;">Belum ada laporan</p>';
            pagination.style.display = "none";
            return;
        }

        currentPage = data.page;
        
        // Build history items safely (XSS prevention)
        historyList.innerHTML = '';
        data.reports.forEach(report => {
            const item = document.createElement('div');
            item.className = 'history-item';
            
            const header = document.createElement('div');
            header.className = 'history-item-header';
            
            const hazardSpan = document.createElement('span');
            hazardSpan.className = 'history-hazard';
            hazardSpan.textContent = '⚠️ ' + (report.hazard || 'Bencana');
            
            const severitySpan = document.createElement('span');
            const severity = (report.severity || '').toLowerCase();
            severitySpan.className = 'severity-badge severity-' + severity;
            severitySpan.textContent = report.severity || '?';
            
            header.appendChild(hazardSpan);
            header.appendChild(severitySpan);
            
            const locationDiv = document.createElement('div');
            locationDiv.className = 'history-location';
            locationDiv.textContent = '📍 ' + (report.location || 'Lokasi tidak diketahui');
            
            item.appendChild(header);
            item.appendChild(locationDiv);
            historyList.appendChild(item);
        });
        
        // Update pagination controls
        if (data.total_pages > 1) {
            pagination.style.display = 'flex';
            document.getElementById('pageInfo').textContent = `Hal ${data.page} / ${data.total_pages} (${data.total} laporan)`;
            document.getElementById('prevPage').disabled = (data.page <= 1);
            document.getElementById('nextPage').disabled = (data.page >= data.total_pages);
        } else {
            pagination.style.display = 'none';
        }
        
        // Load markers for all reports on first page only
        if (data.page === 1) {
            eventMarkers.forEach(m => map.removeLayer(m));
            eventMarkers = [];
            
            data.reports.forEach(report => {
                if (report.lat && report.long) {
                    const popupDiv = document.createElement('div');
                    const b = document.createElement('b');
                    b.textContent = '⚠️ ' + (report.hazard || 'Bencana');
                    const br = document.createElement('br');
                    const locText = document.createTextNode('📍 ' + (report.location || 'Lokasi'));
                    popupDiv.appendChild(b);
                    popupDiv.appendChild(br);
                    popupDiv.appendChild(locText);
                    
                    const marker = L.marker([report.lat, report.long], { icon: eventIcon })
                        .addTo(map)
                        .bindPopup(popupDiv);
                    eventMarkers.push(marker);
                }
            });
        }
        
    } catch (error) {
        console.error("Failed to load history:", error);
    }
}

// Pagination button events
document.getElementById('prevPage').addEventListener('click', () => {
    if (currentPage > 1) {
        loadHistory(currentPage - 1);
    }
});

document.getElementById('nextPage').addEventListener('click', () => {
    loadHistory(currentPage + 1);
});

loadHistory(1);

// =============================================================================
// 10. PWA INSTALL
// =============================================================================

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    document.getElementById('installBanner').classList.add('show');
});

document.getElementById('installBtn').addEventListener('click', async () => {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        console.log('Install outcome:', outcome);
        deferredPrompt = null;
        document.getElementById('installBanner').classList.remove('show');
    }
});

document.getElementById('closeBanner').addEventListener('click', () => {
    document.getElementById('installBanner').classList.remove('show');
});

// =============================================================================
// 11. SERVICE WORKER
// =============================================================================

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => console.log('Service Worker registered:', reg.scope))
            .catch(err => console.log('Service Worker registration failed:', err));
    });
}