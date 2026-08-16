// Shared client-side entry point for the browser-based whisper-web STT
// engine. Used by both control.js (experimenter test recorder) and app.js
// (participant mic button) so the audio decode/resample + worker handling
// logic exists exactly once.

const TARGET_SAMPLE_RATE = 16000;

let worker = null;
let activeRequest = null;

function getWorker() {
  if (!worker) {
    worker = new Worker(new URL('./whisper-web-worker.js', import.meta.url), { type: 'module' });
    worker.addEventListener('message', handleWorkerMessage);
    worker.addEventListener('error', (event) => {
      if (activeRequest) {
        activeRequest.reject(new Error(event.message || 'Whisper-Web Worker Fehler.'));
        activeRequest = null;
      }
    });
  }
  return worker;
}

function handleWorkerMessage(event) {
  const data = event.data;
  if (!activeRequest) return;

  switch (data.status) {
    case 'initiate':
      activeRequest.onStatus?.(`Lade Modell: ${data.file}...`);
      break;
    case 'progress':
      activeRequest.onStatus?.(`Lade Modell: ${data.file} (${Math.round(data.progress || 0)}%)`);
      break;
    case 'done':
      activeRequest.onStatus?.(`Modell geladen: ${data.file}`);
      break;
    case 'complete':
      activeRequest.resolve(data.text);
      activeRequest = null;
      break;
    case 'error':
      activeRequest.reject(new Error(data.message || 'Transkription fehlgeschlagen.'));
      activeRequest = null;
      break;
  }
}

// Decodes an arbitrary audio blob (e.g. webm/opus from MediaRecorder) and
// downmixes/resamples it to mono 16kHz, the format Whisper expects.
async function blobToFloat32Audio(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const decodeCtx = new AudioContext();
  let decoded;
  try {
    decoded = await decodeCtx.decodeAudioData(arrayBuffer);
  } finally {
    await decodeCtx.close();
  }

  const targetLength = Math.ceil(decoded.duration * TARGET_SAMPLE_RATE);
  const offlineCtx = new OfflineAudioContext(1, targetLength, TARGET_SAMPLE_RATE);
  const source = offlineCtx.createBufferSource();
  source.buffer = decoded;
  source.connect(offlineCtx.destination);
  source.start(0);
  const resampled = await offlineCtx.startRendering();
  return resampled.getChannelData(0);
}

/**
 * Transcribes an audio blob entirely in the browser via whisper-web.
 * @param {Blob} audioBlob Recorded/uploaded audio.
 * @param {{model: string, multilingual: boolean, quantized: boolean, subtask: string, language: string}} settings
 * @param {(text: string) => void} [onStatus] Progress callback for UI status text.
 * @returns {Promise<string>} Transcribed text.
 */
export function transcribeInBrowser(audioBlob, settings, onStatus) {
  return new Promise((resolve, reject) => {
    if (activeRequest) {
      reject(new Error('Es läuft bereits eine Browser-Transkription.'));
      return;
    }

    (async () => {
      try {
        onStatus?.('Audio wird aufbereitet...');
        const audio = await blobToFloat32Audio(audioBlob);

        activeRequest = { resolve, reject, onStatus };
        onStatus?.('Transkribiere (Browser)...');

        getWorker().postMessage(
          {
            audio,
            model: settings.model,
            multilingual: !!settings.multilingual,
            quantized: !!settings.quantized,
            subtask: settings.subtask,
            language: settings.language,
          },
          [audio.buffer],
        );
      } catch (err) {
        activeRequest = null;
        reject(err);
      }
    })();
  });
}
