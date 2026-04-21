"""OCR-based text finding for XisWalker composite steps.

Supports two backends:
  - pytesseract: wraps Tesseract OCR (requires separate Tesseract install).
  - ollama: sends a screenshot crop to a local Ollama vision model.
"""

import base64
import difflib
import io
import json
import time
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional

from PIL import ImageGrab


@dataclass
class OcrMatchResult:
    """Result of an OCR text-search operation."""

    found: bool
    x: int = 0       # top-left x of matched text region (absolute screen coords)
    y: int = 0       # top-left y of matched text region
    w: int = 0       # width of matched region
    h: int = 0       # height of matched region
    text: str = ""   # the actual recognised text


# ---------------------------------------------------------------------------
# Pure helper — used by tests
# ---------------------------------------------------------------------------

def fuzzy_ratio(a: str, b: str) -> float:
    """Return SequenceMatcher similarity ratio between two strings (0.0–1.0)."""
    return difflib.SequenceMatcher(None, a, b).ratio()


# ---------------------------------------------------------------------------
# Backend implementations
# ---------------------------------------------------------------------------

def _find_pytesseract(
    target: str,
    screenshot,
    threshold: float,
    case_sensitive: bool,
) -> OcrMatchResult:
    """Search for *target* in *screenshot* using pytesseract word-level OCR.

    Returns an OcrMatchResult. Logs a warning and returns not-found if
    pytesseract is not installed.
    """
    try:
        import pytesseract
    except ImportError:
        print("[OCR] pytesseract not installed — cannot perform OCR search.")
        return OcrMatchResult(found=False)

    data = pytesseract.image_to_data(
        screenshot, output_type=pytesseract.Output.DICT
    )

    best_ratio = 0.0
    best_idx = -1

    for i, word in enumerate(data["text"]):
        if not word.strip():
            continue

        a = target if case_sensitive else target.lower()
        b = word if case_sensitive else word.lower()
        ratio = fuzzy_ratio(a, b)

        if ratio > best_ratio:
            best_ratio = ratio
            best_idx = i

    if best_ratio >= threshold and best_idx >= 0:
        x = data["left"][best_idx]
        y = data["top"][best_idx]
        w = data["width"][best_idx]
        h = data["height"][best_idx]
        return OcrMatchResult(
            found=True, x=x, y=y, w=w, h=h, text=data["text"][best_idx]
        )

    return OcrMatchResult(found=False)


def _clean_ollama_output(text: str) -> str:
    """Strip model-artifact lines and XML tags from raw Ollama OCR output.

    nanonets-ocr-s sometimes echoes its own system-prompt instructions when it
    cannot read text in the image. Filter those lines out so the caller only
    sees genuine OCR content.
    """
    import re as _re
    # Remove XML/HTML-like tags (e.g. <watermark>OFFICIAL COPY</watermark>)
    text = _re.sub(r"<[^>]+>", " ", text)
    # Drop lines that are clearly model-instruction artefacts
    _ARTIFACT_PHRASES = (
        "watermarks should be",
        "wrapped in brackets",
        "ex:",
        "official copy",
    )
    lines = [
        ln for ln in text.splitlines()
        if not any(p in ln.lower() for p in _ARTIFACT_PHRASES)
    ]
    return "\n".join(lines).strip()


