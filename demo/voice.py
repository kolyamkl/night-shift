# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = [
#   "kokoro>=0.9.4",
#   "soundfile",
#   "numpy",
#   "en_core_web_sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl",
# ]
# ///
"""Draft voiceover: one WAV per scene from demo/scenes.json, with word timings, using Kokoro locally.

    uv run demo/voice.py            # every scene whose text changed since the last run
    uv run demo/voice.py --force    # every scene

Writes demo/public/media/vo/<id>.wav, <id>.json (words with start/end seconds) and durations.json.
A clip is reused while its text and voice are unchanged, so editing one line re-voices only that scene.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent
RATE = 24000

spec = json.loads((ROOT / "scenes.json").read_text())
voice = spec.get("voice", {}).get("kokoro", "af_heart")
speed = spec.get("voice", {}).get("speed", 1.0)
# Names Kokoro would guess wrong, as phonemes: {"MuGuard": "mjˈuːɡɑːd"}. Captions still show the written word.
pronounce = spec.get("voice", {}).get("pronounce", {})


def spoken(text: str) -> str:
    import re
    for word, phonemes in pronounce.items():
        text = re.sub(rf"\b{re.escape(word)}\b", f"[{word}](/{phonemes}/)", text)
    return text
out = ROOT / "public" / "media" / "vo"
out.mkdir(parents=True, exist_ok=True)
force = "--force" in sys.argv

durations_file = out / "durations.json"
durations = json.loads(durations_file.read_text()) if durations_file.exists() else {}

pipeline = None
for scene in spec["scenes"]:
    sid, text = scene["id"], spoken(scene["vo"])
    key = hashlib.sha1(f"{voice}|{speed}|{text}".encode()).hexdigest()[:12]
    wav, words_file = out / f"{sid}.wav", out / f"{sid}.json"
    if not force and wav.exists() and durations.get(sid, {}).get("key") == key:
        continue
    if pipeline is None:
        from kokoro import KPipeline
        pipeline = KPipeline(lang_code=voice[0], repo_id="hexgrad/Kokoro-82M")  # af_/am_ American, bf_/bm_ British
    chunks, words, offset = [], [], 0.0
    for result in pipeline(text, voice=voice, speed=speed):
        audio = result.audio.numpy()
        chunks.append(audio)
        for token in result.tokens or []:
            if token.start_ts is not None and token.end_ts is not None:
                words.append({"w": token.text, "start": round(offset + token.start_ts, 3), "end": round(offset + token.end_ts, 3)})
        offset += len(audio) / RATE
    audio = np.concatenate(chunks)
    # Kokoro comes out around -24 dBFS; bring speech to about -18 dBFS RMS without clipping.
    rms = float(np.sqrt(np.mean(audio**2))) or 1.0
    audio = audio * min(10 ** (-18 / 20) / rms, 0.95 / float(np.max(np.abs(audio)) or 1.0))
    sf.write(wav, audio, RATE)
    words_file.write_text(json.dumps(words))
    durations[sid] = {"seconds": round(len(audio) / RATE, 3), "key": key}
    print(f"{sid}: {durations[sid]['seconds']:.2f}s")

durations_file.write_text(json.dumps(durations, indent=1))
total = sum(durations[s["id"]]["seconds"] for s in spec["scenes"] if s["id"] in durations)
print(f"total voice: {total:.1f}s")
