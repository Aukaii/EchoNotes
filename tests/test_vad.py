import numpy as np

from transcrevetexto.vad import SegmentChunker


def silence_frame(n=480):
    return np.zeros(n, dtype=np.float32)


def speech_frame(n=480, amplitude=0.5):
    rng = np.random.default_rng(0)
    return (rng.standard_normal(n) * amplitude).astype(np.float32)


def test_no_segment_during_pure_silence():
    chunker = SegmentChunker(sample_rate=16000, frame_ms=30, silence_ms_to_close_segment=300)
    for _ in range(20):
        assert chunker.push(silence_frame()) is None


def test_segment_emitted_after_speech_then_silence():
    chunker = SegmentChunker(
        sample_rate=16000,
        frame_ms=30,
        silence_ms_to_close_segment=300,
        min_segment_ms=50,
    )
    result = None
    for _ in range(10):
        result = chunker.push(speech_frame())
        assert result is None
    for _ in range(10):
        result = chunker.push(silence_frame())
        if result is not None:
            break
    assert result is not None
    assert result.ndim == 1


def test_short_speech_below_min_duration_is_discarded():
    chunker = SegmentChunker(
        sample_rate=16000,
        frame_ms=30,
        silence_ms_to_close_segment=60,
        min_segment_ms=1000,
    )
    assert chunker.push(speech_frame()) is None
    result = None
    for _ in range(5):
        result = chunker.push(silence_frame())
    assert result is None


def test_flush_remaining_returns_buffered_speech():
    chunker = SegmentChunker(sample_rate=16000, frame_ms=30, min_segment_ms=10)
    chunker.push(speech_frame())
    chunker.push(speech_frame())
    result = chunker.flush_remaining()
    assert result is not None
    assert result.shape[0] == 480 * 2
