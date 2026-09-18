# Brag Plan: NBA Live Predictor

## What is this app?
A real-time NBA analytics dashboard that ingests live play-by-play, scores every shot with an XGBoost shot-quality model and every game state with a PyTorch win-probability model, and pushes it to a single-page dashboard over WebSocket every 3 seconds.

## The angle
A broadcast-grade NBA playoff cold-open — except the star of the open is the model, not the player. Everything cinematic in this video is drawn from the product's own geometry: the real half-court shot chart, the real win-probability polyline, the real orange-on-near-black palette. No stock arena footage, no generic motion graphics. The premise: *the camera is the model's point of view.*

> Sourcing note: real NBA broadcast clips and agency photography from the 2025-26 season are licensed material and are not used. The "cinematographic basketball" texture is built from the app's own court SVG, shot dots, light haze, letterbox, and grain.

## Hook (first 2-3 seconds)
Pure black, letterboxed. A single thin orange vector arc draws across the dark — the flight path of a shot, rendered in the app's accent color. It lands on the rim circle from the app's real court SVG. Type slams in: **EVERY SHOT HAS A NUMBER.**

## Key moments (the middle)
- The real half-court diagram draws itself stroke-by-stroke (exact geometry from `dashboard.js`: key, restricted arc, 3pt arc, hoop at 255,422.5), then 9 shot dots pop in one by one — orange = made, dim = missed, **radius scaled by the model's shot-quality score**, exactly as the app does it.
- The actual dashboard pushes in: the real KPI row (`16 PLAYOFF TEAMS`, `78.4% MODEL ACCURACY`, `2.1M+ EVENTS ANALYZED`) and the real Upcoming Games panel with the `OKC 78%` prediction chip on Thunder-Lakers.
- Simulated interaction: a cursor clicks **Run Model**. The button flips to `Running...`, then the pick lands with the app's plain-English reason line, and the win-probability polyline draws live and swings.

## Outro / punchline
Three real numbers slam in and hold: `3,680 GAMES FIT` / `68.1% PRE-GAME ACCURACY` / `EVERY 3 SECONDS`. Then the mark. Final line: **The game is live. So is the model.**

## User flow worth showing
1. **Entry** — open the dashboard, see live KPIs and tonight's slate with model percentages already attached.
2. **Key action** — click `Run Model` on a game.
3. **Result** — the pick, its plain-English justification, and the win-probability trend line moving.

This flow is the centerpiece (Scenes 3-4). The court and stat scenes frame it.

## Tone
- Preset: `cinematic`
- Creative direction: NBA playoff broadcast cold-open where the model is the athlete
- Interpretation: wide frames, big restrained type, long confident holds, dramatic light-sweep and push-in camera moves instead of cutting for its own sake. Motion is heavy and weighted, not bouncy. Letterbox bars, subtle grain, and a slow warm haze sell the "broadcast film" read. Restraint everywhere except the two payoff beats.

## Format: landscape — 1920x1080
## Duration: 23 seconds (built)

> Revised from 21s during composition: the app's own plain-English reason line is 14 words, which needs ~4.2s of settled hold at the reading floor. Scenes 3 and 4 were also merged into one continuous camera move, since the storyboard already called for "no cut" between them. Final shape is 4 clips, 23.0s — still inside the 15-25s law.

## Visual identity (from the project)
- Background: `#0b0e14` (dark-theme `--page`), sidebar/void `#05070a`
- Surface: `#121722` (`--surface` dark), `#171d29`
- Accent: `#ed4f1c` (`--orange` / `--accent`), dark `#c4380e`
- Text: `#eef1f6` (`--ink` dark), muted `#9aa5b3`
- Green (made/positive): `#1f7a4d` · Red: `#c4302b` · Gold: `#cf9416`
- Display font: Inter 800 (tight tracking, uppercase for slams)
- Body font: Inter 400/500
- Strongest visual element: the half-court shot chart SVG — real geometry, dots sized by model confidence

## Share copy (draft)
Built an NBA dashboard that scores every shot as it happens — XGBoost for shot quality, PyTorch for win probability, live over WebSocket every 3 seconds. 3,680 games fit. 68.1% pre-game accuracy.

