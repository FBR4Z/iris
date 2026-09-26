"""Wake word end to end: synthesized speech -> fake microphone -> Vosk -> Listener.

Needs the voice models (Piper faber and the Vosk model) in the models folder, so it
runs on a machine with iris-voz set up, not in CI:

    uv run --no-project --python 3.13 --with vosk --with piper-tts --with soundfile \
        --with numpy --with pytest --with sounddevice pytest voz/tests
    (with PYTHONPATH=voz/src)
"""

from __future__ import annotations

import io
import queue
import threading
import time
import wave

import numpy as np
import pytest

pytest.importorskip("vosk")
piper = pytest.importorskip("piper")
soundfile = pytest.importorskip("soundfile")

from iris_voz import server  # noqa: E402

MODELS = server.DEFAULT_MODELS
if not (MODELS / server.WAKE_MODEL).exists() or not (MODELS / "pt_BR-faber-medium.onnx").exists():
    pytest.skip("modelos de voz não baixados", allow_module_level=True)


class FakeMicrophone(server.Microphone):
    """Plays a clip into the subscribers instead of opening the sound card."""

    def subscribe(self):
        blocks = queue.Queue()
        with self._lock:
            self._subscribers.append(blocks)
        return blocks

    def unsubscribe(self, blocks) -> None:
        with self._lock:
            if blocks in self._subscribers:
                self._subscribers.remove(blocks)

    def play(self, audio: np.ndarray, speed: float = 4.0) -> None:
        for start in range(0, len(audio), self.BLOCK):
            block = audio[start : start + self.BLOCK]
            if len(block) < self.BLOCK:
                block = np.pad(block, (0, self.BLOCK - len(block)))
            self._callback(block.reshape(-1, 1), self.BLOCK, None, None)
            time.sleep(server.LEVEL_INTERVAL / speed)


class FakeWhisper:
    def __init__(self) -> None:
        self.audio: list[np.ndarray] = []

    def transcribe(self, audio, **_):
        self.audio.append(audio)

        class Segment:
            text = "transcrito"

        return [Segment()], None


class FakeSpeaker:
    playing = False
    stopped_at = 0.0


_voice = None


def speech(text: str, before: float = 1.0, after: float = 2.5) -> np.ndarray:
    global _voice
    if _voice is None:
        _voice = piper.PiperVoice.load(str(MODELS / "pt_BR-faber-medium.onnx"))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        _voice.synthesize_wav(text, wav_file)
    buffer.seek(0)
    samples, rate = soundfile.read(buffer, dtype="float32")
    count = int(len(samples) * server.MIC_RATE / rate)
    samples = np.interp(
        np.linspace(0, len(samples), count, endpoint=False), np.arange(len(samples)), samples
    ).astype(np.float32)
    noise = np.random.default_rng(0).normal(0, 0.003, int(server.MIC_RATE * before))
    tail = np.random.default_rng(1).normal(0, 0.003, int(server.MIC_RATE * after))
    return np.concatenate([noise, samples, tail]).astype(np.float32)


@pytest.fixture
def events(monkeypatch):
    seen: list[dict] = []
    monkeypatch.setattr(server, "emit", lambda event, **data: seen.append({"event": event, **data}))
    return seen


def run(text: str, speaker=None) -> tuple[FakeWhisper, FakeMicrophone]:
    microphone = FakeMicrophone()
    listener = server.Listener("base", cuda=False, microphone=microphone)
    whisper = listener._model = FakeWhisper()
    watcher = server.WakeWatcher(MODELS, microphone, listener, speaker or FakeSpeaker())
    watcher.load()
    thread = threading.Thread(target=watcher.run, daemon=True)
    thread.start()
    time.sleep(0.2)
    microphone.play(speech(text))
    deadline = time.monotonic() + 5
    while listener.busy and time.monotonic() < deadline:
        time.sleep(0.05)
    watcher.stop()
    thread.join(2)
    return whisper, microphone


def names(events: list[dict]) -> list[str]:
    return [event["event"] for event in events if event["event"] != "level"]


def test_wake_word_starts_dictation_with_the_word_itself(events):
    whisper, microphone = run("Íris, abre o Gemini.")
    assert names(events) == ["wake", "listening", "listening", "transcript"]
    assert events[-1] == {"event": "transcript", "text": "transcrito", "wake": True}
    # The recording includes the wake word (pre-roll) and the rest of the phrase.
    (audio,) = whisper.audio
    assert len(audio) / server.MIC_RATE > 2.0
    assert not microphone._subscribers


def test_other_speech_is_ignored(events):
    whisper, _ = run("A máquina três parou de novo, chama a manutenção.")
    assert "wake" not in names(events)
    assert not whisper.audio


def test_no_wake_while_iris_is_talking(events):
    speaker = FakeSpeaker()
    speaker.playing = True
    whisper, _ = run("Íris, abre o Gemini.", speaker=speaker)
    assert "wake" not in names(events)
    assert not whisper.audio
