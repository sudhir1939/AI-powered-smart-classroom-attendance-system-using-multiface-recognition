const form = document.getElementById('student-form');
const video = document.getElementById('registration-video');
const canvas = document.getElementById('registration-canvas');
const startButton = document.getElementById('camera-start');
const captureButton = document.getElementById('capture-sample');
const countLabel = document.getElementById('sample-count');
const progress = document.getElementById('sample-progress');
const statusBox = document.getElementById('registration-status');
const samples = [];
let stream;
let captureTimer;
let capturing = false;
const accountPassword = form?.querySelector('[name="account_password"]');
const sampleTarget = Number(form?.dataset.sampleTarget || 12);
const captureGuide = [
    'Look straight at the camera', 'Keep looking straight', 'Keep looking straight',
    'Turn your face slightly left', 'Turn a little more left', 'Return to center',
    'Turn your face slightly right', 'Turn a little more right', 'Return to center',
    'Tilt your face slightly up', 'Tilt your face slightly down', 'Look straight again'
];

if (accountPassword) {
    accountPassword.required = true;
    accountPassword.closest('label')?.querySelector('small')?.replaceChildren('(minimum 8 characters)');
}

startButton?.addEventListener('click', async () => {
    try {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 640 } }, audio: false });
        video.srcObject = stream;
        captureButton.disabled = false;
        startButton.textContent = 'Camera enabled';
        document.getElementById('camera-message').textContent = 'Preparing guided capture...';
        window.setTimeout(beginGuidedCapture, 1000);
    } catch (error) {
        statusBox.textContent = 'Camera permission was denied or no camera is available.';
        statusBox.className = 'status-box error';
    }
});

function captureOneSample() {
    if (samples.length >= sampleTarget) return;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    samples.push(canvas.toDataURL('image/jpeg', 0.82));
    countLabel.textContent = `${samples.length} / ${sampleTarget} samples`;
    progress.style.width = `${samples.length / sampleTarget * 100}%`;
    document.getElementById('camera-message').textContent = captureGuide[samples.length] || 'Capture complete';
    if (samples.length >= sampleTarget) {
        capturing = false;
        captureButton.disabled = true;
        window.clearInterval(captureTimer);
        statusBox.textContent = 'Guided capture complete. Review the details and save the student.';
    }
}

function beginGuidedCapture() {
    if (capturing || samples.length >= sampleTarget || !stream) return;
    capturing = true;
    captureButton.disabled = true;
    statusBox.textContent = 'Capturing automatically. Follow each direction shown over the camera.';
    document.getElementById('camera-message').textContent = captureGuide[0];
    captureTimer = window.setInterval(captureOneSample, 900);
    captureOneSample();
}

captureButton?.addEventListener('click', beginGuidedCapture);

form?.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (samples.length < sampleTarget) {
        statusBox.textContent = `Capture ${sampleTarget} samples before saving.`;
        statusBox.className = 'status-box error';
        return;
    }
    const data = Object.fromEntries(new FormData(form).entries());
    data.frames = samples;
    data.existing_student_id = form.dataset.existingStudentId || '';
    statusBox.textContent = 'Checking samples and saving embedding...';
    try {
        const response = await fetch(form.dataset.api, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || (result.errors || []).join(' '));
        statusBox.textContent = 'Student registered successfully. Redirecting...';
        if (stream) stream.getTracks().forEach((track) => track.stop());
        window.location.href = '/students';
    } catch (error) {
        statusBox.textContent = error.message;
        statusBox.className = 'status-box error';
    }
});
