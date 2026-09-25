import { transcribeInBrowser } from '../stt/whisper-web-client.js';
import { LANGUAGES } from '../stt/whisper-web-constants.js';

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



//Condition toggles send immediately their state to backend to the avatar
toggleLipsync.addEventListener('change', () => {
    channel.postMessage({ type: 'set_lipsync', payload: { enabled: toggleLipsync.checked } });
});

toggleEmotion.addEventListener('change', () => {
    channel.postMessage({ type: 'set_emotion', payload: { enabled: toggleEmotion.checked } });
});

//####### Sprachausgabe (TTS): ElevenLabs vs. Google #######

// Der Anbieter ist Server-Zustand (POST /tts/provider) -- TalkingHead
// schickt immer denselben Request-Body an /tts, das Backend entscheidet.
// Hier wird nur die Stimme des jeweils aktiven Anbieters mitgeschickt;
// welche Liste sichtbar ist, haengt am gewaehlten Anbieter.
const elevenlabsVoiceSelect = document.getElementById('elevenlabs-voice-select');
const googleVoiceSelect = document.getElementById('google-voice-select');
const elevenlabsSettings = document.getElementById('tts-elevenlabs-settings');
const googleSettings = document.getElementById('tts-google-settings');
const elevenlabsModelInfo = document.getElementById('elevenlabs-model-info');
const ttsStatusEl = document.getElementById('tts-status');

let currentTtsProvider = 'elevenlabs';
let lastReportedTtsError = null;

// Aktuell gewaehlte Stimme des aktiven Anbieters -- geht als ttsVoice an den
// Avatar und landet im /tts-Request als voice.name.
function activeTtsVoice() {
    return currentTtsProvider === 'elevenlabs'
        ? elevenlabsVoiceSelect.value
        : googleVoiceSelect.value;
}

function setTtsProviderUi(provider) {
    currentTtsProvider = provider;
    elevenlabsSettings.hidden = provider !== 'elevenlabs';
    googleSettings.hidden = provider !== 'google';
    const radio = document.querySelector(`input[name="tts-provider"][value="${provider}"]`);
    if (radio) radio.checked = true;
}

function fillVoiceSelect(select, voices, valueKey, defaultValue) {
    select.replaceChildren();
    voices.forEach((voice) => {
        const option = document.createElement('option');
        option.value = voice[valueKey];
        option.textContent = voice.label;
        option.selected = voice[valueKey] === defaultValue;
        select.appendChild(option);
    });
}

async function loadTtsConfig() {
    try {
        const response = await fetch(API_URL + '/tts/config');
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Server error: ' + response.status);
        }

        fillVoiceSelect(elevenlabsVoiceSelect, data.elevenlabs.voices, 'id', data.elevenlabs.default);
        fillVoiceSelect(googleVoiceSelect, data.google.voices, 'name', data.google.default);
        setTtsProviderUi(data.provider);

        elevenlabsModelInfo.textContent = data.elevenlabs.apiKeyConfigured
            ? `Modell: ${data.elevenlabs.modelId}`
            : `Modell: ${data.elevenlabs.modelId} — ACHTUNG: ELEVENLABS_API_KEY ist nicht gesetzt (.env).`;

        channel.postMessage({ type: 'set_voice', payload: { voice: activeTtsVoice() } });
    } catch (error) {
        ttsStatusEl.textContent = 'TTS-Konfiguration nicht ladbar: ' + error.message;
    }
}

document.querySelectorAll('input[name="tts-provider"]').forEach((radio) => {
    radio.addEventListener('change', async () => {
        if (!radio.checked) return;
        const previous = currentTtsProvider;
        setTtsProviderUi(radio.value);
        ttsStatusEl.textContent = '';

        try {
            const response = await fetch(API_URL + '/tts/provider', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: radio.value }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.detail || 'Server error: ' + response.status);
            }
            lastReportedTtsError = null;
            logSystem('TTS-Anbieter: ' + data.provider);
            channel.postMessage({ type: 'set_voice', payload: { voice: activeTtsVoice() } });
        } catch (error) {
            // Umschalten am Server fehlgeschlagen -> UI zurueckdrehen, sonst
            // zeigt das Panel einen Anbieter an, der gar nicht aktiv ist.
            setTtsProviderUi(previous);
            ttsStatusEl.textContent = 'Anbieterwechsel fehlgeschlagen: ' + error.message;
        }
    });
});

[elevenlabsVoiceSelect, googleVoiceSelect].forEach((select) => {
    select.addEventListener('change', () => {
        channel.postMessage({ type: 'set_voice', payload: { voice: activeTtsVoice() } });
    });
});

