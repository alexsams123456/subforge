# SubForge

> Local speech recognition → soft subtitles in video · [Whisper](https://github.com/openai/whisper) · Windows

**SubForge** is a Windows desktop app that transcribes speech with OpenAI Whisper ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)) and muxes subtitles into video (default **MP4**) as a soft track. Everything runs on your machine — no uploads, no word filtering. Subtitles auto-enable in VLC and PotPlayer.

Pick a video → speech is recognized locally → subtitles are **embedded inside** the output file as a separate track (or burned in for WebM). No standalone `.srt` file is created or left behind.

## Why SubForge?

Most Whisper tools export a separate `.srt` file. SubForge goes further:

| | Typical Whisper GUI | SubForge |
|---|---------------------|----------|
| Output | `.srt` on disk | Soft subs **inside video** (MP4/MKV/…) |
| Privacy | Often cloud-based | **100% local** on your PC |
| Playback | Manual load in player | **Auto-enable** in VLC / PotPlayer |
| Dialog | Single block of text | **Speaker separation** — one line per voice |
| Text | Sometimes filtered | **Verbatim** — no censorship |

Built for films and long-form video: batch queue, GPU acceleration (NVIDIA CUDA), progress with ETA, and a portable `.exe` build.

## Features

- **Fully local** — video never leaves your PC
- **Soft subtitles** muxed into MP4/MKV/MOV/M4V/AVI/WMV; **WebM** uses burn-in (no separate track)
- **Output format selector** — MP4 (default), MKV, MOV, M4V, AVI, WebM, WMV
- **Three Whisper engines** — from fast (`base`) to maximum accuracy (`large-v3`)
- **Speaker separation** — different voices on separate lines (no "Speaker 1" labels)
- **Batch processing** — queue multiple videos with the same settings
- **GPU acceleration** — NVIDIA CUDA when available
- **Multilingual UI** — English, Russian, German, French, Italian, Japanese
- **No censorship** — verbatim transcription, no word filtering

## Requirements

- Windows 10/11
- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) in `PATH`, **or** `bin\ffmpeg.exe` in the project folder

### Install ffmpeg

Using the included script (winget):

```powershell
powershell -ExecutionPolicy Bypass -File .\install_ffmpeg.ps1
```

Or manually:

```powershell
winget install Gyan.FFmpeg
```

Or download a build and place `ffmpeg.exe` in the project's `bin\` folder.

Verify:

```powershell
ffmpeg -version
```

## Quick setup

**Clone + install (one line):**

```powershell
git clone https://github.com/alexsams123456/subforge.git subforge; cd subforge; powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

**Already cloned:**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`setup.ps1` creates `.venv`, installs dependencies, copies ffmpeg to `bin\`, and adds `SubForge.lnk` on the desktop.

**Recreate venv from scratch:**

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -Recreate
```

On first run, the Whisper model downloads automatically (internet required once).  
With **Separate speakers** enabled, a voice model (~90 MB) is also downloaded once.

Double-click **SubForge.lnk** to launch — no console window.

## Run from terminal

```powershell
.\.venv\Scripts\Activate.ps1
python main.py
```

1. Click **Choose video** or **drag and drop** one or more videos into the window
2. Pick **engine**, **languages**, **output format**, **subtitle lines**, and toggles
3. Click **Create subtitles** and choose an **output folder** — each file is saved as `{name}_subtitles.{ext}` (e.g. `.mp4`, `.mkv`)
4. During processing you see **progress**, **ETA**, and the file number in the queue; **Cancel** stops the entire queue
5. Open the result in **VLC** or **PotPlayer**

## Batch processing

- Add multiple videos via the file dialog (multi-select) or drag-and-drop
- One output folder for the whole batch; names like `film_subtitles.mkv`, or `film_subtitles_2.mkv` on collision (extension matches chosen format)
- Files are processed **sequentially** with the same settings
- If any file has **no audio track**, the batch **won't start** (preflight check before processing)
- On **error** or **cancel**, remaining files are skipped
- External audio files (e.g. Topaz workflow) are **not supported** in batch mode

## Saved settings

Engine, speech and subtitle languages, **output format**, lines per screen, **Separate speakers**, and **Hide non-speech sounds** are **remembered** between sessions. Stored in `%LOCALAPPDATA%\SubForge\settings.json` (along with UI language).

## Output format

Choose **Output format** in settings before processing:

| Format | Subtitles | Notes |
|--------|-----------|-------|
| **MP4** (default) | Soft track (`mov_text`) | Best compatibility with VLC / PotPlayer |
| **MKV** | Soft track (`srt`) | Good for anime and films |
| **MOV / M4V** | Soft track (`mov_text`) | Same family as MP4 |
| **AVI / WMV** | Soft track (`srt`) | Works, but fewer players than MP4/MKV |
| **WebM** | Burned into video | WebM has no soft subtitle track — subs are always visible |

No extra codecs to download: bundled ffmpeg (via `install_ffmpeg.ps1`) includes everything needed.

