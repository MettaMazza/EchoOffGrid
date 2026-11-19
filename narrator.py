"""Render short passages locally. Weights are loaded only on first playback."""
from array import array
from io import BytesIO
from pathlib import Path
import math
import sys
from threading import Lock
import wave

VOICE_DIR = Path(__file__).with_name("Narrator")
_lock = Lock()
_engine = None


def render(text):
    global _engine
    if not text.strip() or len(text) > 500:
        raise ValueError("Select a passage of up to 500 characters per request.")
    with _lock:
        if _engine is None:
            if not (VOICE_DIR / "model/model.int8.onnx").is_file():
                raise RuntimeError("Install the EchoOffGrid voice package to enable narration.")
            sys.path.insert(0, str(VOICE_DIR / "runtime"))
            import sherpa_onnx as sherpa
            model = VOICE_DIR / "model"
            kokoro = sherpa.OfflineTtsKokoroModelConfig(
                model=str(model/"model.int8.onnx"), voices=str(model/"voices.bin"),
                tokens=str(model/"tokens.txt"), data_dir=str(model/"espeak-ng-data"),
                lexicon=str(model/"lexicon-gb-en.txt"), lang="en-us")
            config = sherpa.OfflineTtsModelConfig(kokoro=kokoro, num_threads=3)
            _engine = sherpa.OfflineTts(sherpa.OfflineTtsConfig(model=config))
        audio = _engine.generate(text, sid=21, speed=1.0)
        samples = array("h", (round(max(-1,min(1,x))*32767) for x in audio.samples))
    if not samples:
        raise ValueError("This passage contains no speakable text.")
    result = BytesIO()
    with wave.open(result, "wb") as wav:
        wav.setparams((1, 2, audio.sample_rate, 0, "NONE", ""))
        wav.writeframes(samples.tobytes())
    return result.getvalue()


def for_playback(payload):
    """Give local speech consistent headroom and a little warmth on small speakers."""
    with wave.open(BytesIO(payload)) as source:
        if source.getsampwidth()!=2 or source.getnchannels()!=1:
            return payload
        rate=source.getframerate()
        samples=array("h",source.readframes(source.getnframes()))
    if not samples:
        return payload
    gain=10**(5/20)
    low=0.0
    alpha=1-math.exp(-2*math.pi*330/rate)
    ceiling=31000
    knee=24000
    for i,sample in enumerate(samples):
        low+=alpha*(sample-low)
        level=gain*(sample+0.14*low)
        magnitude=abs(level)
        if magnitude>knee:
            excess=magnitude-knee
            magnitude=knee+excess/(1+excess/(ceiling-knee))
        samples[i]=round(math.copysign(magnitude,level))
    result=BytesIO()
    with wave.open(result,"wb") as target:
        target.setparams((1,2,rate,0,"NONE",""))
        target.writeframes(samples.tobytes())
    return result.getvalue()
