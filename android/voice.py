"""Use the desktop reader's Kokoro model and speaker through sherpa-onnx's Android C API."""
import ctypes
from pathlib import Path
import tempfile
from threading import Lock

def renderer(native, private):
    lock=Lock()
    engine=None
    library=None
    def render(text):
        nonlocal engine, library
        if not text.strip() or len(text)>500:
            raise ValueError("Select a passage of up to 500 characters.")
        with lock:
            if not engine:
                library=ctypes.CDLL(str(Path(native)/"libvoice.so"))
                library.voice_init.argtypes=[ctypes.c_char_p]*5
                library.voice_init.restype=ctypes.c_void_p
                library.voice_render.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p]
                model=Path(__file__).with_name("model")
                names=("model.int8.onnx","voices.bin","tokens.txt","espeak-ng-data","lexicon-gb-en.txt")
                engine=library.voice_init(*(str(model/name).encode() for name in names))
                if not engine:
                    raise RuntimeError("Could not open the offline voice.")
            with tempfile.NamedTemporaryFile(dir=private,suffix=".wav") as target:
                if not library.voice_render(engine,text.encode(),target.name.encode()):
                    raise ValueError("This passage contains no speakable text.")
                return target.read()
    return render
