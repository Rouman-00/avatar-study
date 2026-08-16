import { TalkingHead } from "talkinghead";
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { transcribeInBrowser } from './stt/whisper-web-client.js';

let head = null;
let animationMixer = null;
let currentAnimation = null;

const channel = new BroadcastChannel('avatar-control');
const API_URL = 'http://127.0.0.1:8000';

// Einstellungen aus control.html (per BroadcastChannel synchronisiert), z.B.
// fuer die Sprachaufnahme-Buttons hier auf der Avatar-Seite.
let currentTtsVoice = 'en-US-Neural2-A';
let currentSttEngine = 'server';
let currentSttDevice = 'cpu';
let currentSttModel = 'medium';
let currentBeamSize = 5;
let currentVadFilter = false;

// whisper-web (Browser-STT via Transformers.js) Einstellungen, synchronisiert
// aus control.html. Defaults spiegeln control.html.
let currentWwModel = 'Xenova/whisper-tiny';
let currentWwQuantized = true;
let currentWwMultilingual = false;
let currentWwLanguage = 'auto';
let currentWwSubtask = 'transcribe';

// Aktuell laufende Interview-Session (null = kein Interview aktiv). Wird
// gesetzt, sobald control.html per 'interview_start' ein Interview startet.
let interviewSessionId = null;

async function initAvatar() {
  const container = document.getElementById('avatar');

  head = new TalkingHead(container, {
    ttsEndpoint: 'http://127.0.0.1:8000/tts',
    //ttsAPIKey: "...",
    //cameraView: "upper",
    ttsLang: 'en-US',
    ttsVoice: 'en-US-Neural2-A',
    lipsyncModules: ['en', 'de'],
  });

  // laod Avatar
  await head.showAvatar({
    url: 'TalkingHead/avatars/new-avatar.glb',
    body: 'M',
    avatarMood: 'happy',
    baseline: {
    headRotateX: -0.05,
    eyeBlinkLeft: 0.15,
    eyeBlinkRight: 0.15,
  }
  });

  addSceneObjects();

  // load Animation (optional)
  await loadAnimations();

  console.log('[Avatar] Initialisiert (Avatar + Animationen geladen)');
}

async function loadAnimations() { 
    //FBX-Animationen hier laden, brauch allerdings Three.js FBXLoader, da GLTF-Format keine Animationen unterstützt
  try {
    //const fbxLoader = new FBXLoader();
    //const animations = await fbxLoader.loadAsync('animations/walking.fbx');
    //animationMixer = new THREE.AnimationMixer(head.avatar);
    console.log('[Avatar] Animations loaded');
    } catch (error) {
    console.error('[Avatar] NO Animation available', error);
    }
}

// Listen for messages from control panel