// TalkingHead verwirft einen fehlgeschlagenen /tts-Aufruf im Browser
// kommentarlos (der Avatar schweigt dann einfach). Der Fehler passiert
// ausserdem im ANDEREN Fenster (index.html), das Panel kann ihn also nicht
// selbst mitbekommen. Der Server meldet ihn deshalb per Server-Sent Events
// hierher -- eine stehende Verbindung statt einer Anfrage im Sekundentakt.
function applyTtsStatus(data) {
    // Anbieter kann auch von aussen umgestellt worden sein (zweites Panel,
    // Serverneustart) -- Anzeige nachziehen, aber nur bei echtem Unterschied.
    if (data.provider && data.provider !== currentTtsProvider) {
        setTtsProviderUi(data.provider);
        logSystem('TTS-Anbieter (vom Server): ' + data.provider);
    }

    if (!data.lastError) {
        lastReportedTtsError = null;
        ttsStatusEl.textContent = '';
        return;
    }

    const text = `TTS-Fehler (${data.lastError.provider}/${data.lastError.reason}): ${data.lastError.message}`;
    ttsStatusEl.textContent = text;

    // Nach einem Verbindungsabriss schickt der Server den aktuellen Stand
    // erneut -- ohne diesen Vergleich stuende derselbe Fehler mehrfach im Log.
    if (text !== lastReportedTtsError) {
        lastReportedTtsError = text;
        logSystem(text);
    }
}

function connectTtsEvents() {
    const events = new EventSource(API_URL + '/tts/events');

    events.addEventListener('message', (event) => {
        try {
            applyTtsStatus(JSON.parse(event.data));
        } catch (error) {
            console.error('[control] TTS-Event nicht lesbar:', error);
        }
    });

    // Kein eigener Reconnect noetig: EventSource verbindet nach einem Abriss
    // (z.B. uvicorn-Neustart) von selbst wieder. Der Verbindungsindikator
    // oben meldet ohnehin, wenn der Server weg ist.
    events.addEventListener('error', () => {
        console.warn('[control] TTS-Event-Verbindung unterbrochen, verbinde neu...');
    });
}

loadTtsConfig();
connectTtsEvents();

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

//####### STT-Engine: Server (faster-whisper) vs. Browser (whisper-web) #######

const sttServerSettings = document.getElementById('stt-server-settings');
const sttWhisperWebSettings = document.getElementById('stt-whisperweb-settings');
const wwModelSelect = document.getElementById('ww-model-select');
const wwQuantizedCheckbox = document.getElementById('ww-quantized-checkbox');
const wwMultilingualCheckbox = document.getElementById('ww-multilingual-checkbox');
const wwLanguageSelect = document.getElementById('ww-language-select');
const wwSubtaskSelect = document.getElementById('ww-subtask-select');

let currentSttEngine = 'server';

// "auto" = Whisper erkennt die Sprache selbst (kein language-Parameter an die Pipeline)
const languageOption = document.createElement('option');
languageOption.value = 'auto';
languageOption.textContent = 'Auto-Erkennung';
languageOption.selected = true;
wwLanguageSelect.appendChild(languageOption);
Object.entries(LANGUAGES).forEach(([code, name]) => {
    const option = document.createElement('option');
    option.value = code;
    option.textContent = name.charAt(0).toUpperCase() + name.slice(1);
    wwLanguageSelect.appendChild(option);
});

function setSttEngineUi(engine) {
    sttServerSettings.hidden = engine !== 'server';
    sttWhisperWebSettings.hidden = engine !== 'whisper-web';
}

document.querySelectorAll('input[name="stt-engine"]').forEach((radio) => {
    radio.addEventListener('change', () => {
        if (!radio.checked) return;
        currentSttEngine = radio.value;
        setSttEngineUi(currentSttEngine);
        channel.postMessage({ type: 'set_stt_engine', payload: { engine: currentSttEngine } });
    });
});

wwModelSelect.addEventListener('change', () => {
    channel.postMessage({ type: 'set_ww_model', payload: { model: wwModelSelect.value } });
});

wwQuantizedCheckbox.addEventListener('change', () => {
    channel.postMessage({ type: 'set_ww_quantized', payload: { enabled: wwQuantizedCheckbox.checked } });
});

wwMultilingualCheckbox.addEventListener('change', () => {
    wwLanguageSelect.disabled = !wwMultilingualCheckbox.checked;
    wwSubtaskSelect.disabled = !wwMultilingualCheckbox.checked;
    channel.postMessage({ type: 'set_ww_multilingual', payload: { enabled: wwMultilingualCheckbox.checked } });
});

wwLanguageSelect.addEventListener('change', () => {
    channel.postMessage({ type: 'set_ww_language', payload: { language: wwLanguageSelect.value } });
});