## Audio direction
- Role: cinematic support — low bed with weight, restrained motion-matched accents
- Music: `happy-beats-business-moves-vol-9-by-ende-dot-app.mp3`
- Music treatment: start at 0, enter low (~0.45), lift to ~0.6 at the dashboard reveal, hold under the payoff, fade to 0 across the last 1.2s so the final accent rings out over silence
- Music cue guidance: bundled preset read (`cues/...vol-9...music-cues.md`, 114.84 BPM). Strong cues to target — **4.23s** (hook type slam), **12.65s** (the pick lands), **20.02s** (mark). Beat-grid window for sequential shot dots: 4.23 / 4.75 / 5.28 / 5.80 / 6.34. Beat-grid for KPI cards: 7.92 / 8.44 / 8.96.
- Audio-reactive treatment: subtle — bass RMS drives the arena haze brightness behind the court and the glow presence on the accent line. No waveform bars, no particles, no strobing.
- SFX posture: sparse and heavy. A low swell under the hook, soft card arrivals on the KPI row, one click on the Run Model press, one restrained announcement hit on the pick, one dry logo hit at the end.
- Audio-coupled moments: shot dots arriving one by one; KPI cards arriving one by one; the cursor click; the pick payoff; the mark.
- Restraint rule: no sound on every tween. Under 8 SFX total. Nothing bright or tinny — this is a broadcast open, not a UI demo reel.

## Storyboard

### Scene 1 — Tip-off / the arc — 3.2s
Black `#05070a`, 2.35:1 letterbox bars. A slow warm haze (arena light bloom, `#ed4f1c` at very low alpha) drifts across from upper-left. A single 2px orange arc draws left-to-right across the frame — a shot's flight path — and terminates on a small ring (the app's hoop circle). Type slams in centered, Inter 800, uppercase, tight: **EVERY SHOT HAS A NUMBER.** (5 words → ~1.5s settled minimum; entrance 0.45s, hold ~2.2s.)
Sequential/interaction: none — one arc draw, one type slam.
Audio intent: low swell rising out of silence; the frame should feel like a broadcast about to start.
Audio-coupled idea: the type slam lands on a strong cue with a single low impact.
Music: cinematic bed entering low.
Transition mood: dramatic → Scene 2

### Scene 2 — The court draws itself — 3.8s
The arc's ring expands into the app's real half-court SVG, which draws stroke-by-stroke (key rect, restricted-area arc, 3pt arc, baseline lines, hoop). Lines are `#eef1f6` at low alpha on `#0b0e14`. Then 9 shot dots pop in **one by one** — made = `#ed4f1c`, missed = dim `#323b48` — each dot's radius set by the model's shot-quality score, exactly as the product does it. Small caption lower-left: `DOT SIZE = MODEL SHOT QUALITY`. Product mark appears upper-left: **NBA LIVE PREDICTOR**.
Sequential/interaction: yes — 9 dots arrive one at a time on the beat grid (4.23 / 4.75 / 5.28 / 5.80 / 6.34 and continuing), with the last dot punctuated.
Audio intent: the bed gains a pulse; each dot gets a soft, low tick — never bright.
Audio-coupled idea: beat-gridded dot arrivals.
Music: bed lifting.
Transition mood: dramatic push-in → Scene 3

### Scene 3 — The dashboard — 4.5s
Camera pushes in on the real dashboard, recreated in the app's exact palette and Inter type: dark sidebar `#05070a` with the orange `NBA` brand ball and nav, and the real KPI row. Three KPI cards arrive **one by one**: `16 PLAYOFF TEAMS` → `78.4% MODEL ACCURACY` → `2.1M+ EVENTS ANALYZED`. Then the Upcoming Games panel slides in showing the real slate row: `Oklahoma City Thunder OKC / Los Angeles Lakers LAL` with the `OKC 78%` chip.
Sequential/interaction: yes — 3 KPI cards arrive one by one (beats 7.92 / 8.44 / 8.96), each held; the games panel follows as a block.
Audio intent: confident, building; the product feels substantial.
Audio-coupled idea: card-arrival sounds on each KPI, soft and low.
Music: full bed.
Transition mood: clean hold, no cut — camera continues → Scene 4

