const channel = new BroadcastChannel('avatar-control');
const API_URL = 'http://127.0.0.1:8000'; 

const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const logElement = document.getElementById('log');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

const toggleLipsync = document.getElementById('toggle-lipsync');
const toggleEmotion = document.getElementById('toggle-emotion');
const toggleLLM = document.getElementById('toggle-llm');
const voiceSelect = document.getElementById('voice-select');



//Condition toggles send immediately their state to backend to the avatar
toggleLipsync.addEventListener('change', () => {
    channel.postMessage({ type: 'set_lipsync', payload: { enabled: toggleLipsync.checked } });
});

toggleEmotion.addEventListener('change', () => {
    channel.postMessage({ type: 'set_emotion', payload: { enabled: toggleEmotion.checked } });
});

voiceSelect.addEventListener('change', () => {
    channel.postMessage({ type: 'set_voice', payload: { voice: voiceSelect.value } });
});

const modelSelect = document.getElementById('model-select');
const beamSizeRange = document.getElementById('beam-size-range');
const beamSizeValueEl = document.getElementById('beam-size-value');
const vadFilterCheckbox = document.getElementById('vad-filter-checkbox');

modelSelect.addEventListener('change', () => {
    channel.postMessage({ type: 'set_model', payload: { model: modelSelect.value } });
});

beamSizeRange.addEventListener('input', () => {
    beamSizeValueEl.textContent = beamSizeRange.value;
    channel.postMessage({ type: 'set_beam_size', payload: { beamSize: Number(beamSizeRange.value) } });
});

vadFilterCheckbox.addEventListener('change', () => {
    channel.postMessage({ type: 'set_vad_filter', payload: { enabled: vadFilterCheckbox.checked } });
});

//Send message (enter key or button click)
sendButton.addEventListener('click', () => {
    sendChatMessage(messageInput.value.trim());
    messageInput.value = '';
});
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendChatMessage(messageInput.value.trim());
        messageInput.value = '';
    }
});

// Gemeinsamer Pfad fuer Tastatur- UND Voice-Eingabe: beide sollen im selben
// Dialog-Log erscheinen und denselben /chat-Aufruf (inkl. speak-Broadcast an
// den Avatar) durchlaufen, damit die Antwort in beiden Faellen auch
// gesprochen wird.
async function sendChatMessage(message) {
    if (!message) {
        return;
    }

    logEntry('user', 'you: ' + message);
    setStatus('loading');

    // Send message to backend
    try {
        const response = await fetch(API_URL + '/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: message, 
                lipsync: toggleLipsync.checked,
                emotion: toggleEmotion.checked,
                use_llm: toggleLLM.checked 
            }),
        });

        // Parse JSON response
        const data = await response.json();

        // Check for HTTP errors
        if (!response.ok) {
            throw new Error(data.detail || 'Server error: ' + response.status);
        }

        logEntry('AI-Agent', 'AI-Agent: ' + data.response);
        setStatus('Response received');

        // broadcast response to avatar for speaking
        channel.postMessage({
            type: 'speak',
            payload: { text: data.response, options: { emotion: data.emotion ?? 'neutral', ttsVoice: voiceSelect.value } },
        })
    }
    catch (error) {
        console.error('Error:', error);
        logEntry('system', 'Error: ' + error.message);
        setStatus('error', 'Error: ' + error.message);
    }
}

//status indicator
function setStatus(state) {
  statusIndicator.className = 'status-indicator';
  if (state === 'connected') {
    statusIndicator.classList.add('connected');
    statusText.textContent = 'connected';
  } else if (state === 'error') {
    statusIndicator.classList.add('error');
    statusText.textContent = 'error';
  } else {
    statusText.textContent = 'loading...';
  }
}

// Logging-function 
function logEntry(sender, message) {
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + sender;
    entry.textContent = `[${timestamp()}] ${message}`;
    logElement.appendChild(entry);
    logElement.scrollTop = logElement.scrollHeight;
}

function logSystem(message) {
    logEntry('system', `[System] ${message}`);

}

function timestamp() {
  return new Date().toLocaleTimeString('de-DE', { hour12: false });
}

//check connection to backend
async function checkConnection() {
  try {
    await fetch(API_URL + '/health');
    setStatus('connected');
  } catch {
    setStatus('error');
  }
}

