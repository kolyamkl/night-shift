# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "soundfile"]
# ///
"""8-bit sound effects for the edit, synthesised here so there is nothing to license.

    uv run sfx.py    # writes public/media/sfx/<name>.wav
"""
from pathlib import Path

import numpy as np
import soundfile as sf

RATE = 44100
OUT = Path(__file__).parent / "public" / "media" / "sfx"
OUT.mkdir(parents=True, exist_ok=True)


def t(seconds: float) -> np.ndarray:
    return np.arange(int(RATE * seconds)) / RATE


def square(freq, seconds, duty=0.5):
    f = np.broadcast_to(freq, t(seconds).shape)
    phase = np.cumsum(f) / RATE
    return np.where((phase % 1) < duty, 1.0, -1.0)


def triangle(freq, seconds):
    phase = np.cumsum(np.broadcast_to(freq, t(seconds).shape)) / RATE
    return 2 * np.abs(2 * (phase % 1) - 1) - 1


def env(x, attack=0.004, release=None):
    n = len(x)
    a = np.minimum(1, np.arange(n) / max(1, int(RATE * attack)))
    r = np.linspace(1, 0, n) ** (2 if release is None else release)
    return x * a * r


def note(freq, seconds, wave=square, duty=0.5, release=None):
    x = wave(freq, seconds) if wave is triangle else wave(freq, seconds, duty)
    return env(x, release=release)


def save(name, x, gain=0.35):
    x = x / (np.max(np.abs(x)) or 1) * gain
    sf.write(OUT / f"{name}.wav", x.astype(np.float32), RATE)


# A click: a short upward chirp.
save("blip", note(np.linspace(700, 1400, int(RATE * 0.06)), 0.06, duty=0.25), 0.22)
# Hiding a value: the classic two-note coin.
save("coin", np.concatenate([note(988, 0.07, duty=0.5, release=0.3), note(1319, 0.32, duty=0.5, release=1.5)]), 0.25)
# Pixel wipe: a falling noise sweep.
noise = np.random.default_rng(7).uniform(-1, 1, int(RATE * 0.5))
sweep = noise * square(np.linspace(1800, 200, len(noise)), 0.5, 0.5) * 0.5 + noise * 0.5
save("sweep", env(np.convolve(sweep, np.ones(6) / 6, mode="same"), attack=0.06, release=1.2), 0.16)
# Blocks filling a grid: a fast run of rising ticks.
save("fill", np.concatenate([note(600 + i * 45, 0.035, duty=0.125, release=1) for i in range(30)]), 0.16)
# A stat landing: a short rising arpeggio.
save("powerup", np.concatenate([note(f, 0.06, duty=0.25, release=0.5) for f in (523, 659, 784, 1047, 1319)]), 0.22)
# Approve and the closing card: a little fanfare on square and triangle.
melody = [(523, 0.11), (659, 0.11), (784, 0.11), (1047, 0.42)]
lead = np.concatenate([note(f, d, duty=0.5, release=1.2) for f, d in melody])
bass = np.concatenate([note(f / 2, d, wave=triangle, release=1.0) for f, d in melody])
save("fanfare", lead * 0.7 + bass * 0.5, 0.26)
print("wrote", ", ".join(sorted(p.stem for p in OUT.glob("*.wav"))))
