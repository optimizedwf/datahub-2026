# Demo film v4.4 — Mr Chow voice + visual polish (2026-08-10)

## What changed (from v4.3 SHIP-certified)
1. **Voiceover re-voiced with the Mr Chow persona voice** (`en-US-GuyNeural` via edge-tts).
   - Provenance: the Mr Chow show pipeline (`mr-chows-show/scripts/tts_generate.py`) generates its
     show audio with exactly this voice ("deep, authoritative, American male voice").
   - Verified spectrally against the show's `audio.mp3` cold-open: matching fundamental (≈314–320 Hz)
     and spectral centroid; a different voice (ChristopherNeural) clearly differs (132 Hz).
2. **Visual polish** on all three generated cards (A/B bars, architecture, CTA):
   - Vertical gradient backgrounds instead of flat panels.
   - Soft glows behind headlines, bars, and the repo pill.
   - Glass-style cards with shadows + accent lines; refined typography and letter-spaced captions.

## Artifact
- `datahub_demo_final.mp4` — 131.5 s (2:11), 1920×1080 h264+AAC, 29.9 MB.
- Audio: mean −21.2 dB / max −1.5 dB (loudnorm I=−16:TP=−1.5, fade-out last 2 s).
- md5 `2c2cb6eddf72e2adae589d86b1e55535`.
- Video is hosted out-of-repo (gitignored `demo_*.mp4`) per submission checklist.
