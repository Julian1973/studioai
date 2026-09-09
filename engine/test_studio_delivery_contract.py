import pytest
from studio_delivery_contract import require_aligned_timing


def test_upstream_and_audio_must_fit_same_delivery():
    assert require_aligned_timing(30, direction_duration=30, audio_duration=30) == 30
    assert require_aligned_timing(30, audio_duration=24) == 30  # silence padding is safe
    with pytest.raises(ValueError, match='HEAR exceeds'):
        require_aligned_timing(24, audio_duration=30)
    with pytest.raises(ValueError, match='different durations'):
        require_aligned_timing(30, direction_duration=24)


@pytest.mark.parametrize('duration', [float('nan'), float('inf'), 0, -1])
def test_unverifiable_audio_is_not_ready(duration):
    with pytest.raises(ValueError):
        require_aligned_timing(30, audio_duration=duration)
