# Demo video made by an agent: audit

Checked on 24 October 2026. The goal is an agent (Claude Code) that, from this repo alone, starts Veil, drives it with a visible cursor and highlights, records it cleanly, adds a voiceover and edits it into the 2 to 3 minute MP4 that the submission needs. Items marked UNVERIFIED were not confirmed on their source.

## Bottom line

- **No mature tool does all three stages well.** There are two young all-in-ones: DemoDay (11 stars, needs a fal.ai key) and Ultrademo (35 stars). Neither is proven.
- **Playwright 1.64.1, released today, does most of the recording work itself.** `page.screencast` records 1920x1080 at 60 fps (VP9, about 3.5 Mb/s in our test). It draws an animated cursor with a click point, outlines the element being acted on, and shows chapter title cards. The old "blurry 1 Mb/s VP8" complaints are about earlier versions. We tested this on our landing page; the test files are in the scratchpad, not in the repo.
- **Recommendation: one pipeline in the repo, run in three stages that share one timeline file.** Generate the voice first, record second, edit third:
  1. TTS per scene.
  2. A deterministic Playwright script paced to the clip lengths.
  3. A Remotion composition that adds zoom, the browser frame, the numbers slides and music.
- **DemoDay is worth a 45-minute time-boxed try in parallel.** It is the closest one-shot match.

## The pipeline we recommend

```
demo/scenes.json      one narration line + actions per scene (the script, about 375 words for 2:30)
  -> 1. voice         demo/vo/<scene>.mp3 (+ word timings), duration of each clip via ffprobe
  -> 2. record        demo/record.mjs: Playwright 1.64 page.screencast, waits max(action, clip + 0.4 s)
                      writes raw.webm + timeline.json (scene start times, click times and boxes)
  -> 3. edit          Remotion: browser frame, zoom to each click, captions, title and numbers slides,
                      voice placed at each scene start, music ducked under the voice -> veil-demo.mp4
```

Why voice first: the narration length sets each scene's length, so the voice cannot drift behind the picture. A slow action simply delays the next line. Every tool that works well does this (DemoDay, Argo, demoreel, Remotion's voiceover rule).

Why a script and not a live agent: a live agent leaves seconds of idle frames while it thinks, and every take differs. Use Playwright MCP to explore and find selectors, then freeze the flow into `record.mjs`.

As a Claude Code skill this is one skill (`/demo-video`) with three steps, not three skills. The steps share `scenes.json` and `timeline.json`.

## 1. Recording and cursor

