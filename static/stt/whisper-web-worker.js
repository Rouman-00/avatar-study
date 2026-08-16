// Module worker running Whisper entirely in the browser via Transformers.js
// (https://github.com/huggingface/transformers.js), the actively maintained
// successor of the library used by the original xenova/whisper-web demo this
// engine is modeled after.
import { pipeline } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.2.0';

// Caches one loaded pipeline per (model, quantized) combination so switching
// back to a previously used setting doesn't re-download/re-init the model.
const pipelineCache = new Map();

async function getPipeline(model, quantized, progress_callback) {
  const key = `${model}::${quantized}`;
  if (!pipelineCache.has(key)) {
    pipelineCache.set(
      key,
      pipeline('automatic-speech-recognition', model, {
        dtype: quantized ? 'q8' : 'fp32',
        progress_callback,
      }),
    );
  }
  return pipelineCache.get(key);
}

function resolveModelName(model, multilingual) {
  const isDistilWhisper = model.startsWith('distil-whisper/');
  // distil-whisper models here are English-only already; every other model
  // needs the ".en" suffix to use its English-only checkpoint.
  if (!isDistilWhisper && !multilingual) {
    return `${model}.en`;
  }
  return model;
}

self.addEventListener('message', async (event) => {
  const { audio, model, multilingual, quantized, subtask, language } = event.data;

  try {
    const modelName = resolveModelName(model, multilingual);
    const isDistilWhisper = modelName.startsWith('distil-whisper/');

    const transcriber = await getPipeline(modelName, quantized, (progress) => {
      self.postMessage(progress);
    });

    const result = await transcriber(audio, {
      language: multilingual && language && language !== 'auto' ? language : null,
      task: multilingual ? subtask : null,
      chunk_length_s: isDistilWhisper ? 20 : 30,
      stride_length_s: isDistilWhisper ? 3 : 5,
      top_k: 0,
      do_sample: false,
    });

    self.postMessage({ status: 'complete', text: result.text.trim() });
  } catch (error) {
    self.postMessage({ status: 'error', message: error?.message || String(error) });
  }
});
