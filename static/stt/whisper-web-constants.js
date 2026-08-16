// Shared constants for the browser-side whisper-web STT engine
// (https://github.com/xenova/whisper-web), ported to run on
// @huggingface/transformers instead of the original @xenova/transformers.

// Curated subset of the original whisper-web model list. "medium" and
// "distil-large-v2" are intentionally left out: they are too slow to load
// and run in-browser (WASM only, no WebGPU) for a ~20 min study session.
export const MODELS = {
  'Xenova/whisper-tiny': { label: 'tiny', sizeHint: '~75MB / ~41MB quantized' },
  'Xenova/whisper-base': { label: 'base', sizeHint: '~145MB / ~77MB quantized' },
  'Xenova/whisper-small': { label: 'small', sizeHint: '~484MB / ~249MB quantized' },
  'distil-whisper/distil-medium.en': { label: 'distil-medium.en (nur Englisch)', sizeHint: '~789MB / ~402MB quantized' },
};

export const DEFAULT_MODEL = 'Xenova/whisper-tiny';

// Canonical Whisper language table (code -> English name), same set Whisper
// itself was trained on. Used for the "Sprache" dropdown when "Mehrsprachig"
// is enabled.
export const LANGUAGES = {
  en: 'english', zh: 'chinese', de: 'german', es: 'spanish', ru: 'russian',
  ko: 'korean', fr: 'french', ja: 'japanese', pt: 'portuguese', tr: 'turkish',
  pl: 'polish', ca: 'catalan', nl: 'dutch', ar: 'arabic', sv: 'swedish',
  it: 'italian', id: 'indonesian', hi: 'hindi', fi: 'finnish', vi: 'vietnamese',
  he: 'hebrew', uk: 'ukrainian', el: 'greek', ms: 'malay', cs: 'czech',
  ro: 'romanian', da: 'danish', hu: 'hungarian', ta: 'tamil', no: 'norwegian',
  th: 'thai', ur: 'urdu', hr: 'croatian', bg: 'bulgarian', lt: 'lithuanian',
  la: 'latin', mi: 'maori', ml: 'malayalam', cy: 'welsh', sk: 'slovak',
  te: 'telugu', fa: 'persian', lv: 'latvian', bn: 'bengali', sr: 'serbian',
  az: 'azerbaijani', sl: 'slovenian', kn: 'kannada', et: 'estonian', mk: 'macedonian',
  br: 'breton', eu: 'basque', is: 'icelandic', hy: 'armenian', ne: 'nepali',
  mn: 'mongolian', bs: 'bosnian', kk: 'kazakh', sq: 'albanian', sw: 'swahili',
  gl: 'galician', mr: 'marathi', pa: 'punjabi', si: 'sinhala', km: 'khmer',
  sn: 'shona', yo: 'yoruba', so: 'somali', af: 'afrikaans', oc: 'occitan',
  ka: 'georgian', be: 'belarusian', tg: 'tajik', sd: 'sindhi', gu: 'gujarati',
  am: 'amharic', yi: 'yiddish', lo: 'lao', uz: 'uzbek', fo: 'faroese',
  ht: 'haitian creole', ps: 'pashto', tk: 'turkmen', nn: 'nynorsk', mt: 'maltese',
  sa: 'sanskrit', lb: 'luxembourgish', my: 'myanmar', bo: 'tibetan', tl: 'tagalog',
  mg: 'malagasy', as: 'assamese', tt: 'tatar', haw: 'hawaiian', ln: 'lingala',
  ha: 'hausa', ba: 'bashkir', jw: 'javanese', su: 'sundanese', yue: 'cantonese',
};

export const DEFAULT_LANGUAGE = 'en';
export const DEFAULT_SUBTASK = 'transcribe';