wwSubtaskSelect.addEventListener('change', () => {
    channel.postMessage({ type: 'set_ww_subtask', payload: { subtask: wwSubtaskSelect.value } });
});

function getWhisperWebSettings() {
    return {
        model: wwModelSelect.value,
        quantized: wwQuantizedCheckbox.checked,
        multilingual: wwMultilingualCheckbox.checked,
        language: wwLanguageSelect.value,
        subtask: wwSubtaskSelect.value,
    };
}

//Send message (enter key or button click)
sendButton.addEventListener('click', () => {
    handleSendMessage(messageInput.value.trim());
    messageInput.value = '';
});
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        handleSendMessage(messageInput.value.trim());
        messageInput.value = '';
    }
});

// Laeuft gerade ein Interview, soll das Textfeld als Test-Fallback ohne
// Mikro an /interview/answer gehen statt an den generischen /chat-Pfad
// (der bei deaktiviertem LLM-Modus ablehnt und ohnehin nichts mit dem
// Interview zu tun hat).
function handleSendMessage(message) {
    if (activeInterviewSessionId) {
        submitInterviewAnswerFromControl(message);
    } else {
        sendChatMessage(message);
    }
}

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
            payload: { text: data.response, options: { emotion: data.emotion ?? 'neutral', ttsVoice: activeTtsVoice() } },
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
const participantNumberInput = document.getElementById('participant-number-input');

// Gesetzt waehrend ein Interview laeuft (Session-ID des Backends); steuert
// den Text-Fallback in handleSendMessage() oben.
let activeInterviewSessionId = null;

interviewStartButton.addEventListener('click', async () => {
    const participantNumber = participantNumberInput.value.trim();
    if (!participantNumber) {
        interviewStatusEl.textContent = 'Fehler: Teilnehmernummer fehlt.';
        return;
    }

    interviewStartButton.disabled = true;
    interviewStatusEl.textContent = 'wird gestartet...';

    try {
        const response = await fetch(API_URL + '/interview/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ participant_number: participantNumber }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Server error: ' + response.status);
        }

        activeInterviewSessionId = data.session_id;
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

// Test-Fallback: Antwort per Textfeld statt Mikro einreichen, waehrend ein
// Interview laeuft. Spiegelt submitInterviewAnswer() aus app.js, inkl.
// speak-Broadcast, damit der Avatar (falls index.html offen ist) die
// naechste Frage trotzdem spricht.
async function submitInterviewAnswerFromControl(message) {
    if (!message) {
        return;
    }

    logEntry('user', 'you (Interview): ' + message);

    try {
        const response = await fetch(API_URL + '/interview/answer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: activeInterviewSessionId, message }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Server error: ' + response.status);
        }

        // BroadcastChannel liefert nicht an den Sender selbst zurueck -- die
        // eigene UI (Log/Status) hier direkt aktualisieren, nicht ueber den
        // 'interview_update'-Listener unten (der ist fuer den Fall gedacht,
        // dass app.js/index.html die Antwort per Mikro eingereicht hat).
        logEntry('AI-Agent', 'Interview: ' + data.text);
        if (data.survey_url) {
            logEntry('system', 'Umfrage-Link: ' + data.survey_url);
        }
        if (data.done) {
            activeInterviewSessionId = null;
            interviewStatusEl.textContent = 'beendet';
            interviewStartButton.disabled = false;
        } else {
            interviewStatusEl.textContent = 'läuft...';
        }

        // Nur fuer den Avatar bestimmt, damit er (falls index.html offen
        // ist) die naechste Frage auch tatsaechlich spricht.
        channel.postMessage({
            type: 'speak',
            payload: { text: data.text, options: { ttsVoice: activeTtsVoice() } },
        });
    } catch (error) {
        console.error('Error:', error);
        logEntry('system', 'Error: ' + error.message);
    }
}

// Fortschritt des laufenden Interviews (kann von hier oder von index.html
// per Mikro ausgeloest worden sein) hier im Dialog-Log mitloggen.
channel.addEventListener('message', (event) => {
    const { type, payload } = event.data;

    switch (type) {
        case 'interview_answer_received':
            logEntry('user', 'Teilnehmer: ' + payload.text);
            break;

        case 'interview_update':
            logEntry('AI-Agent', 'Interview: ' + payload.text);
            if (payload.survey_url) {
                logEntry('system', 'Umfrage-Link: ' + payload.survey_url);
            }
            if (payload.done) {
                activeInterviewSessionId = null;
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
  if (currentSttEngine === 'whisper-web') {
    return transcribeInBrowser(audioBlob, getWhisperWebSettings(), setAudioStatus);
  }

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
