import { TalkingHead } from "talkinghead";

let head = null;
let animationMixer = null; 
let currentAnimation = null; 
const channel = new BroadcastChannel('avatar-control');

async function initAvatar() {
  const container = document.getElementById('avatar');

  head = new TalkingHead(container, {
    ttsEndpoint: 'http://127.0.0.1:8000/tts',
    //ttsAPIKey: "...",
    //cameraView: "upper",
    ttsLang: 'de-DE',
    ttsVoice: 'de-DE-Standard-A',
    lipsyncModules: ['en', 'de'],
  });

  // laod Avatar
  await head.showAvatar({
    url: 'TalkingHead/avatars/new-avatar.glb',
    body: 'M',
    avatarMood: 'neutral',
    baseline: {
    headRotateX: -0.05,
    eyeBlinkLeft: 0.15,
    eyeBlinkRight: 0.15,
  }
  });

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

    case 'play_animation':
      if (payload.name) {
        playAnimation(payload.name);
      }
      break;

    default:
      console.warn('[Avatar] Unknown message type:', type);
  }
});

async function speak(text, options = {}) {
  if (!text || !head) return;

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