channel.addEventListener('message', async (event) => {
  const { type, payload } = event.data;

  switch (type) {
    case 'speak':
      await speak(payload.text, payload.options);
      break;

    case 'set_lipsync':
      if (head) {
        head.setLipsync?.(payload.enabled);
      }
      console.log('[Avatar] Lippensync:', payload.enabled);
      break;

    case 'set_emotion':
      if (head) {
        head.setMood?.(payload.emotion || 'neutral');
      }
      console.log('[Avatar] Emotion:', payload.emotion);
      break;

    case 'open_door':
      openDoor();
      break;

    case 'walk_to_door':
      walkToDoor();
      break;

    case 'play_animation':
      if (payload.name) {
        playAnimation(payload.name);
      }
      break;

    case 'interview_start':
      await runInterviewStart(payload.sessionId, payload.text);
      break;

    case 'set_voice':
      currentTtsVoice = payload.voice;
      console.log('[Avatar] TTS-Stimme:', currentTtsVoice);
      break;

    case 'set_device':
      currentSttDevice = payload.device;
      console.log('[Avatar] STT-Device:', currentSttDevice);
      break;

    case 'set_model':
      currentSttModel = payload.model;
      console.log('[Avatar] STT-Modell:', currentSttModel);
      break;

    case 'set_beam_size':
      currentBeamSize = payload.beamSize;
      console.log('[Avatar] Beam Size:', currentBeamSize);
      break;

    case 'set_vad_filter':
      currentVadFilter = !!payload.enabled;
      console.log('[Avatar] VAD-Filter:', currentVadFilter);
      break;

    case 'set_stt_engine':
      currentSttEngine = payload.engine;
      console.log('[Avatar] STT-Engine:', currentSttEngine);
      break;

    case 'set_ww_model':
      currentWwModel = payload.model;
      console.log('[Avatar] whisper-web Modell:', currentWwModel);
      break;

    case 'set_ww_quantized':
      currentWwQuantized = !!payload.enabled;
      console.log('[Avatar] whisper-web quantisiert:', currentWwQuantized);
      break;

    case 'set_ww_multilingual':
      currentWwMultilingual = !!payload.enabled;
      console.log('[Avatar] whisper-web mehrsprachig:', currentWwMultilingual);
      break;

    case 'set_ww_language':
      currentWwLanguage = payload.language;
      console.log('[Avatar] whisper-web Sprache:', currentWwLanguage);
      break;

    case 'set_ww_subtask':
      currentWwSubtask = payload.subtask;
      console.log('[Avatar] whisper-web Task:', currentWwSubtask);
      break;

    default:
      console.warn('[Avatar] Unknown message type:', type);
  }
});

async function speak(text, options = {}) {
  if (!text || !head) return;

  setLastResponseText(text);

  try {
    // Emotion setzen, falls vorhanden
    if (options.emotion) {
      head.setMood?.(options.emotion);
    }

    // Avatar spricht mit Lippensync
    head.speakText(text, options);
    console.log('[Avatar] Spricht:', text);

    // head.speakText() kehrt sofort zurueck (Sprache wird ueber eine interne
    // Queue abgespielt) -- hier warten wir, bis head.isSpeaking wieder false
    // ist, damit Aufrufer (z.B. das Interview) wissen, wann der Avatar
    // wirklich fertig gesprochen hat.
    await waitUntilDoneSpeaking();
  } catch (err) {
    console.error('[Avatar] Fehler beim Sprechen:', err);
  }

  // Fertig-Signal an Steuerung
  channel.postMessage({ type: 'speak_done' });
}

function waitUntilDoneSpeaking() {
  return new Promise((resolve) => {
    const check = () => {
      if (!head || !head.isSpeaking) {
        resolve();
      } else {
        setTimeout(check, 150);
      }
    };
    check();
  });
}

function playAnimation(name) {
  // Platzhalter für Animation abspielen
  // Mit FBXLoader: animationMixer.clipAction(animations[name]).play();
  console.log('[Avatar] Animation starten:', name);
}


initAvatar();


//####### Antwort-Panel (letzte AI-Nachricht) #######

const responsePanel = document.getElementById('response-panel');
const responseToggle = document.getElementById('response-toggle');
const responseText = document.getElementById('response-text');

responseToggle.addEventListener('click', () => {
  const expanded = responsePanel.classList.toggle('expanded');
  responseToggle.setAttribute('aria-expanded', String(expanded));
});

function setLastResponseText(text) {
  responseText.textContent = text;
}


//####### Voice-Aufnahme (Interview-Antworten, Kunden-UI) #######

const micBtn = document.getElementById('mic-btn');
const recordingActions = document.getElementById('recording-actions');
const cancelBtn = document.getElementById('cancel-btn');
const sendBtn = document.getElementById('send-btn');
const voiceStatusEl = document.getElementById('voice-status');

let voiceRecorder = null;
let voiceChunks = [];
let voiceCancelled = false;

function setVoiceStatus(text) {
  voiceStatusEl.textContent = text || '';
}

function showRecordingUI(recording) {
  micBtn.classList.toggle('recording', recording);
  micBtn.style.visibility = recording ? 'hidden' : 'visible';
  recordingActions.classList.toggle('visible', recording);
}