def _find_ollama(
    target: str,
    screenshot,
    model: str,
    ollama_url: str,
    roi: Optional[List[int]],
    threshold: float = 0.8,
    case_sensitive: bool = False,
) -> OcrMatchResult:
    """Extract all visible text via an Ollama model, then fuzzy-search for *target*.

    Works with pure OCR models (nanonets-ocr-s) and vision/chat models (llava).
    Since pure OCR models don't return bounding boxes, the click target is the
    centre of the ROI when a match is found.
    """
    try:
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # Empty prompt — lets the model's built-in system prompt drive OCR.
        # Works for nanonets-ocr-s (fine-tuned) and llava (instruction-following).
        payload = json.dumps(
            {
                "model": model,
                "prompt": "",
                "images": [image_b64],
                "stream": False,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{ollama_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        full_text = _clean_ollama_output(body.get("response", "").strip())
        if not full_text:
            return OcrMatchResult(found=False)

        # Python-side fuzzy word matching (same approach as pytesseract backend)
        best_ratio = 0.0
        best_word = ""
        for word in full_text.split():
            a = target if case_sensitive else target.lower()
            b = word if case_sensitive else word.lower()
            ratio = fuzzy_ratio(a, b)
            if ratio > best_ratio:
                best_ratio = ratio
                best_word = word

        if best_ratio >= threshold:
            # Pure OCR models don't return per-word coords — return ROI centre
            cx = (roi[0] + roi[2] // 2) if roi else 0
            cy = (roi[1] + roi[3] // 2) if roi else 0
            rw = roi[2] if roi else 0
            rh = roi[3] if roi else 0
            return OcrMatchResult(found=True, x=cx, y=cy, w=rw, h=rh, text=best_word)

        return OcrMatchResult(found=False)

    except Exception as exc:  # noqa: BLE001
        print(f"[OCR] Ollama error: {exc}")
        return OcrMatchResult(found=False)


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class OcrMatcher:
    """Finds text on screen using OCR (pytesseract or Ollama vision)."""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url

    def find_text(
        self,
        target: str,
        roi: Optional[List[int]] = None,
        threshold: float = 0.8,
        timeout: float = 5.0,
        backend: str = "pytesseract",
        model: str = "llava",
        case_sensitive: bool = False,
    ) -> OcrMatchResult:
        """Search for *target* text on screen, retrying until *timeout* seconds.

        Args:
            target: The text string to locate.
            roi: Optional [x, y, w, h] region to restrict the search.
            threshold: Fuzzy match ratio (0.0–1.0). Used by pytesseract only.
            timeout: Maximum seconds to keep trying.
            backend: "pytesseract" or "ollama".
            model: Ollama model name (ignored when backend="pytesseract").
            case_sensitive: Whether the match is case-sensitive (pytesseract only).

        Returns:
            The first successful OcrMatchResult, or a not-found result when
            the timeout expires.
        """
        deadline = time.time() + timeout

        while time.time() < deadline:
            screenshot = self._grab(roi)

            if backend == "ollama":
                result = _find_ollama(
                    target, screenshot, model, self.ollama_url, roi,
                    threshold, case_sensitive,
                )
            else:
                result = _find_pytesseract(
                    target, screenshot, threshold, case_sensitive
                )

            if result.found:
                return result

            time.sleep(0.5)

        return OcrMatchResult(found=False)

    def _grab(self, roi: Optional[List[int]]):
        """Capture a PIL image of the full screen or the specified ROI."""
        if roi:
            x, y, w, h = roi
            return ImageGrab.grab(bbox=(x, y, x + w, y + h))
        return ImageGrab.grab()

    # -----------------------------------------------------------------------
    # Full-text reading (used by the OCR timer step)
    # -----------------------------------------------------------------------

    def _preprocess_for_ocr(self, img):
        """Upscale, auto-invert (dark-mode) and sharpen *img* for OCR.

        Dark-mode crops (light text on dark background) are inverted so both
        pytesseract and vision models receive the conventional black-on-white
        layout they perform best on.  The image is upscaled 3× and contrast
        is boosted before being returned as an RGB PIL image.
        """
        from PIL import Image, ImageEnhance, ImageOps
        import statistics

        grey = img.convert("L")
        pixels = list(grey.getdata())
        if pixels and statistics.median(pixels) < 128:
            # Light text on dark background → invert to black-on-white
            grey = ImageOps.invert(grey)

        # Upscale 3× for better model accuracy on small crops
        w, h = grey.size
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS  # type: ignore[attr-defined]
        grey = grey.resize((w * 3, h * 3), resample)

        # Boost contrast so faint characters become crisp
        grey = ImageEnhance.Contrast(grey).enhance(2.5)

        return grey.convert("RGB")

    def read_all_text(
        self,
        roi: Optional[List[int]] = None,
        backend: str = "pytesseract",
        model: str = "llava",
    ) -> str:
        """Read and return ALL visible text from the screen (or ROI) as a string.

        Unlike ``find_text``, this does not search for a specific target —
        it returns the full OCR dump, which can then be scanned for timer
        patterns by ``xiswalker.timer_parser``.

        Always saves the preprocessed image to missions/ocr_debug_last.png so
        you can inspect exactly what the OCR model receives.
        """
        screenshot = self._grab(roi)
        processed = self._preprocess_for_ocr(screenshot)
        try:
            from pathlib import Path
            debug_path = Path("missions/ocr_debug_last.png")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            processed.save(str(debug_path))
            print(f"   [Timer OCR] Debug image saved → {debug_path.resolve()}")
        except Exception as _e:
            print(f"   [Timer OCR] Could not save debug image: {_e}")
        if backend == "ollama":
            return self._read_all_ollama(processed, model)
        return self._read_all_pytesseract(processed)

    def _read_all_pytesseract(self, screenshot) -> str:
        try:
            import pytesseract
        except ImportError:
            print("[OCR] pytesseract not installed — cannot read text.")
            return ""
        # PSM 7 = treat image as a single text line (ideal for timer crops)
        return pytesseract.image_to_string(screenshot, config="--psm 7")

    def _read_all_ollama(self, screenshot, model: str) -> str:
        try:
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            payload = json.dumps(
                {
                    "model": model,
                    "prompt": "Read all text in this image exactly as it appears.",
                    "images": [image_b64],
                    "stream": False,
                }
            ).encode("utf-8")

            req = urllib.request.Request(
                f"{self.ollama_url.rstrip('/')}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return _clean_ollama_output(body.get("response", "").strip())

        except Exception as exc:  # noqa: BLE001
            print(f"[OCR] Ollama read_all_text error: {exc}")
            return ""
