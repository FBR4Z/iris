"""iris-voz: serviço de voz local da Íris.

Protocolo: um JSON por linha. Comandos chegam pelo stdin, eventos saem pelo stdout.

Comandos:
  {"cmd": "say", "text": str, "cache": bool}   enfileira uma fala
  {"cmd": "stop"}                              para de falar e limpa a fila
  {"cmd": "listen"}                            grava até o silêncio e transcreve
  {"cmd": "cancel"}                            cancela a gravação em andamento
  {"cmd": "quit"}

Eventos:
  {"event": "ready", "tts": str, "stt": str}
  {"event": "speaking", "on": bool}
  {"event": "listening", "on": bool}
  {"event": "level", "value": float}           0..1, enquanto ouve ou fala
  {"event": "transcript", "text": str}
  {"event": "error", "message": str}
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import queue
import site
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

MIC_RATE = 16_000
LEVEL_INTERVAL = 0.05
DEFAULT_MODELS = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "iris-voz" / "models"

MODEL_URLS = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
    "pt_BR-faber-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx",
    "pt_BR-faber-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json",
}
"""Voice model files, fetched on first use. (Whisper models are fetched by faster-whisper.)"""


def ensure_models(models: Path, names: list[str]) -> None:
    """Download any missing model files into `models`."""
    import urllib.request

    models.mkdir(parents=True, exist_ok=True)
    for name in names:
        target = models / name
        if target.exists():
            continue
        log(f"baixando {name}…")
        partial = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(MODEL_URLS[name], partial)
        partial.replace(target)


# --------------------------------------------------------------------------- io

_out_lock = threading.Lock()


def emit(event: str, **data) -> None:
    with _out_lock:
        sys.stdout.write(json.dumps({"event": event, **data}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# ------------------------------------------------------------------------- cuda


def add_cuda_dlls() -> None:
    """On Windows the CUDA DLLs live inside the nvidia-* wheels; make them loadable."""
    for base in site.getsitepackages():
        for path in (Path(base) / "nvidia").glob("*/bin"):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(path))
            os.environ["PATH"] = f"{path}{os.pathsep}{os.environ['PATH']}"


def has_cuda() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


# -------------------------------------------------------------------------- tts


class Speaker:
    """Text-to-speech with a phrase cache, played on a background thread."""

    def __init__(self, engine: str, voice: str, speed: float, models: Path, cuda: bool):
        self.models = models
        self.speed = speed
        self.cuda = cuda
        if engine == "auto":
            engine = "kokoro" if cuda else "piper"
        self.engine = engine
        self.voice = voice if engine == "kokoro" else "pt_BR-faber-medium"
        self._kokoro = None
        self._piper = None
        self._queue: queue.Queue[tuple[str, bool]] = queue.Queue()
        self._stop = threading.Event()
        cache_root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "iris-voz" / "cache"
        self.cache_dir = cache_root / f"{self.engine}-{self.voice}-{self.speed}"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def description(self) -> str:
        device = "gpu" if (self.engine == "kokoro" and self.cuda) else "cpu"
        return f"{self.engine}/{self.voice}/{device}"

    def load(self) -> None:
        if self.engine == "kokoro":
            ensure_models(self.models, ["kokoro-v1.0.onnx", "voices-v1.0.bin"])
        else:
            ensure_models(self.models, [f"{self.voice}.onnx", f"{self.voice}.onnx.json"])
        if self.engine == "kokoro":
            if self.cuda:
                os.environ.setdefault("ONNX_PROVIDER", "CUDAExecutionProvider")
            from kokoro_onnx import Kokoro

            self._kokoro = Kokoro(
                str(self.models / "kokoro-v1.0.onnx"), str(self.models / "voices-v1.0.bin")
            )
            self._kokoro.create("ok", voice=self.voice, lang="pt-br")  # warm-up
        else:
            from piper import PiperVoice

            self._piper = PiperVoice.load(str(self.models / f"{self.voice}.onnx"))

    def synthesize(self, text: str, cache: bool) -> tuple[np.ndarray, int]:
        import soundfile as sf

        cache_path = self.cache_dir / (hashlib.sha1(text.encode()).hexdigest() + ".wav")
        if cache and cache_path.exists():
            samples, rate = sf.read(cache_path, dtype="float32")
            return samples, rate
        if self._kokoro is not None:
            samples, rate = self._kokoro.create(
                text, voice=self.voice, speed=self.speed, lang="pt-br"
            )
        else:
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav_file:
                self._piper.synthesize_wav(text, wav_file)
            buffer.seek(0)
            samples, rate = sf.read(buffer, dtype="float32")
        samples = np.asarray(samples, dtype=np.float32)
        if cache:
            sf.write(cache_path, samples, rate)
        return samples, rate

    def say(self, text: str, cache: bool) -> None:
        self._queue.put((text, cache))

    def stop(self) -> None:
        self._stop.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def run(self) -> None:
        import sounddevice as sd

        while True:
            text, cache = self._queue.get()
            self._stop.clear()
            try:
                samples, rate = self.synthesize(text, cache)
            except Exception as error:
                emit("error", message=f"TTS: {error}")
                continue
            if self._stop.is_set():
                continue
            emit("speaking", on=True)
            block = max(int(rate * LEVEL_INTERVAL), 256)
            try:
                with sd.OutputStream(samplerate=rate, channels=1, dtype="float32") as stream:
                    for start in range(0, len(samples), block):
                        if self._stop.is_set():
                            break
                        chunk = samples[start : start + block]
                        stream.write(chunk.reshape(-1, 1))
                        rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) else 0.0
                        emit("level", value=round(min(rms * 6, 1.0), 3))
            except Exception as error:
                emit("error", message=f"Áudio: {error}")
            emit("level", value=0.0)
            emit("speaking", on=False)


# -------------------------------------------------------------------------- stt


class Listener:
    """Records until the speaker goes quiet, then transcribes with faster-whisper."""

    MAX_SECONDS = 20.0
    NO_SPEECH_SECONDS = 6.0
    END_SILENCE_SECONDS = 1.0

    def __init__(self, model: str, cuda: bool):
        if model == "auto":
            model = "large-v3-turbo" if cuda else "small"
        self.model_name = model
        self.device = "cuda" if cuda else "cpu"
        self.compute = "float16" if cuda else "int8"
        self._model = None
        self._cancel = threading.Event()
        self._busy = threading.Lock()
        self.hint = ""

    @property
    def description(self) -> str:
        return f"{self.model_name}/{self.device}"

    def load(self) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute)
        self._model.transcribe(np.zeros(MIC_RATE, dtype=np.float32), language="pt")

    def cancel(self) -> None:
        self._cancel.set()

    def listen(self) -> None:
        if not self._busy.acquire(blocking=False):
            return
        try:
            self._listen()
        finally:
            self._busy.release()

    def _record(self) -> np.ndarray:
        import sounddevice as sd

        frames: list[np.ndarray] = []
        block = int(MIC_RATE * LEVEL_INTERVAL)
        floor = None
        speech_started = False
        silence = 0.0
        elapsed = 0.0
        with sd.InputStream(samplerate=MIC_RATE, channels=1, dtype="float32", blocksize=block) as stream:
            while not self._cancel.is_set():
                chunk, _ = stream.read(block)
                chunk = chunk[:, 0].copy()
                frames.append(chunk)
                elapsed += LEVEL_INTERVAL
                rms = float(np.sqrt(np.mean(chunk**2)))
                emit("level", value=round(min(rms * 12, 1.0), 3))
                if elapsed <= 0.3:
                    # Calibrate the noise floor on the first moments.
                    floor = rms if floor is None else max(floor, rms)
                    continue
                threshold = max((floor or 0.0) * 2.5, 0.012)
                if rms > threshold:
                    speech_started = True
                    silence = 0.0
                else:
                    silence += LEVEL_INTERVAL
                if speech_started and silence >= self.END_SILENCE_SECONDS:
                    break
                if not speech_started and elapsed >= self.NO_SPEECH_SECONDS:
                    return np.zeros(0, dtype=np.float32)
                if elapsed >= self.MAX_SECONDS:
                    break
        return np.concatenate(frames) if frames else np.zeros(0, dtype=np.float32)

    def _listen(self) -> None:
        self._cancel.clear()
        emit("listening", on=True)
        try:
            audio = self._record()
        except Exception as error:
            emit("error", message=f"Microfone: {error}")
            audio = np.zeros(0, dtype=np.float32)
        finally:
            emit("level", value=0.0)
            emit("listening", on=False)
        if self._cancel.is_set() or not len(audio):
            emit("transcript", text="")
            return
        if self._model is None:
            self.load()
        segments, _ = self._model.transcribe(
            audio,
            language="pt",
            beam_size=1,
            vad_filter=True,
            initial_prompt=self.hint or None,
        )
        emit("transcript", text=" ".join(segment.text.strip() for segment in segments))


# ------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(prog="iris-voz", description=__doc__.splitlines()[0])
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "check"])
    parser.add_argument("--tts", default="auto", choices=["auto", "kokoro", "piper", "off"])
    parser.add_argument("--stt", default="off", help="auto, off ou nome do modelo Whisper")
    parser.add_argument("--voice", default="pf_dora", help="voz do Kokoro")
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--cpu", action="store_true", help="ignora a GPU")
    parser.add_argument("--models", default=os.environ.get("IRIS_VOZ_MODELS", str(DEFAULT_MODELS)))
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    add_cuda_dlls()
    cuda = has_cuda() and not args.cpu

    speaker = None if args.tts == "off" else Speaker(args.tts, args.voice, args.speed, Path(args.models), cuda)
    listener = None if args.stt == "off" else Listener(args.stt, cuda)

    try:
        if speaker is not None:
            speaker.load()
        if listener is not None:
            listener.load()
    except Exception as error:
        emit("error", message=f"Falha ao carregar modelos: {error}")
        sys.exit(1)

    emit(
        "ready",
        tts=speaker.description if speaker else "off",
        stt=listener.description if listener else "off",
    )
    if args.command == "check":
        if speaker is not None:
            speaker.say("Voz da Íris funcionando.", cache=False)
            threading.Thread(target=speaker.run, daemon=True).start()
            time.sleep(4)
        return

    if speaker is not None:
        threading.Thread(target=speaker.run, daemon=True, name="speaker").start()

    for line in sys.stdin:
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        command = message.get("cmd")
        if command == "say" and speaker is not None:
            speaker.say(str(message.get("text", "")), bool(message.get("cache", False)))
        elif command == "stop" and speaker is not None:
            speaker.stop()
        elif command == "listen" and listener is not None:
            if speaker is not None:
                speaker.stop()  # don't transcribe ourselves
            listener.hint = str(message.get("hint", ""))
            threading.Thread(target=listener.listen, daemon=True, name="listener").start()
        elif command == "cancel" and listener is not None:
            listener.cancel()
        elif command == "quit":
            break


if __name__ == "__main__":
    main()
