# app/services/stt_service.py
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


"""
STTService (Whisper Local) — Updated
✅ Accepts uploaded audio (webm/wav/mp3/m4a/ogg) from Flask request.files
✅ Saves to a temp file safely
✅ Transcribes using Faster-Whisper (recommended)
✅ Better error + meta reporting
✅ Works well with MediaRecorder audio/webm
✅ Optional: force English with STT_LANGUAGE=en
✅ Optional: tune speed/quality with env vars

Install:
  pip install faster-whisper ctranslate2

System dependency:
  ffmpeg available in PATH (important for webm/ogg/m4a)
"""


@dataclass
class STTMeta:
    engine: str = "faster-whisper"
    model: str = "base"
    language: Optional[str] = None
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None
    duration_seconds: Optional[float] = None
    device: Optional[str] = None
    compute_type: Optional[str] = None
    segments: Optional[int] = None
    warning: Optional[str] = None
    hint: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "engine": self.engine,
            "model": self.model,
            "language": self.language,
            "avg_logprob": self.avg_logprob,
            "no_speech_prob": self.no_speech_prob,
            "duration_seconds": self.duration_seconds,
            "device": self.device,
            "compute_type": self.compute_type,
            "segments": self.segments,
        }
        if self.warning:
            out["warning"] = self.warning
        if self.hint:
            out["hint"] = self.hint
        if self.error:
            out["error"] = self.error
        return out