checkConnection();


//####### Interview #######

const interviewStartButton = document.getElementById('interview-start-button');
const interviewStatusEl = document.getElementById('interview-status');

interviewStartButton.addEventListener('click', async () => {
    interviewStartButton.disabled = true;
    interviewStatusEl.textContent = 'wird gestartet...';

    try {
        const response = await fetch(API_URL + '/interview/start', { method: 'POST' });
        if (!response.ok) {
            throw new Error('Server error: ' + response.status);
        }
        const data = await response.json();

        logEntry('AI-Agent', 'Interview: ' + data.text);
        interviewStatusEl.textContent = 'läuft...';

        channel.postMessage({
            type: 'interview_start',
            payload: { sessionId: data.session_id, text: data.text },
        });
    } catch (error) {
        console.error('Error:', error);
        interviewStatusEl.textContent = 'Fehler: ' + error.message;
        interviewStartButton.disabled = false;
    }
});

// Fortschritt des laufenden Interviews (auf index.html gesteuert) hier nur
// zur Beobachtung im Dialog-Log mitloggen.
channel.addEventListener('message', (event) => {
    const { type, payload } = event.data;

    switch (type) {
        case 'interview_answer_received':
            logEntry('user', 'Teilnehmer: ' + payload.text);
            break;

        case 'interview_update':
            logEntry('AI-Agent', 'Interview: ' + payload.text);
            if (payload.done) {
                interviewStatusEl.textContent = 'beendet';
                interviewStartButton.disabled = false;
            } else {
                interviewStatusEl.textContent = 'läuft...';
            }
            break;
    }
});


//####### Audio #######

const recordBtn = document.getElementById("recordBtn");
const audioFileInput = document.getElementById("audioFileInput");
const gpuCheckbox = document.getElementById("gpuCheckbox");
const audioStatusEl = document.getElementById("audio-status");

gpuCheckbox.addEventListener("change", () => {
    channel.postMessage({ type: 'set_device', payload: { device: gpuCheckbox.checked ? 'cuda' : 'cpu' } });
});

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

// Eigener Name noetig: setStatus(state) oben wird fuer den
// Verbindungsindikator gebraucht und darf hier nicht ueberschrieben werden.
function setAudioStatus(text) {
  audioStatusEl.textContent = text;
}

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  audioChunks = [];

  mediaRecorder.addEventListener("dataavailable", (event) => {
    if (event.data.size > 0) {
      audioChunks.push(event.data);
    }
  });

  mediaRecorder.addEventListener("stop", () => {
    stream.getTracks().forEach((track) => track.stop());
    const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
    processAudioBlob(audioBlob, "recording.webm");
  });

  mediaRecorder.start();
  isRecording = true;
  recordBtn.textContent = "Aufnahme stoppen";
  setAudioStatus("Aufnahme läuft...");
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    recordBtn.textContent = "Aufnahme starten";
  }
}

async function processAudioBlob(audioBlob, filename) {
  try {
    setAudioStatus("Transkribiere...");
    const text = await transcribeAudio(audioBlob, filename);

    if (!text) {
      setAudioStatus("Kein Text erkannt.");
      return;
    }

    setAudioStatus("");
    await sendChatMessage(text);
  } catch (err) {
    setAudioStatus(`Fehler: ${err.message}`);
  }
}

async function transcribeAudio(audioBlob, filename) {
  const formData = new FormData();
  formData.append("audio", audioBlob, filename);
  formData.append("device", gpuCheckbox.checked ? "cuda" : "cpu");
  formData.append("model_size", modelSelect.value);
  formData.append("beam_size", beamSizeRange.value);
  formData.append("vad_filter", vadFilterCheckbox.checked);

  const response = await fetch(API_URL + "/api/transcribe", {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || data.detail || "Transkription fehlgeschlagen.");
  }
  return data.text;
}

recordBtn.addEventListener("click", () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording().catch((err) => setAudioStatus(`Fehler: ${err.message}`));
  }
});

audioFileInput.addEventListener("change", () => {
  const file = audioFileInput.files[0];
  if (!file) {
    return;
  }
  processAudioBlob(file, file.name);
  audioFileInput.value = "";
});
