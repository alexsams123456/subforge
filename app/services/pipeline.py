# -*- coding: utf-8 -*-
"""Оркестрация: аудио → Whisper → вшивание субтитров."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from app.services import ffmpeg_service
from app.services.cancellation import CancellationToken, PipelineCancelledError
from app.services.engines import DEFAULT_ENGINE_ID, resolve_engine
from app.services.ffmpeg_service import FFmpegError, NoAudioStreamError
from app.services.i18n import t
from app.services.progress import ProgressSnapshot, ProgressTracker
from app.services.diarization import DiarizationError, assign_speakers
from app.services.languages import validate_language_pair, whisper_task
from app.services.non_speech_filter import filter_non_speech_segments
from app.services.subtitle_format import DEFAULT_MAX_LINES, format_subtitles
from app.services.subtitle_timing import normalize_subtitle_timing
from app.services.transcription import TranscriptionError, WhisperTranscriber, write_srt


class PipelineError(RuntimeError):
    """Ошибка пайплайна обработки."""


ProgressCallback = Optional[Callable[[ProgressSnapshot], None]]


@dataclass
class PipelineResult:
    output_path: Path
    segment_count: int


class SubtitlePipeline:
    def __init__(self) -> None:
        self._transcriber = WhisperTranscriber()

    def process(
        self,
        input_video: Path,
        output_video: Path,
        engine: str = DEFAULT_ENGINE_ID,
        speech_language: str = "en",
        subtitle_language: str = "en",
        max_subtitle_lines: int = DEFAULT_MAX_LINES,
        separate_speakers: bool = True,
        hide_non_speech: bool = False,
        audio_source: Optional[Path] = None,
        on_progress: ProgressCallback = None,
        cancel: Optional[CancellationToken] = None,
    ) -> PipelineResult:
        input_video = Path(input_video)
        output_video = Path(output_video)

        if not input_video.is_file():
            raise PipelineError(t("pipeline.file_not_found", path=input_video))

        if output_video.suffix.lower() != ".mp4":
            output_video = output_video.with_suffix(".mp4")

        pair_error = validate_language_pair(speech_language, subtitle_language)
        if pair_error:
            raise PipelineError(pair_error)

        tracker = ProgressTracker(on_progress)

        temp_dir = Path(tempfile.mkdtemp(prefix="subforge_"))
        audio_path = temp_dir / "audio.wav"
        srt_path = temp_dir / "subs.srt"

        try:
            if cancel:
                cancel.check()

            tracker.begin("ffmpeg", t("pipeline.ffmpeg_check"))
            try:
                ffmpeg_path = ffmpeg_service.check_ffmpeg()
            except FFmpegError as exc:
                raise PipelineError(str(exc)) from exc
            tracker.complete("ffmpeg", t("pipeline.ffmpeg_found", name=Path(ffmpeg_path).name))

            if cancel:
                cancel.check()

            tracker.begin("extract", t("pipeline.extract_start"))

            def extract_progress(ratio: float) -> None:
                pct = int(ratio * 100)
                tracker.update("extract", ratio, t("pipeline.extract_progress", pct=pct))

            audio_input = Path(audio_source) if audio_source else input_video
            if audio_input != input_video:
                tracker.update(
                    "extract",
                    0.0,
                    t("pipeline.audio_from_other", name=audio_input.name),
                )

            try:
                ffmpeg_service.extract_audio(
                    audio_input,
                    audio_path,
                    on_progress=extract_progress,
                    cancel=cancel,
                )
            except PipelineCancelledError:
                raise
            except NoAudioStreamError as exc:
                raise PipelineError(str(exc)) from exc
            except FFmpegError as exc:
                raise PipelineError(str(exc)) from exc
            tracker.complete("extract", t("pipeline.extract_done"))

            if cancel:
                cancel.check()

            preset = resolve_engine(engine)
            try:
                segments = self._transcriber.transcribe(
                    audio_path,
                    engine=preset,
                    language=speech_language,
                    task=whisper_task(speech_language, subtitle_language),
                    tracker=tracker,
                    cancel=cancel,
                )
            except PipelineCancelledError:
                raise
            except TranscriptionError as exc:
                raise PipelineError(str(exc)) from exc

            if cancel:
                cancel.check()

            if hide_non_speech:
                segments = filter_non_speech_segments(segments)
                if not segments:
                    raise PipelineError(t("transcription.no_speech"))

            if separate_speakers:
                try:
                    segments = assign_speakers(
                        segments,
                        audio_path,
                        tracker=tracker,
                        cancel=cancel,
                    )
                except PipelineCancelledError:
                    raise
                except DiarizationError as exc:
                    raise PipelineError(str(exc)) from exc
            else:
                tracker.begin("diarize", t("stage.diarize"))
                tracker.complete("diarize", t("pipeline.diarize_skip"))

            if cancel:
                cancel.check()

            tracker.begin("srt", t("pipeline.srt_start"))
            display_segments = format_subtitles(
                segments,
                max_lines=max_subtitle_lines,
                language=subtitle_language,
            )
            display_segments = normalize_subtitle_timing(display_segments)
            write_srt(display_segments, srt_path)
            tracker.complete(
                "srt",
                t(
                    "pipeline.srt_done",
                    count=len(display_segments),
                    max_lines=max_subtitle_lines,
                ),
            )

            if cancel:
                cancel.check()

            tracker.begin("mux", t("pipeline.mux_start"))

            def mux_progress(ratio: float) -> None:
                pct = int(ratio * 100)
                tracker.update("mux", ratio, t("pipeline.mux_progress", pct=pct))

            try:
                ffmpeg_service.mux_soft_subtitles(
                    input_video,
                    srt_path,
                    output_video,
                    language=subtitle_language,
                    on_progress=mux_progress,
                    cancel=cancel,
                )
            except PipelineCancelledError:
                raise
            except FFmpegError as exc:
                raise PipelineError(t("pipeline.mux_fail", error=exc)) from exc
            tracker.complete("mux", t("pipeline.mux_done"))

            if on_progress:
                tracker.update("mux", 1.0, t("stage.done"))
            return PipelineResult(output_path=output_video, segment_count=len(segments))
        except PipelineCancelledError:
            if output_video.exists():
                output_video.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