// Der Mic-Button darf nur geklickt werden, waehrend ein Interview laeuft UND
// der Avatar gerade nicht spricht bzw. eine vorherige Antwort verarbeitet.
const MIC_STATUS_TEXT = {
  'no-interview': 'Kein Interview aktiv.',
  speaking: 'Der Avatar spricht...',
  processing: 'Verarbeite deine Antwort...',
  ready: 'Bereit fuer deine Antwort.',
};

function setMicState(state) {
  const enabled = state === 'ready';
  micBtn.disabled = !enabled;
  micBtn.classList.toggle('disabled', !enabled);
  setVoiceStatus(MIC_STATUS_TEXT[state]);
}

async function runInterviewStart(sessionId, text) {
  interviewSessionId = sessionId;
  setMicState('speaking');
  await speak(text, { ttsVoice: currentTtsVoice });
  setMicState('ready');
}

async function startVoiceRecording() {
  voiceCancelled = false;
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  voiceRecorder = new MediaRecorder(stream);
  voiceChunks = [];

  voiceRecorder.addEventListener('dataavailable', (event) => {
    if (event.data.size > 0) {
      voiceChunks.push(event.data);
    }
  });

  voiceRecorder.addEventListener('stop', () => {
    stream.getTracks().forEach((track) => track.stop());
    if (voiceCancelled) {
      voiceChunks = [];
      return;
    }
    const audioBlob = new Blob(voiceChunks, { type: 'audio/webm' });
    handleVoiceRecording(audioBlob);
  });

  voiceRecorder.start();
  showRecordingUI(true);
}

function cancelVoiceRecording() {
  voiceCancelled = true;
  if (voiceRecorder && voiceRecorder.state !== 'inactive') {
    voiceRecorder.stop();
  }
  showRecordingUI(false);
  setMicState('ready');
}

function sendVoiceRecording() {
  if (!voiceRecorder || voiceRecorder.state === 'inactive') {
    return;
  }
  voiceCancelled = false;
  showRecordingUI(false);
  setMicState('processing');
  voiceRecorder.stop();
}

async function handleVoiceRecording(audioBlob) {
  try {
    const text = await transcribeVoiceAudio(audioBlob);

    if (!text) {
      setMicState('ready');
      setVoiceStatus('Kein Text erkannt.');
      return;
    }

    channel.postMessage({ type: 'interview_answer_received', payload: { text } });
    await submitInterviewAnswer(text);
  } catch (err) {
    setMicState('ready');
    setVoiceStatus(`Fehler: ${err.message}`);
  }
}

async function transcribeVoiceAudio(audioBlob) {
  if (currentSttEngine === 'whisper-web') {
    return transcribeInBrowser(
      audioBlob,
      {
        model: currentWwModel,
        quantized: currentWwQuantized,
        multilingual: currentWwMultilingual,
        language: currentWwLanguage,
        subtask: currentWwSubtask,
      },
      setVoiceStatus,
    );
  }

  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');
  formData.append('device', currentSttDevice);
  formData.append('model_size', currentSttModel);
  formData.append('beam_size', currentBeamSize);
  formData.append('vad_filter', currentVadFilter);

  const response = await fetch(API_URL + '/api/transcribe', {
    method: 'POST',
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || data.detail || 'Transkription fehlgeschlagen.');
  }
  return data.text;
}

async function submitInterviewAnswer(message) {
  const response = await fetch(API_URL + '/interview/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: interviewSessionId, message }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Server error: ' + response.status);
  }

  channel.postMessage({ type: 'interview_update', payload: { text: data.text, done: data.done } });

  setMicState('speaking');
  await speak(data.text, { ttsVoice: currentTtsVoice });

  if (data.done) {
    interviewSessionId = null;
    setMicState('no-interview');
  } else {
    setMicState('ready');
  }
}

micBtn.addEventListener('click', () => {
  startVoiceRecording().catch((err) => {
    setVoiceStatus(`Fehler: ${err.message}`);
  });
});

cancelBtn.addEventListener('click', cancelVoiceRecording);
sendBtn.addEventListener('click', sendVoiceRecording);

setMicState('no-interview');
