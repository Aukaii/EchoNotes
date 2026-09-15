import numpy as np

from echonotes.vad import SegmentChunker


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


def const_frame(amplitude, n=480):
    return np.full(n, amplitude, dtype=np.float32)


def test_continuous_speech_force_closes_at_max_duration():
    chunker = SegmentChunker(
        sample_rate=16000,
        frame_ms=30,
        min_segment_ms=10,
        max_segment_ms=300,
    )
    result = None
    for _ in range(10):
        result = chunker.push(speech_frame())
        if result is not None:
            break
    assert result is not None
    assert result.shape[0] > 0


def test_forced_close_cuts_at_quietest_recent_point_not_mid_word():
    # Fala contínua (sem pausa real) atingindo max_segment_ms: um corte
    # arbitrário no fim do buffer partiria uma palavra ao meio, o que
    # confundia demais o Whisper. O corte deve procurar, na janela recente,
    # o frame mais "fraco" (aqui, o índice 5) e cortar logo depois dele.
    chunker = SegmentChunker(
        sample_rate=16000,
        frame_ms=30,
        min_segment_ms=10,
        max_segment_ms=300,
        soft_cut_lookback_ms=300,
    )
    amplitudes = [0.5, 0.5, 0.5, 0.5, 0.5, 0.05, 0.5, 0.5, 0.5, 0.5]
    result = None
    for amp in amplitudes:
        result = chunker.push(const_frame(amp))
        if result is not None:
            break
    assert result is not None
    assert result.shape[0] == 480 * 6

    remainder = chunker.flush_remaining()
    assert remainder is not None
    assert remainder.shape[0] == 480 * 4


def test_flush_remaining_returns_buffered_speech():
    chunker = SegmentChunker(sample_rate=16000, frame_ms=30, min_segment_ms=10)
    chunker.push(speech_frame())
    chunker.push(speech_frame())
    result = chunker.flush_remaining()
    assert result is not None
    assert result.shape[0] == 480 * 2
