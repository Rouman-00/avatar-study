import os
import sys
from importlib import import_module
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Expliziter Pfad statt load_dotenv(): dessen Suche laeuft vom Aufrufer aus
# nach oben und wuerde je nach Startverzeichnis eine andere Datei erwischen.
# Vorlage mit allen Variablen steht in .env.example (versioniert).
load_dotenv(BASE_DIR / ".env")

# Leitlinie fuer diese Datei: in die .env gehoert nur, was geheim ist oder
# sich pro Rechner unterscheidet. Alles, was beeinflusst, was die Probanden
# hoeren und sehen, bleibt hier im Code -- die .env ist gitignored, ihre
# Werte tauchen in keinem Commit auf und waeren spaeter nicht mehr
# rekonstruierbar.

# --- Geheimnisse und Zugaenge (.env) -----------------------------------
HF_TOKEN = os.environ.get("HF_TOKEN", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
# Optionaler Pfad zu einem Google-Service-Account-JSON. Leer = Application
# Default Credentials (gcloud auth application-default login). Relative
# Pfade werden in tts.py gegen BASE_DIR aufgeloest.
GOOGLE_APPLICATION_CREDENTIALS = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

# --- Umgebung (.env) ---------------------------------------------------
# URL-Vorlage fuer die externe Umfrage (Godspeed/METI), z.B.
# "https://survey.example.com/limesurvey/index.php/12345?participant_number={participant_number}".
# Leer = Feature inaktiv (Survey-Tool/Aufbau steht noch nicht final fest).
SURVEY_URL_TEMPLATE = os.environ.get("SURVEY_URL_TEMPLATE", "")

# Ablage der Studiendaten. Ueber die .env umlenkbar, damit Pilot- und
# Testlaeufe nicht in derselben Datei landen wie die echte Erhebung.
_db_path = os.environ.get("STUDY_DB_PATH", "").strip()
DB_PATH = Path(_db_path).expanduser() if _db_path else BASE_DIR / "data" / "study.db"
if not DB_PATH.is_absolute():
    DB_PATH = (BASE_DIR / DB_PATH).resolve()
# --- TTS ---------------------------------------------------------------
# Aktiver TTS-Anbieter beim Serverstart. Umschaltbar zur Laufzeit ueber
# POST /tts/provider (Control-Panel), siehe tts.py. Per .env setzbar, damit
# der Entwicklungsrechner auf "google" starten kann und keine ElevenLabs-
# Credits verbraucht -- welcher Anbieter im Versuch lief, entscheidet
# ohnehin der Versuchsleiter im Control-Panel, nicht dieser Startwert.
TTS_PROVIDER_DEFAULT = os.environ.get("TTS_PROVIDER", "elevenlabs")  # "elevenlabs" | "google"

# Stimmen-Pool Google Cloud TTS. "name" geht 1:1 als voice.name an die API,
# "label" ist nur die Anzeige im Control-Panel.
GOOGLE_TTS_LANGUAGE_CODE = "en-US"
GOOGLE_TTS_VOICES = [
    {"name": "en-US-Neural2-A", "label": "en-US-Neural2-A (m)"},
    {"name": "en-US-Neural2-D", "label": "en-US-Neural2-D (m)"},
    {"name": "en-US-Wavenet-A", "label": "en-US-Wavenet-A (m)"},
    {"name": "en-US-Wavenet-B", "label": "en-US-Wavenet-B (m)"},
    {"name": "en-US-Standard-A", "label": "en-US-Standard-A (m)"},
]
GOOGLE_TTS_VOICE_DEFAULT = GOOGLE_TTS_VOICES[0]["name"]

# ElevenLabs. Der Key steht oben bei den Geheimnissen; die Voice-IDs sind
# nicht vertraulich und stehen hier, damit sie sprechende Labels und
# Kommentare behalten koennen.
# Per .env umbiegbar auf einen lokalen Mock-Server, damit die TTS-Tests
# ohne echte Credits laufen koennen.
ELEVENLABS_API_BASE = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io/v1")

# eleven_turbo_v2_5 waere die schnellere/guenstigere Alternative (geringere
# Latenz, etwas weniger Prosodie-Qualitaet) -- fuer die Studie bleibt es
# vorerst bei multilingual_v2.
ELEVENLABS_MODEL_ID = "eleven_multilingual_v2"  # Alternative: "eleven_turbo_v2_5"

# Nur stability/similarity_boost werden bewusst gesetzt; alles Weitere
# (style, use_speaker_boost, speed) bleibt auf dem Default von ElevenLabs.
ELEVENLABS_VOICE_SETTINGS = {
    "stability": 0.65,
    "similarity_boost": 0.75,
}

# mp3_44100_128 ist der Default der API und wird von decodeAudioData im
# Browser (TalkingHead) direkt verstanden.
ELEVENLABS_OUTPUT_FORMAT = "mp3_44100_128"
ELEVENLABS_TIMEOUT_SECONDS = 30

# Stimmen-Pool ElevenLabs (Premade-Voices). IDs aus dem Voice Lab / der
# Voice Library uebernehmen und hier ergaenzen oder ersetzen.
ELEVENLABS_VOICES = [
    {"id": "21m00Tcm4TlvDq8ikWAM", "label": "Rachel (w, calm)"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "label": "Sarah (w, soft)"},
    {"id": "TxGEqnHWrfWFTfGW9XjX", "label": "Josh (m, deep)"},
    {"id": "pNInz6obpgDQGcFmaJgB", "label": "Adam (m, narration)"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "label": "Daniel (m, news)"},
]
ELEVENLABS_VOICE_DEFAULT = ELEVENLABS_VOICES[0]["id"]

# --- STT ---------------------------------------------------------------
WHISPER_MODEL_MEDIUM = "Systran/faster-whisper-medium"
WHISPER_MODEL_SMALL = "Systran/faster-whisper-small"
WHISPER_MODEL_ID = WHISPER_MODEL_MEDIUM  # Default-Modell, wird beim Start vorgeladen

# Diese drei bestimmen mit, WAS im Transkript steht, und damit die
# Rohdaten der Studie -- deshalb bewusst hier und nicht in der .env.
# Das Control-Panel kann sie pro Aufnahme ueberschreiben (Testbetrieb);
# diese Werte sind der Startzustand.
STT_MODEL_SIZE = "medium"  # "medium" | "small"
STT_BEAM_SIZE = 5
STT_VAD_FILTER = False

LLM_MODEL_ID = "meta-llama/Llama-3.1-8B-Instruct"

# --- CUDA-Setup (nur Windows) REMINDER-------------------------------------------
# faster-whisper laedt sein GPU-Backend (ctranslate2) ueber cuBLAS/cuDNN-DLLs,
# die unter Windows explizit im DLL-Suchpfad liegen muessen. Wo diese DLLs
# liegen, haengt von der Installationsart ab (conda vs. pip) und ist von
# Rechner zu Rechner/Nutzer zu Nutzer unterschiedlich. Statt eines fest
# codierten Pfads (z.B. eines einzelnen Windows-Nutzerprofils) werden hier
# beide ueblichen Orte relativ zur AKTIVEN Python-Umgebung (sys.prefix)
# geprueft, damit es auf jedem conda-Env/Rechner funktioniert.
if sys.platform == "win32":
    # Ohne Windows Developer Mode fehlt Standardnutzern das Recht, Symlinks
    # anzulegen. huggingface_hub nutzt Symlinks im Cache (blobs/ <- snapshots/);
    # ohne dieses Flag schlaegt der Modell-Download mit WinError 1314 fehl.
    # Muss vor dem Import von huggingface_hub/faster_whisper gesetzt werden.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

    def _register_cuda_dll_dirs() -> None:
        candidate_dirs = [
            Path(sys.prefix) / "Library" / "bin",  # conda: cudatoolkit/cudnn (conda-forge)
        ]
        for pkg in ("nvidia.cublas", "nvidia.cudnn"):  # pip: nvidia-cublas-cuXX / nvidia-cudnn-cuXX
            try:
                module = import_module(pkg)
            except ImportError:
                print(f"[cuda-setup] Paket '{pkg}' nicht installiert, uebersprungen.")
                continue
            # Diese Wheels liefern nvidia.cublas/nvidia.cudnn als PEP-420-
            # Namespace-Pakete ohne __init__.py aus -> __file__ ist None,
            # nur __path__ (Namespace-Suchpfad) ist gesetzt.
            if module.__file__:
                pkg_dir = Path(module.__file__).resolve().parent
            else:
                pkg_dir = Path(next(iter(module.__path__))).resolve()
            candidate_dirs.append(pkg_dir / "bin")

        for directory in candidate_dirs:
            if not directory.is_dir():
                print(f"[cuda-setup] Verzeichnis existiert nicht, uebersprungen: {directory}")
                continue

            os.add_dll_directory(str(directory))

            # ctranslate2 (faster-whisper's GPU-Backend) laedt cuBLAS/cuDNN
            # per Delay-Load erst beim ersten echten GPU-Aufruf -- dieser
            # MSVC-Mechanismus sucht ueber die klassische DLL-Suche (PATH),
            # nicht ueber die von add_dll_directory registrierten
            # Verzeichnisse. Deshalb zusaetzlich vorn an PATH anhaengen.
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            if str(directory) not in path_dirs:
                os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")

            print(f"[cuda-setup] DLL-Verzeichnis registriert: {directory}")

    _register_cuda_dll_dirs()


# --- STT-Geraet --------------------------------------------------------
# Muss NACH _register_cuda_dll_dirs() stehen: die Abfrage laedt ctranslate2,
# und das findet seine cuBLAS/cuDNN-DLLs nur, wenn die Suchpfade vorher
# registriert wurden.
#
# Das Geraet ist reine Hardware-Eigenschaft (hat dieser Rechner CUDA?) und
# damit .env-Material -- meist braucht es aber gar keinen Eintrag, weil
# "auto" selbst nachschaut. Nicht ganz folgenlos fuer die Daten: auf cuda
# rechnet faster-whisper mit float16, auf cpu mit int8, wodurch sich
# Transkripte minimal unterscheiden koennen. Deshalb wird das aufgeloeste
# Geraet beim Start geloggt.
def _detect_stt_device() -> str:
    try:
        import ctranslate2

        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception as exc:
        print(f"[stt] CUDA-Erkennung fehlgeschlagen, nutze CPU: {exc}", flush=True)
        return "cpu"


STT_DEVICE = os.environ.get("STT_DEVICE", "auto").strip().lower()
if STT_DEVICE not in ("auto", "cpu", "cuda"):
    print(f"[stt] Unbekanntes STT_DEVICE '{STT_DEVICE}' in der .env, nutze 'auto'.", flush=True)
    STT_DEVICE = "auto"
if STT_DEVICE == "auto":
    STT_DEVICE = _detect_stt_device()
print(f"[stt] Geraet: {STT_DEVICE} | Modell: {STT_MODEL_SIZE} | beam_size: {STT_BEAM_SIZE}", flush=True)