### Scene 4 — Run Model — 4.5s
A cursor moves to the `Run Model` button on the Thunder-Lakers row and clicks. The button label flips to `Running...` for ~0.4s. Then the prediction card lands hard: **OKC 78%**, with the app's plain-English reason line beneath: *"The Thunder get the edge because their overall team rating is stronger in this matchup."* As it lands, the win-probability polyline (the app's real `wp-chart` — 600x140 viewBox, 3px orange stroke, midline at 50%) draws across and swings above the midline.
Sequential/interaction: yes — simulated cursor move + click, button state change, then the payoff card.
Audio intent: the click is dry and small; the pick landing is the loudest moment in the video.
Audio-coupled idea: one click SFX on the press, one restrained announcement hit as the card lands, beat-locked to **12.65s**.
Music: bed holds under the payoff.
Transition mood: hard, weighted cut → Scene 5

### Scene 5 — The receipts / mark — 5.0s
Back to near-black, letterboxed, with the win-probability line still faintly alive behind at low alpha. Three real numbers reveal quickly and then **hold together on screen**: `3,680 GAMES FIT` · `68.1% PRE-GAME ACCURACY` · `EVERY 3 SECONDS`. (Revealed ~0.5s apart, then the full set holds ~1.4s — never one-per-beat at this tempo.) They fade; the mark lands centered: the orange `NBA` ball + **NBA Live Predictor**, with the final line beneath: **The game is live. So is the model.**
Sequential/interaction: yes — 3 stat lines reveal in sequence, then hold as a set.
Audio intent: the bed drops away; the mark lands into near-silence.
Audio-coupled idea: one dry logo hit at the mark, beat-locked near **20.02s**, ringing out as the music fades to 0.
Music: fade to 0 across the final 1.2s.
Transition mood: end.

**Music mood for this video:** cinematic
**Audio summary:** A low bed rises out of silence under the opening arc, gains pulse as the court populates, carries the dashboard at full weight, holds steady under the single loud payoff when the pick lands, then fades to nothing so the final logo hit rings out alone.

**Scene duration check (as built):**

| # | Scene | Start | Duration | End |
|---|---|---|---|---|
| 1 | Tip-off / the arc | 0.00 | 3.70 | 3.70 |
| 2 | The court draws itself | 3.70 | 4.22 | 7.92 |
| 3 | The dashboard → Run Model (one continuous camera) | 7.92 | 9.46 | 17.38 |
| 4 | The receipts / the mark | 17.38 | 5.62 | 23.00 |

**Total: 23.0s** (within 15-25s)

**Beat locks as built** (3 strong cues, per the ±0.15s budget):
- **3.70s** — the hook's ring expands into the half-court (scene turn)
- **7.92s** — the dashboard push-in begins
- **12.65s** — the pick lands (strongest cue in the window)

**Beat grid as built:** hook slam 1.07 · shot dots 4.75 +0.14 stagger (non-text accents) · hero dot 6.34 · KPI cards 8.44 / 8.96 / 9.50 · cursor press 12.12 · reason line 13.18 · receipts 17.91 / 18.44 / 18.96 · mark 20.54

**Audio as built:** 7 SFX total (hook slam, 3 KPI arrivals, the click, the pick hit, the logo bell) — the planned shot-dot ticks were cut to honor the "under 8 SFX, not a UI demo reel" restraint rule. Music bed fades in 0→1.1s at 0.45, lifts to 0.60 at 7.6s, settles to 0.50 under the payoff, and fades to 0 across 21.5-22.9s so the bell rings out alone.

**Audio-reactive:** extraction skipped — FFmpeg is not installed on this machine, so per-frame RMS could not be pulled. Substituted a deterministic music-coupled treatment instead: the arena haze swells on the same cue timestamps the edit is locked to (1.07, 6.34), driven off the bundled cue preset rather than sampled audio. Wire the real RMS pass once FFmpeg is present if you want it tighter.
