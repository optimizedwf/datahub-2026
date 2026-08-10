# Demo Video Script — DataHub 2026 (3:41, two-domain story)

**Goal:** show DataHub as a factory's institutional memory — a Shop Graph of every part,
machine, and decision with lineage; agents that read the graph to say yes to profitable
work, no to money-losers, and get smarter with every job; then the original SQL evidence
proving metadata-aware code generation at 0.95 vs 0.70.

**Format:** 4 acts, 3:41, 1600x900@30fps. Real DataHub UI captures (:9002) + real terminal
replays (live LLM calls, deepseek-v4-flash temp 0) + TTS voiceover (edge-tts `en-US-ChristopherNeural`, +8% rate on SQL acts)
over a soft synth pad. Assembled with ffmpeg (concat filter).

---

## Act 0 — The Factory (0:00–1:04)

- 0:00–0:05 Title card: *DATAHUB 2026 — The Factory's Institutional Memory*
- 0:05–0:22 **The Shop Graph** (`docs/gallery/mfg_shop_graph.png`): 36 mfg entities —
  11 materials, machine profile, operation plan, 21 RFQs, 2 decision kernels — with
  lineage RFQ → material → machine. "Every part, machine, and material is registered
  with lineage."
- 0:22–0:36 **The No-Bid Agent** (`docs/gallery/rfq_010_brass.png`): Inconel on a 3-axis
  mill, titanium with no stock data → the graph says no-bid before the shop burns a
  dollar. **22/22 decisions match engineering ground truth.**
- 0:36–0:50 **Quotes · Safety Gates**: manufacturability scores, cycle times, envelope
  checks. Thin wall, tight tolerance, missing dimension each change the quote. Exotic
  alloys cap the score at 30 and block the gate.
- 0:50–1:04 **Part 2 / Automotive** (`docs/gallery/partsnap_brake_pad.png`): same
  substrate, new domain — 8 automotive parts, confidence or escalate to human.

## Act 1 — The graph knows (1:04–1:55)

- `healthcare.main.mart_billing` dataset summary: lineage sidebar, docs, tags,
  glossary term *Billing Amount*, ownership.
- Lineage tab: upstream dependency graph.
- Quality tab: **Failing** freshness assertion.
- Voiceover: DataHub registers every table, pipeline, and dashboard with lineage,
  glossary terms, and quality assertions — the context a code agent needs.

## Act 2 — Live evaluation (1:55–2:34)

- Real terminal: `bash examples/eval.sh` against the live DataHub instance.
- Three real questions with real LLM calls and real scores (h1 negative billing,
  h4 admissions after discharge, f1 fiction-retail order count).
- Voiceover: metadata-aware generation scores **0.95 vs 0.70** plain
  (20 questions, best-of-3, frozen 2026-08-05) — **+0.25** from reading the graph first.

## Act 3 — Write-back (2:34–2:51)

- `mart_billing` documentation tab showing the `[eval h1]` Insight doc — the agent's
  finding published back into the graph, searchable by the whole team.
- Same write-back mechanics power the factory: Decision / Analysis / Summary docs.

## Outro (3:05–3:41)

- Results card: **One platform. Every decision.** Factory Shop Graph (36 entities +
  lineage), No-Bid Agent 22/22, Safety Gates, Quotes, Tool-Wear Freshness, Learning
  Loop, PartSnap Automotive 8/8, SQL evidence **0.95 vs 0.70 (+0.25)**.
- Repo card: `github.com/optimizedwf/datahub-2026`, Apache-2.0, Makefile/CI/pytest.

---

## Rebuild

```bash
# 1. capture real UI screenshots (Playwright, authed against :9002) -> docs/gallery/
# 2. record terminal: ssh chow@<dell> 'bash examples/eval.sh' under ttyrec
# 3. render terminal frames: pyte + Menlo (1280x844) -> /tmp/term_frames2/
# 4. TTS: edge-tts --voice en-US-ChristopherNeural --rate +8% '<script>' -> .mp3 per segment
# 5. assemble: ffmpeg concat filter (part0_open + part2_mfg + sql_part + part3_results)
```

Artifact: `docs/demo_2026.mp4` (3:41, h264/aac 44100 stereo, 14.9 MB). Gallery captures were re-taken **after** B8 enrichment so the UI shows tags, glossary terms, domains, and owners. Voiceover: edge-tts en-US-ChristopherNeural (authoritative), SQL acts at +8% rate to fit the 128s visual timeline.
