"""Apple Vision text recognition. macOS only; runs on this machine and sends nothing anywhere.

We call Vision directly (through PyObjC) instead of through ocrmac's helper because
ocrmac cannot turn off Vision's language correction, and language correction rewrites
identifiers: "QQ 12 34 56 C" came back as "QQ 12 C" with it on.
"""

from __future__ import annotations

import io
import math

from PIL import Image

from .types import Line, OcrError

DEFAULT_LANGUAGES = ("en-US",)  # Vision has no en-GB recognition model


def recognize(image: Image.Image, languages: tuple[str, ...] = DEFAULT_LANGUAGES) -> list[Line]:
    """Text lines found in the image, with top-left-origin boxes and confidences, in no particular order."""
    try:
        import objc
        import Vision
        from Foundation import NSData
    except ImportError as exc:  # not macOS, or PyObjC missing
        raise OcrError("Apple Vision is not available (macOS with pyobjc-framework-Vision is required)") from exc

    buf = io.BytesIO()
    image.save(buf, "PNG")
    raw = buf.getvalue()
    with objc.autorelease_pool():
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(False)
        req.setRecognitionLanguages_(list(languages))
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
            NSData.dataWithBytes_length_(raw, len(raw)), None
        )
        ok = handler.performRequests_error_([req], None)
        ok, err = ok if isinstance(ok, tuple) else (ok, None)
        if not ok or err is not None:
            raise OcrError(f"Vision text recognition failed: {err}")
        lines = []
        for obs in req.results() or []:
            candidates = obs.topCandidates_(1)
            if not candidates:
                continue
            cand = candidates[0]
            box = obs.boundingBox()  # normalised, origin at the bottom left
            x0, w = float(box.origin.x), float(box.size.width)
            bottom, h = float(box.origin.y), float(box.size.height)
            top_left, top_right = obs.topLeft(), obs.topRight()
            angle = math.degrees(
                math.atan2((top_right.y - top_left.y) * image.height, (top_right.x - top_left.x) * image.width)
            )
            lines.append(
                Line(
                    text=str(cand.string()),
                    bbox=(x0, 1.0 - bottom - h, x0 + w, 1.0 - bottom),
                    confidence=float(cand.confidence()),
                    angle=angle,
                )
            )
        return lines
