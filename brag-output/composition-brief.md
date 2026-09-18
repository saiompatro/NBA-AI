# Hyperframes Composition Brief: NBA Live Predictor

## Objective
Create a short launch-style brag video for NBA Live Predictor, in the register of an NBA playoff broadcast cold-open where the model — not a player — is the athlete.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 21 seconds

## Source Material
- Project root: `C:/Users/admin/NBA AI`
- Primary files read: `app/templates/index.html`, `app/static/styles.css`, `app/static/dashboard.js`, `README.md`, `data/live_model_backtest.json`, `data/pregame_calibration.json`, `data/dashboard-screenshot.png`
- Product name: **NBA Live Predictor**
- Tagline / strongest claim: *"Live play-by-play in. Shot quality and win probability out. Every 3 seconds."*
- Key UI moments to recreate (all verbatim geometry / values from the project):
  - **Half-court shot chart SVG** — from `dashboard.js:shotChart()`. viewBox `0 0 510 480`. Court rect `x=5 y=5 w=500 h=470 rx=2`; key rect `x=175 y=285 w=160 h=190`; free-throw circle `cx=255 cy=285 r=60`; corner-three lines `x=35` and `x=475` from `y=475` to `y=333`; three-point arc `M 35 333 A 237.5 237.5 0 0 1 475 333`; restricted arc `M 215 422.5 A 40 40 0 0 1 295 422.5`; backboard `x1=225 y1=435 x2=285 y2=435`; hoop `cx=255 cy=422.5 r=7.5`. Shot dot radius is `4 + quality * 5` — **dot size literally encodes the model's shot-quality score**; keep that relationship and say so on screen.
  - **Win-probability chart** — from `dashboard.js:winProbabilityChart()`. viewBox `0 0 600 140`, pad 6, midline at y=67, `polyline` with `stroke-width=3`, `stroke-linecap=round`, `stroke-linejoin=round`, stroke = accent `#ed4f1c`.
  - **KPI row** — `.kpi-card` with a rounded icon chip, a big number, and an uppercase label beneath.
  - **Sidebar** — `#05070a`, the circular orange-outlined `NBA` brand ball, and the wordmark `NBA` + orange `Live` + `Predictor`.
  - **Upcoming Games row** — tip time on the left, two team rows, and a prediction chip on the right (`OKC 78%`) with `--accent-soft` background.
  - **Run Model button** — `.action-button`, label flips to `Running...` while in flight.
- Copy that must appear verbatim:
  - `EVERY SHOT HAS A NUMBER.`
  - `NBA Live Predictor`
  - `DOT SIZE = MODEL SHOT QUALITY`
  - `16` / `PLAYOFF TEAMS`
  - `78.4%` / `MODEL ACCURACY`
  - `2.1M+` / `EVENTS ANALYZED`
  - `Oklahoma City Thunder` / `OKC`, `Los Angeles Lakers` / `LAL`, chip `OKC 78%`
  - `Run Model` → `Running...`
  - `The Thunder get the edge because their overall team rating is stronger in this matchup.`
  - `3,680 GAMES FIT`
  - `68.1% PRE-GAME ACCURACY`
  - `EVERY 3 SECONDS`
  - `The game is live. So is the model.`

## Creative Direction
- Tone preset: `cinematic`
- Creative direction: NBA playoff broadcast cold-open where the model is the athlete
- Interpretation: wide frames, big restrained uppercase type, long confident holds. Camera language is push-in and slow drift, not chatter-cutting. Motion is heavy and weighted (long eases, no overshoot bounce). 2.35:1 letterbox bars, a faint film grain, and a slow warm light haze sell the broadcast-film read. Two loud beats only: the hook slam and the pick landing.
- Angle: A broadcast-grade NBA playoff cold-open where the star of the open is the model. Everything cinematic is drawn from the product's own geometry — the real half-court shot chart, the real win-probability polyline, the real orange-on-near-black palette. The camera is the model's point of view.
- Hook: black frame, letterboxed, warm haze drifting; one thin orange arc draws across the dark and lands on the app's hoop ring; `EVERY SHOT HAS A NUMBER.` slams in.
- Outro / punchline: three real receipts hold together, then the mark and `The game is live. So is the model.`
- Avoid:
  - Generic SaaS language ("streamline", "supercharge", "workflow")
  - Abstract filler visuals, particle systems, waveform bars, generic motion graphics
  - **Any real NBA broadcast footage, team logos, or agency photography** — licensed material, deliberately not used. Basketball texture comes from the app's own court geometry, not from stock media.
  - Unrelated visual redesign — stay inside the project's palette and Inter type

