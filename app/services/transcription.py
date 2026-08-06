# -*- coding: utf-8 -*-
"""Локальное распознавание речи через faster-whisper."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union, TYPE_CHECKING

from app.services.engines import DEFAULT_ENGINE_ID, EnginePreset, engine_label, resolve_engine
from app.services.i18n import t
from app.services.progress import ProgressTracker

if TYPE_CHECKING:
    from app.services.cancellation import CancellationToken


@dataclass
class WordTiming:
    text: str
    start: float
    end: float


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    speech_end: Optional[float] = None
    words: Optional[list[WordTiming]] = None


class TranscriptionError(RuntimeError):
    """Ошибка распознавания речи."""


END_PADDING_SEC = 0.08


def display_end(speech_end: float) -> float:
    """Видимый конец cue: конец речи + короткий padding."""
    return speech_end + END_PADDING_SEC


def _words_from_whisper(seg) -> list[WordTiming]:
    raw = getattr(seg, "words", None) or []
    result: list[WordTiming] = []
    for item in raw:
        text = (getattr(item, "word", None) or "").strip()
        if not text:
            continue
        result.append(
            WordTiming(
                text=text,
                start=float(item.start),
                end=float(item.end),
            )
        )
    return result


def _segment_timing_from_whisper(seg) -> tuple[float, float, float]:
    """Границы сегмента по словам (точнее segment-level timestamps Whisper)."""
    start = float(seg.start)
    speech_end = float(seg.end)
    words = _words_from_whisper(seg)
    if words:
        start = words[0].start
        speech_end = words[-1].end
    return start, display_end(speech_end), speech_end


def _format_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def segments_to_srt(segments: list[Segment]) -> str:
    lines: list[str] = []
    index = 1
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        lines.append(str(index))
        lines.append(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
        lines.append(text)
        lines.append("")
        index += 1
    return "\n".join(lines)


def write_srt(segments: list[Segment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(segments_to_srt(segments), encoding="utf-8")


class WhisperTranscriber:
    """Обёртка над faster-whisper с ленивой загрузкой модели."""

    def __init__(self) -> None:
        self._model = None
        self._model_size: Optional[str] = None
        self._device: Optional[str] = None

    def _load(
        self,
        model_size: str,
        tracker: Optional[ProgressTracker] = None,
        cancel: Optional["CancellationToken"] = None,
    ) -> None:
        if cancel:
            cancel.check()

        if self._model is not None and self._model_size == model_size:
            if tracker:
                tracker.complete("model", t("transcription.model_in_memory"))
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionError(t("transcription.faster_whisper_missing")) from exc

        device = "cpu"
        compute_type = "int8"
        try:
            import ctranslate2

            if ctranslate2.get_cuda_device_count() > 0:
                device = "cuda"
                compute_type = "float16"
        except Exception:
            pass

        if tracker:
            tracker.begin("model", t("transcription.model_prep", model=model_size, device=device))
            tracker.update("model", 0.08, t("transcription.model_prep_short", model=model_size))

        from app.services.model_status import get_model_status

        if not get_model_status(model_size).downloaded:
            if tracker:
                tracker.update("model", 0.15, t("transcription.model_download", model=model_size))
            from faster_whisper.utils import download_model

            try:
                download_model(model_size)
            except Exception as exc:
                raise TranscriptionError(
                    t("transcription.download_failed", model=model_size, error=exc)
                ) from exc
            if cancel:
                cancel.check()
            if tracker:
                tracker.update("model", 0.55, t("transcription.model_downloaded"))

        if tracker:
            tracker.update("model", 0.65, t("transcription.model_loading"))

        if cancel:
            cancel.check()

        try:
            self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        except Exception as exc:
            if device == "cuda":
                if tracker:
                    tracker.update("model", 0.7, t("transcription.cuda_fallback"))
                self._model = WhisperModel(model_size, device="cpu", compute_type="int8")
                device = "cpu"
            else:
                raise TranscriptionError(t("transcription.load_failed", error=exc)) from exc

        self._model_size = model_size
        self._device = device
        if tracker:
            tracker.complete("model", t("transcription.model_ready", model=model_size))

    def transcribe(
        self,
        audio_path: Path,
        engine: Union[str, EnginePreset] = DEFAULT_ENGINE_ID,
        language: str = "en",
        task: str = "transcribe",
        tracker: Optional[ProgressTracker] = None,
        model_size: Optional[str] = None,
        cancel: Optional["CancellationToken"] = None,
    ) -> list[Segment]:
        if isinstance(engine, EnginePreset):
            preset = engine
        else:
            preset = resolve_engine(engine)

        size = model_size or preset.model_size
        self._load(size, tracker=tracker, cancel=cancel)

        whisper_task = "translate" if task == "translate" else "transcribe"
        engine_name = engine_label(preset.id)
        if tracker:
            if whisper_task == "translate":
                tracker.begin("transcribe", t("transcription.translate_start", engine=engine_name))
            else:
                tracker.begin("transcribe", t("transcription.recognize_start", engine=engine_name))

        lang = None if language in ("auto", "", None) else language

        try:
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language=lang,
                task=whisper_task,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                beam_size=preset.beam_size,
                best_of=preset.best_of,
                condition_on_previous_text=True,
                suppress_tokens=[],
                word_timestamps=True,
                hallucination_silence_threshold=2.0,
            )
        except Exception as exc:
            raise TranscriptionError(t("transcription.error", error=exc)) from exc

        duration = getattr(info, "duration", None) or 0.0
        results: list[Segment] = []

        for seg in segments_iter:
            if cancel and cancel.is_cancelled:
                from app.services.cancellation import PipelineCancelledError

                raise PipelineCancelledError(t("pipeline.cancelled"))

            text = (seg.text or "").strip()
            if not text:
                continue
            start, end, speech_end = _segment_timing_from_whisper(seg)
            words = _words_from_whisper(seg)
            results.append(
                Segment(
                    start=start,
                    end=end,
                    text=text,
                    speech_end=speech_end,
                    words=words or None,
                )
            )
            if tracker and duration > 0:
                ratio = min(max(float(seg.end) / duration, 0.0), 1.0)
                pct = int(ratio * 100)
                tracker.update(
                    "transcribe",
                    ratio,
                    t("transcription.progress", pct=pct, count=len(results)),
                )

        if not results:
            raise TranscriptionError(t("transcription.no_speech"))

        if tracker:
            tracker.complete("transcribe", t("transcription.complete", count=len(results)))

        return results
