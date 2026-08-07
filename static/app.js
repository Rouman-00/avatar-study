import { TalkingHead } from "talkinghead";
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

let head = null;
let animationMixer = null;
let currentAnimation = null;

const channel = new BroadcastChannel('avatar-control');
const API_URL = 'http://127.0.0.1:8000';

// Einstellungen aus control.html (per BroadcastChannel synchronisiert), z.B.
// fuer die Sprachaufnahme-Buttons hier auf der Avatar-Seite.
let currentTtsVoice = 'en-US-Neural2-A';
let currentSttDevice = 'cpu';
let currentUseLLM = true;

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

    case 'set_llm':
      currentUseLLM = !!payload.enabled;
      console.log('[Avatar] LLM-Modus:', currentUseLLM);
      break;

    case 'set_voice':
      currentTtsVoice = payload.voice;
      console.log('[Avatar] TTS-Stimme:', currentTtsVoice);
      break;

    case 'set_device':
      currentSttDevice = payload.device;
      console.log('[Avatar] STT-Device:', currentSttDevice);
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
  } catch (err) {
    console.error('[Avatar] Fehler beim Sprechen:', err);
  }

  // Fertig-Signal an Steuerung
  channel.postMessage({ type: 'speak_done' });
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


//####### Voice-Aufnahme (Kunden-UI) #######

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
  setVoiceStatus('Aufnahme läuft...');
}

function cancelVoiceRecording() {
  voiceCancelled = true;
  if (voiceRecorder && voiceRecorder.state !== 'inactive') {
    voiceRecorder.stop();
  }
  showRecordingUI(false);
  setVoiceStatus('');
}

function sendVoiceRecording() {
  if (!voiceRecorder || voiceRecorder.state === 'inactive') {
    return;
  }
  voiceCancelled = false;
  showRecordingUI(false);
  voiceRecorder.stop();
}

async function handleVoiceRecording(audioBlob) {
  try {
    setVoiceStatus('Transcribe...');
    const text = await transcribeVoiceAudio(audioBlob);

    if (!text) {
      setVoiceStatus('Kein Text erkannt.');
      return;
    }

    setVoiceStatus('');
    await sendVoiceMessage(text);
  } catch (err) {
    setVoiceStatus(`Fehler: ${err.message}`);
  }
}

async function transcribeVoiceAudio(audioBlob) {
  const formData = new FormData();
  formData.append('audio', audioBlob, 'recording.webm');
  formData.append('device', currentSttDevice);

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

async function sendVoiceMessage(message) {
  const response = await fetch(API_URL + '/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, use_llm: currentUseLLM }),
  });

  if (!response.ok) {
    throw new Error('Server error: ' + response.status);
  }

  const data = await response.json();
  await speak(data.response, { emotion: data.emotion ?? 'neutral', ttsVoice: currentTtsVoice });
}

micBtn.addEventListener('click', () => {
  startVoiceRecording().catch((err) => {
    setVoiceStatus(`Fehler: ${err.message}`);
    showRecordingUI(false);
  });
});

cancelBtn.addEventListener('click', cancelVoiceRecording);
sendBtn.addEventListener('click', sendVoiceRecording);