## UI language

- Default interface language: **English**
- Switch in the footer: **English**, **Русский**, **Deutsch**, **Français**, **Italiano**, **日本語**
- Choice is saved in `settings.json` and applied without restart
- This is **not** the speech language in the video or subtitle language — only button labels and messages

## Recognition engines

Three engines powered by local **OpenAI Whisper** (via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)).

| Engine | Whisper model | When to use |
|--------|---------------|-------------|
| **Powerful** (default) | `large-v3` | Japanese films, maximum accuracy |
| **Balanced** | `medium` | Quality/speed trade-off for long films |
| **Simple** | `base` | Fast processing, lower CPU/GPU load |

First run of **Powerful** downloads ~3 GB; **Balanced** ~1.5 GB. Internet required once.

## Speech and subtitle languages

Two separate settings:

| Setting | Purpose |
|---------|---------|
| **Speech language** | Language spoken in the video (Whisper hint) |
| **Subtitle language** | Language shown in the player |

Available: **English**, **Deutsch**, **Français**, **Italiano**, **Japanese**, **Русский**, **Auto**. Default for both: **English**.

Examples:

- Japanese film with Japanese subtitles: speech **Japanese**, subtitles **Japanese**, engine **Powerful**
- Japanese film with English subtitles: speech **Japanese**, subtitles **English** — Whisper translates to English

**Limitation:** translation is supported **only to English**. If speech and subtitle languages differ and subtitles are not English, the app shows an error before processing starts.

## Speaker separation

- **Separate speakers** is enabled by default
- Different voices appear on **separate lines** — no "Speaker 1", "Speaker 2" labels
- With two lines on screen, a short two-person dialog may look like:
  ```
  Hello there.
  Hi!
  ```
- Character names are **not** detected — only voice-based separation
- First use downloads a model (~90 MB); on Windows files are copied locally (Developer Mode not required)
- Takes longer; disable via the settings toggle if needed

## Logs

On processing, model download, or startup errors, details are written to a **log**:

- **Log** button in the main window footer — view, copy, refresh
- After an error, the app offers to open the log immediately
- Also on disk: `%LOCALAPPDATA%\SubForge\logs\subforge.log` (**Log folder** button in the log viewer)

Copy log text when you need help diagnosing an issue.

## Troubleshooting mux errors

If processing fails at the **Muxing subtitles** stage:

1. **Free disk space** — for large **MP4** outputs (~4 GB+), keep roughly **2× the video size** free on the output drive. SubForge uses `-movflags +faststart`, which may need a temporary second copy during mux.
2. Try output format **MKV** instead of MP4 — no faststart pass; soft `srt` track remuxes reliably for many files.
3. Choose an output folder with a simple **ASCII path** (e.g. `C:\Temp\subforge_out`).
4. Close any player that may have the output file open.
5. Open **Log** — on failure the full ffmpeg stderr is saved there; the UI shows a short summary (all mux attempts when soft MP4 falls through copy → copy without faststart → re-encode).

## Privacy & uncensored output

- All processing runs **locally** on your PC — video is never uploaded
- Whisper does **not** filter or censor speech — subtitles are verbatim
- No profanity filters, word blocklists, or text rewriting

## Notes

- Default output is **MP4** with a `mov_text` subtitle track; other formats available in settings
- Large MP4 files (~4 GB+): ensure enough free space on the output drive (~2× file size during faststart), or use **MKV**
- Soft subs work reliably in VLC and PotPlayer; **WebM** always shows burned-in subs
- Status bar shows **GPU or CPU** — Whisper uses NVIDIA CUDA automatically when available
- **ETA** (estimated time remaining) is shown during processing
- Long videos take longer on CPU

## Project structure

```
subforge/
  main.py
  setup.ps1
  requirements.txt
  AGENTS.md              # brief instructions for AI agents
  docs/AGENT_CONTEXT.md  # full technical context (for agents)
  app/
    ui/           # application window
    services/     # ffmpeg, Whisper, pipeline, i18n, settings
    locale/       # UI translations (en, ru, de, fr, it, ja)
  bin/            # optional: ffmpeg.exe, ffprobe.exe
```

## Build standalone .exe (developers)

Portable folder without Python on the target PC:

```
dist/SubForge/
  SubForge.exe
  _internal/
  bin/ffmpeg.exe, ffprobe.exe
```

**One line** (after `setup.ps1`):

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1; powershell -ExecutionPolicy Bypass -File .\create_shortcut_release.ps1
```

- Build **Windows only**; bundle includes **torch CUDA** (cu124) — size ~2–4 GB
- Whisper models still download on first run
- Target PC needs an NVIDIA driver for GPU; CPU fallback works without it
- Antivirus software may flag PyInstaller builds — usually a false positive

## For developers / AI agents

Full technical context: [docs/AGENT_CONTEXT.md](docs/AGENT_CONTEXT.md)  
When changing code, update that file and this README.

## License

See repository license file (if present).
