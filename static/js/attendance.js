const video = document.getElementById('attendance-video');
const canvas = document.getElementById('attendance-canvas');
const overlay = document.getElementById('overlay-canvas');
const message = document.getElementById('live-message');
const log = document.getElementById('recognition-log');
const modelStatus = document.getElementById('recognition-model-status');
let stream;
let busy = false;
const cameraSelect = document.getElementById('camera-select');

async function loadCameras() {
    if (!navigator.mediaDevices?.enumerateDevices || !cameraSelect) return;
    const devices = await navigator.mediaDevices.enumerateDevices();
    cameraSelect.innerHTML = '';
    devices.filter((device) => device.kind === 'videoinput').forEach((device, index) => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.textContent = device.label || `Camera ${index + 1}`;
        cameraSelect.appendChild(option);
    });
}

async function startAttendanceCamera(deviceId = '') {
    try {
        if (stream) stream.getTracks().forEach((track) => track.stop());
        stream = await navigator.mediaDevices.getUserMedia({ video: deviceId ? { deviceId: { exact: deviceId }, width: { ideal: 640 } } : { facingMode: 'user', width: { ideal: 640 } }, audio: false });
        video.srcObject = stream;
        await loadCameras();
        message.textContent = 'Scanning for faces...';
        if (!window.attendanceTimer) window.attendanceTimer = window.setInterval(sendFrame, 250);
    } catch (error) {
        message.textContent = 'Camera unavailable. Check browser permission.';
    }
}

function drawFaces(faces, sourceWidth, sourceHeight) {
    overlay.width = video.videoWidth || sourceWidth;
    overlay.height = video.videoHeight || sourceHeight;
    const context = overlay.getContext('2d');
    context.clearRect(0, 0, overlay.width, overlay.height);
    const scaleX = overlay.width / sourceWidth;
    const scaleY = overlay.height / sourceHeight;
    faces.forEach((face) => {
        const [x1, y1, x2, y2] = face.box;
        const x = x1 * scaleX;
        const y = y1 * scaleY;
        const width = (x2 - x1) * scaleX;
        const height = (y2 - y1) * scaleY;
        const known = face.name !== 'Unknown';
        context.strokeStyle = known ? '#d4f36a' : '#ff8a78';
        context.lineWidth = 3;
        context.strokeRect(x, y, width, height);
        context.fillStyle = known ? '#d4f36a' : '#ff8a78';
        context.font = '600 15px Space Grotesk';
        context.fillText(`${face.name}${face.similarity ? ` · ${(face.similarity * 100).toFixed(1)}%` : ''}`, x, Math.max(18, y - 8));
        if (face.quality_flags?.length) {
            context.fillText(`Quality: ${face.quality_flags.join(', ')}`, x, Math.min(overlay.height - 8, y + height + 18));
        }
    });
}

async function sendFrame() {
    if (busy || !video.videoWidth) return;
    busy = true;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    try {
        const response = await fetch(window.ATTENDANCE_ENDPOINT, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image: canvas.toDataURL('image/jpeg', 0.7) }) });
        const contentType = response.headers.get('content-type') || '';
        const result = contentType.includes('application/json') ? await response.json() : { error: `Server returned ${response.status}. Restart the app and try again.` };
        if (modelStatus && result.model_status) modelStatus.textContent = result.model_status;
        if (!response.ok && result.loading) {
            message.textContent = result.error;
            return;
        }
        if (!response.ok) throw new Error(result.error || 'Frame processing failed.');
        message.textContent = 'Scanning for faces...';
        drawFaces(result.faces, canvas.width, canvas.height);
        document.getElementById('present-count').textContent = result.counts.present;
        document.getElementById('absent-count').textContent = result.counts.absent;
        document.getElementById('detected-count').textContent = result.faces.length;
        const recognized = result.faces.filter((face) => face.name !== 'Unknown');
        log.innerHTML = '<p class="eyebrow">RECOGNITION LOG</p>' + (recognized.length ? recognized.map((face) => {
            const state = face.quality_blocked ? 'IMPROVE QUALITY' : (face.attendance_recorded ? (face.new ? 'MARKED' : 'PRESENT') : 'NOT MARKED');
            return `<div class="recognition-item"><span>${face.name}</span><span>${state}</span></div>`;
        }).join('') : '<p class="muted">No registered student detected.</p>');
    } catch (error) {
        message.textContent = error.message;
    } finally {
        busy = false;
    }
}

cameraSelect?.addEventListener('change', () => startAttendanceCamera(cameraSelect.value));

startAttendanceCamera();

const photoForm = document.getElementById('photo-upload-form');
const photoInput = document.getElementById('attendance-photos');
const photoStatus = document.getElementById('photo-upload-status');

function updateCounts(counts) {
    document.getElementById('present-count').textContent = counts.present;
    document.getElementById('absent-count').textContent = counts.absent;
    document.getElementById('total-count').textContent = counts.total;
}

function showPhotoResults(results) {
    const items = [];
    results.forEach((result) => {
        const safeFilename = String(result.filename).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
        if (result.error) {
            items.push(`<div class="recognition-item"><span>${safeFilename}</span><span>ERROR</span></div>`);
            return;
        }
        if (!result.matches.length) {
            items.push(`<div class="recognition-item"><span>${safeFilename}</span><span>NO FACES</span></div>`);
            return;
        }
        result.matches.forEach((match) => {
            const label = match.name === 'Unknown' ? 'Unknown' : `${match.name}${match.new ? ' · MARKED' : ' · PRESENT'}`;
            items.push(`<div class="recognition-item"><span>${safeFilename}: ${label}</span><span>${match.similarity ? `${(match.similarity * 100).toFixed(1)}%` : '--'}</span></div>`);
        });
    });
    log.innerHTML = '<p class="eyebrow">PHOTO RESULTS</p>' + (items.length ? items.join('') : '<p class="muted">No faces found.</p>');
}

photoForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!photoInput.files.length) return;
    const data = new FormData();
    Array.from(photoInput.files).forEach((file) => data.append('photos', file));
    photoStatus.textContent = `Processing ${photoInput.files.length} picture(s)...`;
    photoStatus.className = 'status-box';
    try {
        const response = await fetch(photoForm.dataset.endpoint, { method: 'POST', body: data });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Picture processing failed.');
        updateCounts(result.counts);
        showPhotoResults(result.results);
        const marked = result.results.flatMap((item) => item.matches || []).filter((match) => match.new).length;
        photoStatus.textContent = `${marked} new attendance record(s) marked. Duplicate students were skipped.`;
        photoInput.value = '';
    } catch (error) {
        photoStatus.textContent = error.message;
        photoStatus.className = 'status-box error';
    }
});
