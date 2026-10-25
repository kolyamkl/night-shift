# Demo video pipeline

Makes the submission video from code: a narrated, edited MP4 of MuGuard. It opens on the research numbers and on how the three of us trained the model, then shows the app with a visible sword cursor and zooms on each action, then a closing card. It stays under the 2 minute limit (1:58 now). The approach and the tools we compared are in [docs/research/2026-10-24-demo-video/report.md](../docs/research/2026-10-24-demo-video/report.md).

Voice comes first, then the recording, then the edit. Each scene in the take lasts at least as long as its narration, so the voice never runs behind the picture.

```
scenes.json      the script: one narration line per scene, plus the titles and the numbers for the results slide
voice.py         Kokoro TTS, local and free  -> public/media/vo/<scene>.wav + word timings + durations.json
sfx.py           8-bit sound effects          -> public/media/sfx/*.wav (synthesised, nothing to license)
record.mjs       Playwright 1.64 screencast  -> rec/take.webm, public/media/take.mp4, public/media/timeline.json
edit.mjs         joins the three             -> public/media/edit.json
src/             Remotion composition        -> out/muguard-demo.mp4
```

## Run

1. Start the servers. They are in `.claude/launch.json`, or run them yourself:
   - `veil-backend-demo` on 8002
   - `veil-mock` on 8010
   - `veil-frontend-demo` on 5174
2. Then, from `demo/`:

```bash
npm install                 # once; also run: npx remotion browser ensure && npx playwright install chromium
uv run voice.py             # re-voices only the scenes whose text changed
uv run sfx.py               # once
node record.mjs             # about 80 s; HEADED=1 shows the browser
node edit.mjs
npm run studio              # preview and scrub in Remotion Studio
npm run render              # out/muguard-demo.mp4, 1080p H.264, about 2 minutes
```

## How the pieces work

- **Script.** Change what is said in `scenes.json`. A scene's actions live in `ACTIONS` in `record.mjs` under the same id.
- **Timing actions to words.** Inside an action, `at(seconds)` waits until that moment of the scene. Use it to land a click on a spoken word: the word times are in `public/media/vo/<scene>.json`.
- **Zooms.** `focus(box, scale, hold)` in `record.mjs` logs a zoom. The edit eases into it and holds it. Zooms past about 1.5x start to look soft.
- **Cursor.** Native CSS cursors never reach a screencast, so `record.mjs` injects a DOM copy of the app's sword. It switches sprites the way the app does: red blade on buttons, quill in text, shield on disabled controls. It adds a red pixel ripple on each click.
- **Login.** Each take registers a fresh local test account, so the session list starts empty.

## The pixel-art edit

All of it lives in `src/pixel.tsx`, `src/sprites.tsx` and `src/scenes/`, and uses the app's own palette and sprites.

| Element | What it does |
|---|---|
| Opening | The research as pixels: 71 of 100 blocks fill red, two of three pages turn red, then the pages fly to the model provider. |
| Block wipes | Open the video and hide every cut between chapters. |
| Captions | The knight's RPG dialog box; each word types in while it is spoken. |
| HUD | A quest counter in the corner. |
| Zooms | A red reticle locks onto each zoom. |
| Training | Party-select cards for the three developers, then a race to Mubit's 85% bar. |
| Results | Block meters (scene kind `chart`); not in the 2-minute cut. |
| Closing card | The victory knight drops in pixel by pixel. |
| Sound effects | Placed from the click events in the take: a blip per click, a coin on Hide, a fanfare after Approve, sweeps on the wipes. |

**Voice:**
- `scenes.json` sets the Kokoro voice (`bm_george`, a British male, at 1.12 speed).
- It also gives the phonemes for MuGuard and Mubit, which Kokoro would otherwise guess.
- For a richer old-British narrator, use an ElevenLabs voice. It needs an account (see below).

## Before the final take

**The draft is made against the mock stream, so three things in it are not real:**
- the detector's results come from the sample's answer key;
- the request ids read `mreq_mock…`;
- the answer says "Mock answer, no AI was asked".

**For the video we submit:**
1. Put `MUBIT_API_KEY` in `.env` and restart `veil-backend-demo`. `/api/health` should show the model on.
   - With the key, the mock still fakes the scan but passes the question to Claude through Mubit, so the answer is real.
2. To show the real detector and real request ids as well, run the demo frontend against the backend directly:

   ```bash
   cd frontend && VEIL_API=http://127.0.0.1:8002 npx vite --port 5174 --strictPort
   ```

   Every scan through the real backend is recorded by Mubit for training. Rate or discard those calls in the console.
3. **Final voice.** Swap Kokoro for ElevenLabs: about $0.20 a take, and the Starter plan is needed for a commercial licence. Add "AI voiceover" to the video description.
4. **Mubit console beat.** The console is behind a login, so record it by hand (Cmd+Shift+5) if the video needs it.