## Visual Identity
- Background: `#0b0e14` (dark `--page`); deepest void / sidebar `#05070a`
- Surface: `#121722` (`--surface`), raised `#171d29`
- Line: `#232a35`, strong `#323b48`
- Text: `#eef1f6` (`--ink`), secondary `#cfd6e0`, muted `#9aa5b3`, subtle `#6d7787`
- Accent: `#ed4f1c` (`--accent`/`--orange`), dark `#c4380e`, soft `#2a1c16`
- Green `#1f7a4d` · Red `#c4302b` · Gold `#cf9416`
- Radius: `4px` (the project is deliberately square-ish — do not round things off)
- Display font: **Inter 800**, uppercase, tight tracking for slams
- Body font: **Inter 400/500**
- Visual references from the project:
  - `data/dashboard-screenshot.png` — the actual rendered dashboard (light theme; recreate in **dark** theme using the vars above)
  - `app/static/dashboard.js` — exact shot-chart and win-prob SVG geometry
  - `app/static/styles.css` — `:root[data-theme="dark"]` block

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. **Tip-off / the arc** — 3.2s — orange shot-arc draws across black, lands on the hoop ring; `EVERY SHOT HAS A NUMBER.` slams in and holds ~2.2s.
2. **The court draws itself** — 3.8s — real half-court SVG strokes on, then 9 shot dots arrive one by one, radius = model shot quality; caption `DOT SIZE = MODEL SHOT QUALITY`; mark appears.
3. **The dashboard** — 4.5s — push-in on the real dark-theme dashboard; 3 KPI cards arrive one by one; Upcoming Games panel with the `OKC 78%` chip.
4. **Run Model** — 4.5s — cursor moves and clicks `Run Model`; label flips to `Running...`; the pick card lands (`OKC 78%` + the plain-English reason); the win-probability polyline draws and swings above the midline.
5. **The receipts / mark** — 5.0s — 3 real numbers reveal then hold as a set; fade; the mark lands with `The game is live. So is the model.`

## Audio
- Audio role: cinematic support — a low bed with weight, plus sparse motion-matched accents
- Audio arc: rises out of silence under the opening arc → gains pulse as the court populates → full weight under the dashboard → holds steady under the single loud payoff → fades to nothing so the final logo hit rings out alone
- Music: `assets/music/happy-beats-business-moves-vol-9-by-ende-dot-app.mp3`
- Music treatment: starts at 0s. Enter at ~0.45 volume, lift to ~0.6 at the dashboard reveal (Scene 3), hold under the Scene 4 payoff, fade to 0 across the final ~1.2s.
- Music cue guidance: bundled preset at `~/.claude/skills/brag/assets/music/cues/happy-beats-business-moves-vol-9-by-ende-dot-app.music-cues.json` (114.84 BPM). Target strong cues: **4.23s** (hook type slam), **12.65s** (the pick lands), **20.02s** (the mark). Beat grid for the shot dots: `4.23 / 4.75 / 5.28 / 5.80 / 6.34 / 6.86 / 7.40`. Beat grid for KPI cards: `7.92 / 8.44 / 8.96`. These are hints — ignore any that hurt readability or pacing.
- Audio-reactive treatment: **subtle**. Drive the arena-haze brightness behind the court and the glow presence on the accent line from bass RMS. Nothing else. No waveform bars, no equalizers, no particles, no strobing.
- Audio-coupled moments:
  - Scene 1, type slam — one low impact, beat-locked
  - Scene 2, 9 shot dots — beat-gridded soft low ticks, not one per every beat if it gets busy
  - Scene 3, 3 KPI cards — soft card arrivals
  - Scene 4, the press — one dry click; the pick card landing — one restrained announcement hit (loudest moment)
  - Scene 5, the mark — one dry logo hit, ringing out over the fade
- SFX selection guidance: heavy and dark over bright and tinny. This is a broadcast open, not a UI demo reel. Under 8 SFX total; no sound on every tween.
- SFX analysis guidance: `~/.claude/skills/brag/assets/sfx/sfx-analysis.md` and `.json`. Prefer low high-frequency-risk files for the repeated dot ticks and the polished card arrivals.
- Exact SFX choice: Hyperframes should choose filenames, timestamps, density, and volume based on the implemented animation.
- Audio files: copy the chosen music and any selected SFX into `brag-output/composition/assets/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). /brag is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project. (Here: the shot chart, the KPI row, the games panel, the win-prob chart — all with the project's exact geometry and values.)
- Keep all text readable in the final render. Reading floor: short label ~0.8s settled; a sentence ~0.3s/word, min ~1.2s. The hook line gets the most.
- Keep the video within 15-25 seconds. Target 21s.
- Include the planned music/SFX layer.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints. Major reveals may move toward nearby strong cues within ~0.15s; smaller entrances may align to nearby beats within ~0.10s. Use only 1-3 strong cue locks.
- Use SFX to support motion and interaction; restraint when the edit is already busy.
- Honor the music fade-out so the final logo hit rings out.
- Wire at least one visual element to music RMS (haze brightness / accent glow). If extraction is unavailable, document it and skip — do not block the render.
- Use local assets for audio and any runtime/media dependencies when possible.
- Run `npx hyperframes check` before render — it is brag's single gate.
