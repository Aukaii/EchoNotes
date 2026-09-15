import wave

import numpy as np

from echonotes.audio_utils import save_wav, stretch_duration


def test_factor_one_returns_same_array_unchanged():
    audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    result = stretch_duration(audio, 1.0)
    assert result is audio


def test_factor_two_doubles_length():
    audio = np.linspace(0, 1, 100, dtype=np.float32)
    result = stretch_duration(audio, 2.0)
    assert result.shape[0] == 200


def test_factor_one_point_five():
    audio = np.linspace(0, 1, 100, dtype=np.float32)
    result = stretch_duration(audio, 1.5)
    assert result.shape[0] == 150


def test_empty_array_stays_empty():
    audio = np.array([], dtype=np.float32)
    result = stretch_duration(audio, 1.5)
    assert result.size == 0


def test_save_wav_roundtrip(tmp_path):
    audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
    path = tmp_path / "segmento.wav"
    save_wav(path, audio, sample_rate=16000)

    with wave.open(str(path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == audio.shape[0]


def test_save_wav_clips_out_of_range_values(tmp_path):
    audio = np.array([2.0, -2.0], dtype=np.float32)
    path = tmp_path / "clip.wav"
    save_wav(path, audio, sample_rate=16000)

    with wave.open(str(path), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16)
    assert samples[0] == 32767
    assert samples[1] == -32767