| Tool | Link | Stars, last push | Licence | Covers | Fit |
|---|---|---|---|---|---|
| Playwright 1.64.1 `page.screencast` | [playwright.dev/docs/api/class-screencast](https://playwright.dev/docs/api/class-screencast) | 98.4k, 24 Oct 2026 | Apache-2.0 | 60 fps video, cursor, action highlight, chapter cards | **High** |
| Playwright MCP 0.0.83 | [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | 38.6k | Apache-2.0 | Same video tools, only with `--caps=devtools` (our config does not set it) | Medium |
| webreel 0.1.4 | [vercel-labs/webreel](https://github.com/vercel-labs/webreel) | 949 | Apache-2.0 | JSON steps, cursor, keystroke HUD, MP4; zoom is fixed only | Medium |
| playwright-demo-video | [dxdleady/playwright-demo-video](https://github.com/dxdleady/playwright-demo-video) | 0, new | MIT | Cursor, ripple, DOM zoom, captions, spotlight | Ideas to copy |
| Cap / OpenScreen / Screenity | [Cap](https://github.com/CapSoftware/Cap), [OpenScreen](https://github.com/siddharthvaddem/openscreen) | 23.7k / 39.9k | mixed / MIT | Screen Studio clones; follow the OS cursor, which Playwright never moves | Low |

Gotchas found for Veil:
- **The sword cursor does not appear in recordings.** It is a CSS `cursor:` value, and native cursors never reach screencast frames. Draw it as a DOM sprite that follows `mousemove`, reusing `cursorUrl()` from `frontend/src/ui/cursor.tsx`.
- **Hide Playwright's "Mouse move" label.** By default every action shows a title pill top right; hide it with `showActions({ style: { title: 'display:none' } })`.
- **Set viewport and `size` to the same 1920x1080.** A larger `size` adds grey bars, not pixels. Leaving out `size` shrinks frames to fit 800x800.
- **Start recording only after the page is ready.** `goto`, wait for `document.fonts.ready`, then `screencast.start()`. Do not emulate reduced motion, because our CSS turns animations off under it.
- **Use the mock stream** (`npm --prefix frontend run mock`, then `dev:mock`) so every take has the same timing. Log in with `addCookies` or `storageState`, and never film the login.
- **Install system ffmpeg.** Playwright's own ffmpeg has no libx264, so run `brew install ffmpeg` for MP4 output. This is not needed if Remotion does the final render.

## 2. Voiceover

Ranks come from the [Artificial Analysis TTS leaderboard](https://artificialanalysis.ai/text-to-speech/leaderboard/provider-voice).

| Option | Rank | Cost for about 3 min | Timings | Licence for a public video | Setup |
|---|---|---|---|---|---|
| ElevenLabs `eleven_v4_turbo` / `eleven_v4` | #1 / #2 | about $0.11 / $0.22 | Per character on `/with-timestamps` (v4 support UNVERIFIED; `eleven_multilingual_v2` has it) | Free plan: non-commercial and "elevenlabs.io" must be in the title. Starter ($6/month): commercial | 10 min |
| Gemini 3.8 Flash TTS | #5 | free tier | None; use Whisper | On the free tier Google may use the data | 15 min |
| Kokoro-82M, local | #7 among open-weights models | $0 | Per word, English | Apache-2.0 | 10 min; needs Python 3.12 (`uv run --python 3.12 --with kokoro`) |
| macOS `say` (Premium voice) | not ranked | $0 | None | UNVERIFIED | 2 min, placeholder only |

How to use it:
- **Pick ElevenLabs on Starter for the final cut.** Use Kokoro for drafts, or as the fallback if nobody wants an account.
- **Pass `previous_text`/`next_text` to ElevenLabs** so the voice flows across scenes. Leave 0.3 to 0.6 s between scenes.
- **Write for the ear.** Keep each scene to 8 to 20 words. Write numbers as words, and spell out "P-I-I".
- **Captions:** build the SRT from the TTS timings rather than Whisper, so the text matches the script exactly. Homebrew's plain `ffmpeg` has no libass, so burn captions in Remotion, or install `ffmpeg-full`.
- **Music:** Pixabay Music is free with no credit needed. Keep it about 20 dB under the voice. In ffmpeg, duck it with `sidechaincompress`: music is the first input, the voice is the sidechain.
- **Disclosure:** put "AI voiceover" in the video description.

## 3. Editing

| Tool | Link | Stars, release | Licence | Why | Agent-friendly |
|---|---|---|---|---|---|
| Remotion 4.0.538 | [remotion-dev/remotion](https://github.com/remotion-dev/remotion) | 67.1k, 22 Oct 2026 | Free for individuals and companies of up to 3 people ([licence](https://remotion.dev/docs/license)) | React like our app, props JSON, captions, transitions, bundles its own ffmpeg | High: [remotion-dev/skills](https://github.com/remotion-dev/skills), also in the Anthropic plugin directory |
| reelcn | [reelcn.dev](https://www.reelcn.dev) | UNVERIFIED | MIT | Ready Remotion parts: `browser-window`, `screen-zoom`, `cursor`, `lower-third`, `bar-chart`, `counter`, `kpi-grid`, transitions, captions | High (llms.txt, skill) |
| HyperFrames (HeyGen) | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | 71.4k, v0.8.193 today | Apache-2.0 | HTML + GSAP, local Kokoro TTS, `cursor-zoom-follow` block | High, but pre-1.0 and releases daily |
| Plain ffmpeg | brew `ffmpeg` 9.0.2 | n/a | LGPL/GPL | Fallback: pad, concat, music, loudness | Medium; zoom and rounded corners are fiddly |

How the Remotion composition fits together:
- **The scene list** has three kinds of scene: title, clip and chart. Each scene's length comes from its voice clip (`calculateMetadata`); no frame counts are typed by hand.
- **Clip scenes** sit on a gradient background in a rounded window with a shadow. They zoom to 1.4 to 1.8x around each logged click, easing in over 0.4 s and holding about 1.5 s. They also have a lower third.
- **Chart scenes** show the leak-rate bars and counters, using the pixel font through `@remotion/google-fonts`.
- **Zoom gets soft past about 1.4x.** If text matters in a close-up, record that scene zoomed inside the browser (CSS `transform: scale`) instead.

Commands:
- Run `npx remotion browser ensure` early; it downloads Chrome Headless Shell.
- Render with `npx remotion render src/index.ts Demo out/veil-demo.mp4 --props=props.json --codec=h264 --crf=18`.
- A full render takes about 5 to 10 minutes on an M-series Mac (an estimate). Use `--scale=0.5` for drafts.

## All-in-one candidates

| Name | Link | Stars, last push | Record / voice / edit | Notes | Verdict |
|---|---|---|---|---|---|
| DemoDay | [mrieck/demoday-claude-plugin](https://github.com/mrieck/demoday-claude-plugin) | 11, 15 Sep 2026, MIT | yes / yes / yes | Claude plugin in the Anthropic directory, macOS only. Claude rehearses through its `demo-stage` MCP, then replays a script with an eased cursor. Voice first, Remotion edit with zoom and captions, presenter can be turned off. **Needs `FAL_API_KEY`** (ElevenLabs through fal.ai, about $0.30/min). Logs in with `--storage-state`. Uses native `recordVideo`; whether it gets the 1.64 quality is UNVERIFIED | Try first, 45 minutes max |
| Ultrademo | [new-xp/ultrademo](https://github.com/new-xp/ultrademo) | 35, Jul 2026, Apache-2.0 | yes / yes / yes | Flow file drives Playwright, Remotion renders zoom, cursor and captions. Voice: ElevenLabs, then Piper, then `say`. `npx skills add new-xp/ultrademo -a claude-code` | Fallback all-in-one |
| playwright-recast | [ThePatriczek/playwright-recast](https://github.com/ThePatriczek/playwright-recast) | 65, v0.23.0 4 Oct 2026, MIT | no / yes / yes | Turns a Playwright `trace.zip` into a video with cursor, ripples, auto-zoom, idle speed-up and subtitles; freezes the picture while a line is still playing. TTS from OpenAI, ElevenLabs or Polly | Best building block |
| Demo-Forge | [DixitRam/Demo-Forge](https://github.com/DixitRam/Demo-Forge) | 48, Oct 2026, MIT | yes / yes / yes | CDP screencast at 2x, so zoom stays sharp. Auto-zoom per click, browser editor for the last touches | Option |
| Argo | [shreyaskarnik/argo](https://github.com/shreyaskarnik/argo) | 47, v0.41.0, MIT | yes / yes / light | Playwright plus `narration.mark()`, Kokoro by default. Cursor and zoom UNVERIFIED | Option |
| claude-code-video-toolkit | [digitalsamba/claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) | 2.3k, MIT | yes / yes / yes | Remotion templates, `/record-demo`, voice on your own GPU or ElevenLabs | Too much setup for tonight |
| Marketing skills `video` (installed) | [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | n/a | guide | `references/product-demo-recording.md`: step modes (narrate before, during or after an action), fake cursor, ffmpeg mux | Good checklist |

Commercial tools (Clueso, Trupeer, Guidde, Tella, Arcade, Supademo, Screen Studio, Descript, Synthesia, HeyGen) either need a human recording first or keep the URL-to-video agent on enterprise plans. None has a CLI we could call tonight.

## Veil-specific risks

- **The Mubit console beat (1:20 in the script) is an outside site behind a login.** The agent must not type the password. Options:
  - A person records that 15 seconds with QuickTime or Cmd+Shift+5.
  - A person logs in once in a headed browser and saves a `storageState` file for Playwright.
  - Use screenshots with a slow pan in Remotion.
- **Numbers slides:** take them from `docs/research/2026-10-24-veil-numbers/` and the evalkit results. Say what they do not prove.
- **Synthetic data only.** Use the sample documents, never real ones.
- **Licences:** ElevenLabs Free is non-commercial and needs credit in the title, so use Starter or Kokoro. Remotion is free for a team our size.

## Plan for tonight

| Time box | Step |
|---|---|
| 20 min | Write `demo/scenes.json` from the live demo script (`NIGHT-SHIFT-TEAM-PACK.md` section 11.1), about 375 words |
| 15 min | Voice: Kokoro draft now, ElevenLabs final later |
| 60 min | `demo/record.mjs`: mock stream, cookie, sword sprite, `page.screencast` paced to the clips, `timeline.json` |
| 60 min | Remotion: browser frame, click zoom, captions, title and numbers slides, music |
| 20 min | Render, watch, fix, render the final MP4 |
| Parallel, 45 min max | Try DemoDay on the same flow and compare |

## Sources

- **Playwright**
  - [Screencast API](https://playwright.dev/docs/api/class-screencast) and [release notes](https://playwright.dev/docs/release-notes).
  - Old quality issues: [#31424](https://github.com/microsoft/playwright/issues/31424), [#17217](https://github.com/microsoft/playwright/issues/17217).
- **TTS**
  - [ElevenLabs models](https://elevenlabs.io/docs/overview/models)
  - [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
  - [mlx-audio](https://github.com/Blaizzy/mlx-audio)
- **Editing**
  - [Remotion licence](https://remotion.dev/docs/license) and [render CLI](https://remotion.dev/docs/cli/render)
  - [reelcn llms.txt](https://www.reelcn.dev/llms.txt)
  - [pagecast](https://github.com/mcpware/pagecast): zoom from a Playwright timeline
- **Articles**
  - [Greg Ceccarelli, Claude Code + Remotion](https://www.gregceccarelli.com/writing/build-product-video-with-ai)
  - [PurpleOwl, Playwright + ElevenLabs + FFmpeg](https://purpleowl.io/blog/we-automated-our-product-walkthrough-video-the-whole-thing)
  - [Justin Abrahms, injected cursor](https://justin.abrah.ms/blog/2026-02-12-generating-demo-videos-with-playwright.html)
  - [Javier Aguilar, audio drift fix](https://www.javieraguilar.ai/en/blog/automated-demo-recording-playwright/)
  - [dev.to, 30-second promo with Claude Code and Remotion](https://dev.to/rishabhsxn/making-a-30-second-app-promo-in-code-with-claude-code-and-remotion-5bo8)
- **Videos**
  - [Jonny Burger, Claude Code and Remotion](https://www.youtube.com/watch?v=Xtd4DjU9AU8)
  - [John Hartquist, technical videos with Claude Code and Remotion](https://www.youtube.com/watch?v=z7Bkf3Vc63U)
  - [chantastic, Remotion + Claude test](https://www.youtube.com/watch?v=afXYlQywuz4)
  - [Demo-Forge demo](https://www.youtube.com/watch?v=8yNsWK9SHq0)
- **Threads**
  - [HN: Argo](https://news.ycombinator.com/item?id=47369377)
  - [HN: DemoFly](https://news.ycombinator.com/item?id=47324590)
  - [Devpost: DiffCast](https://devpost.com/software/diffcast) (same React + FastAPI stack)
