import os
import sys
from importlib import import_module
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

HF_TOKEN = os.environ.get("HF_TOKEN")
WHISPER_MODEL_ID = "Systran/faster-whisper-medium"
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
