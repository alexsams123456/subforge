# -*- coding: utf-8 -*-
"""Различение говорящих по голосу (без подписей в субтитрах)."""

from __future__ import annotations

import os
import urllib.error
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np

from app.services.i18n import t
from app.services.progress import ProgressTracker
from app.services.transcription import Segment

if TYPE_CHECKING:
    from app.services.cancellation import CancellationToken

SAMPLE_RATE = 16000
MIN_SEGMENT_SEC = 0.25
MIN_EMBED_SEC = 0.5
CLUSTER_DISTANCE = 0.72


class DiarizationError(RuntimeError):
    """Ошибка определения говорящих."""


def _diarization_load_error(exc: BaseException) -> str:
    """Сообщение для пользователя в зависимости от типа ошибки загрузки модели."""
    base = t("diarization.load_error_base")

    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 1314:
        return t("diarization.symlink_error", base=base)

    if isinstance(exc, (urllib.error.URLError, ConnectionError)):
        return t("diarization.internet_error", base=base)

    try:
        from requests.exceptions import HTTPError

        if isinstance(exc, HTTPError):
            return t("diarization.internet_error", base=base)
    except ImportError:
        pass

    return f"{base}\n{exc}"


def _model_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA", "")
    if base:
        path = Path(base) / "SubForge" / "models" / "spkrec-ecapa-voxceleb"
    else:
        path = Path.home() / ".subforge" / "models" / "spkrec-ecapa-voxceleb"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_classifier():
    try:
        import torch
        from speechbrain.inference.speaker import EncoderClassifier
        from speechbrain.utils.fetching import LocalStrategy
    except ImportError as exc:
        raise DiarizationError(t("diarization.deps_missing")) from exc

    try:
        classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=str(_model_dir()),
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
            local_strategy=LocalStrategy.COPY,
        )
    except Exception as exc:
        raise DiarizationError(_diarization_load_error(exc)) from exc
    return classifier


def _load_audio(audio_path: Path) -> np.ndarray:
    """Загрузить WAV из ffmpeg (16 kHz mono, pcm_s16le) без torchaudio.load."""
    import wave

    try:
        with wave.open(str(audio_path), "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            raw = wf.readframes(wf.getnframes())
    except wave.Error as exc:
        raise DiarizationError(t("diarization.read_audio_failed", error=exc)) from exc

    if sample_width != 2:
        raise DiarizationError(
            t("diarization.unsupported_wav", bits=sample_width * 8)
        )
    if sample_rate != SAMPLE_RATE:
        raise DiarizationError(
            t("diarization.wrong_sample_rate", rate=sample_rate, expected=SAMPLE_RATE)
        )

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)
    return audio


def _slice_segment(waveform: np.ndarray, start: float, end: float) -> np.ndarray:
    s = max(0, int(start * SAMPLE_RATE))
    e = max(s + 1, int(end * SAMPLE_RATE))
    chunk = waveform[s:e]
    min_samples = int(MIN_EMBED_SEC * SAMPLE_RATE)
    if len(chunk) < min_samples:
        pad = min_samples - len(chunk)
        chunk = np.pad(chunk, (0, pad), mode="constant")
    return chunk


def _embed_segment(classifier, chunk: np.ndarray) -> Optional[np.ndarray]:
    try:
        import torch
    except ImportError:
        return None

    tensor = torch.tensor(chunk, dtype=torch.float32).unsqueeze(0)
    with torch.no_grad():
        embedding = classifier.encode_batch(tensor)
    vector = embedding.squeeze().cpu().numpy()
    norm = np.linalg.norm(vector)
    if norm <= 0:
        return None
    return vector / norm


def _cluster_embeddings(embeddings: np.ndarray) -> np.ndarray:
    from sklearn.cluster import AgglomerativeClustering

    if len(embeddings) == 1:
        return np.array([0])

    clustering = AgglomerativeClustering(
        n_clusters=None,
        distance_threshold=CLUSTER_DISTANCE,
        metric="cosine",
        linkage="average",
    )
    return clustering.fit_predict(embeddings)


def _nearest_labeled_index(index: int, labels: list[Optional[int]], total: int) -> Optional[int]:
    for offset in range(1, total):
        left = index - offset
        if left >= 0 and labels[left] is not None:
            return labels[left]
        right = index + offset
        if right < total and labels[right] is not None:
            return labels[right]
    return None


def assign_speakers(
    segments: list[Segment],
    audio_path: Path,
    tracker: Optional[ProgressTracker] = None,
    cancel: Optional["CancellationToken"] = None,
) -> list[Segment]:
    """Назначает каждому фрагменту внутренний id говорящего (без текста в субтитрах)."""
    if not segments:
        return []

    if tracker:
        tracker.begin("diarize", t("diarization.loading_model"))
        tracker.update("diarize", 0.05, t("diarization.loading_model"))

    classifier = _load_classifier()
    waveform = _load_audio(audio_path)

    if tracker:
        tracker.update("diarize", 0.15, t("diarization.analyzing"))

    embed_indices: list[int] = []
    embeddings: list[np.ndarray] = []
    labels: list[Optional[int]] = [None] * len(segments)

    for idx, seg in enumerate(segments):
        if cancel:
            cancel.check()

        duration = max(seg.end - seg.start, 0.0)
        if duration < MIN_SEGMENT_SEC:
            continue
        chunk = _slice_segment(waveform, seg.start, seg.end)
        vector = _embed_segment(classifier, chunk)
        if vector is None:
            continue
        embed_indices.append(idx)
        embeddings.append(vector)
        if tracker:
            ratio = 0.15 + 0.55 * (len(embed_indices) / max(len(segments), 1))
            tracker.update(
                "diarize",
                ratio,
                t("diarization.progress", done=len(embed_indices), total=len(segments)),
            )

    if not embeddings:
        if tracker:
            tracker.complete("diarize", t("diarization.one_speaker"))
        return [
            Segment(
                start=s.start,
                end=s.end,
                text=s.text,
                speaker="0",
                speech_end=s.speech_end,
                words=s.words,
            )
            for s in segments
        ]

    if tracker:
        tracker.update("diarize", 0.75, t("diarization.clustering"))

    cluster_ids = _cluster_embeddings(np.stack(embeddings))
    for seg_idx, cluster in zip(embed_indices, cluster_ids):
        labels[seg_idx] = int(cluster)

    for idx, label in enumerate(labels):
        if label is None:
            nearest = _nearest_labeled_index(idx, labels, len(labels))
            labels[idx] = 0 if nearest is None else labels[nearest]

    speaker_count = len(set(labels))
    if tracker:
        tracker.complete("diarize", t("diarization.speakers_found", count=speaker_count))

    return [
        Segment(
            start=seg.start,
            end=seg.end,
            text=seg.text,
            speaker=str(label),
            speech_end=seg.speech_end,
            words=seg.words,
        )
        for seg, label in zip(segments, labels)
    ]
