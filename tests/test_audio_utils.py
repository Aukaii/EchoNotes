import numpy as np

from echonotes.audio_utils import stretch_duration


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