class STTService:
    """
    Usage:
      transcript, meta = STTService.transcribe(file_storage)

    Env overrides:
      STT_WHISPER_MODEL=base|small|medium|large-v3
      STT_LANGUAGE=en (optional)
      STT_DEVICE=cpu|cuda (optional)
      STT_COMPUTE_TYPE=int8|float16|int8_float16 (optional)
      STT_BEAM_SIZE=1..5 (optional)
      STT_VAD_FILTER=true|false (optional)
      STT_MIN_TRANSCRIPT_CHARS=2 (optional)
    """

    _model = None
    _model_name: Optional[str] = None
    _device: Optional[str] = None
    _compute_type: Optional[str] = None

    # ----------------------------
    # Env helpers
    # ----------------------------
    @staticmethod
    def _cfg(key: str, default: str) -> str:
        return os.getenv(key, default)

    @staticmethod
    def _cfg_bool(key: str, default: bool) -> bool:
        v = (os.getenv(key, "") or "").strip().lower()
        if not v:
            return default
        return v in ("1", "true", "yes", "y", "on")

    @staticmethod
    def _cfg_int(key: str, default: int) -> int:
        try:
            return int((os.getenv(key, "") or "").strip() or default)
        except Exception:
            return default

    # ----------------------------
    # Model loader
    # ----------------------------
    @staticmethod
    def _ensure_model():
        """
        Lazy-load FasterWhisper model once per process.
        """
        if STTService._model is not None:
            return STTService._model

        model_name = STTService._cfg("STT_WHISPER_MODEL", "base")
        device = STTService._cfg("STT_DEVICE", "cpu")
        compute_type = STTService._cfg("STT_COMPUTE_TYPE", "int8")

        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            raise RuntimeError(
                "faster-whisper is not installed. Run:\n"
                "  pip install faster-whisper ctranslate2"
            ) from e

        STTService._model = WhisperModel(model_name, device=device, compute_type=compute_type)
        STTService._model_name = model_name
        STTService._device = device
        STTService._compute_type = compute_type
        return STTService._model

    # ----------------------------
    # File helpers
    # ----------------------------
    @staticmethod
    def _guess_suffix(filename: str, content_type: str) -> str:
        fn = (filename or "").lower()
        ct = (content_type or "").lower()

        for ext in (".webm", ".wav", ".mp3", ".m4a", ".ogg", ".mp4"):
            if fn.endswith(ext):
                return ext

        if "webm" in ct:
            return ".webm"
        if "wav" in ct:
            return ".wav"
        if "mpeg" in ct or "mp3" in ct:
            return ".mp3"
        if "ogg" in ct:
            return ".ogg"
        if "mp4" in ct:
            return ".mp4"
        if "m4a" in ct or "aac" in ct:
            return ".m4a"

        # safest default for browser MediaRecorder
        return ".webm"

    @staticmethod
    def _has_ffmpeg() -> bool:
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def _needs_ffmpeg(content_type: str, filename: str, suffix: str) -> bool:
        ct = (content_type or "").lower()
        fn = (filename or "").lower()
        # formats that often require ffmpeg decoding
        if "webm" in ct or "ogg" in ct or "mp4" in ct or "m4a" in ct:
            return True
        if fn.endswith((".webm", ".ogg", ".mp4", ".m4a")):
            return True
        if suffix in (".webm", ".ogg", ".mp4", ".m4a"):
            return True
        return False

    # ----------------------------
    # Main
    # ----------------------------
    @staticmethod
    def transcribe(file_storage, language: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        file_storage: werkzeug FileStorage (request.files["audio"])
        Returns:
          (transcript, meta_dict)
        """
        if not file_storage:
            return "", STTMeta(engine="faster-whisper", error="No audio file provided").to_dict()

        content_type = (getattr(file_storage, "content_type", "") or "").lower()
        filename = (getattr(file_storage, "filename", "") or "")
        suffix = STTService._guess_suffix(filename=filename, content_type=content_type)

        ffmpeg_ok = STTService._has_ffmpeg()
        needs_ff = STTService._needs_ffmpeg(content_type, filename, suffix)

        # If it needs ffmpeg but ffmpeg is missing, return a clean error now.
        if needs_ff and not ffmpeg_ok:
            meta = STTMeta(
                engine="faster-whisper",
                model=str(STTService._cfg("STT_WHISPER_MODEL", "base")),
                error="ffmpeg not found in PATH (required to decode webm/ogg/m4a/mp4 audio).",
                hint="Install ffmpeg and add it to PATH, then restart terminal/server.",
            ).to_dict()
            return "", meta

        model = STTService._ensure_model()

        lang = language or (os.getenv("STT_LANGUAGE", "").strip() or None)
        beam_size = max(1, min(STTService._cfg_int("STT_BEAM_SIZE", 1), 5))
        vad_filter = STTService._cfg_bool("STT_VAD_FILTER", True)
        min_chars = max(0, STTService._cfg_int("STT_MIN_TRANSCRIPT_CHARS", 2))

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp_path = tmp.name
                file_storage.save(tmp_path)

            segments, info = model.transcribe(
                tmp_path,
                language=lang,
                beam_size=beam_size,
                vad_filter=vad_filter,
            )

            parts = []
            seg_count = 0
            for seg in segments:
                seg_count += 1
                t = (getattr(seg, "text", "") or "").strip()
                if t:
                    parts.append(t)

            transcript = " ".join(parts).strip()

            # avoid false positives for silence
            if len(transcript) < min_chars:
                transcript = ""

            meta_obj = STTMeta(
                engine="faster-whisper",
                model=str(STTService._model_name or "base"),
                device=str(STTService._device or ""),
                compute_type=str(STTService._compute_type or ""),
                language=getattr(info, "language", None),
                avg_logprob=getattr(info, "avg_logprob", None),
                no_speech_prob=getattr(info, "no_speech_prob", None),
                duration_seconds=getattr(info, "duration", None),
                segments=seg_count,
            )

            # non-fatal warning to help debugging
            if needs_ff and ffmpeg_ok:
                meta_obj.warning = "decoded_via_ffmpeg"

            return transcript, meta_obj.to_dict()

        except Exception as e:
            meta_obj = STTMeta(
                engine="faster-whisper",
                model=str(STTService._model_name or "base"),
                device=str(STTService._device or ""),
                compute_type=str(STTService._compute_type or ""),
                error=str(e),
            )
            if needs_ff and not ffmpeg_ok:
                meta_obj.hint = "Install ffmpeg to decode webm/ogg/m4a correctly."
            return "", meta_obj.to_dict()

        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass