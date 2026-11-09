# VoiceBridge &mdash; Development Log

A chronological engineering chronicle of VoiceBridge's evolution from a midnight scratchpad prototype to a zero-dependency, production-grade local network dictation and clipboard bridge for macOS.

---

## [v0.1.0] - 2026-09-25 &bull; 02:30
### The Core Pipeline &bull; Clipboard Injection vs. HID Emulation

- **Context**: Prolonged typing sessions on mechanical keyboards cause significant hand and finger fatigue. Android's Gboard (specifically with the Gemini-powered Rambler model enabled) provides near-flawless, disfluency-stripped speech-to-text, but macOS has no native integration with this pipeline.
- **Architectural Decision**: 
  - Explored simulating a Bluetooth Human Interface Device (HID) keyboard profile on Android, but Bluetooth HID stacks on modern mobile OSes are heavily restricted, unreliable to pair cross-platform, and introduce latency.
  - Explored keystroke-by-keystroke simulation over local sockets (e.g. `osascript -e 'tell application "System Events" to keystroke ...'`), but character-by-character typing of long paragraphs took seconds and choked on emoji and special characters.
  - **Selected Solution**: Local HTTP server (`dictate.py`) running Python 3's built-in `http.server`. When speech is submitted from the phone, the server pipes the string directly to macOS `pbcopy` and executes a single atomic keystroke via `System Events` to fire `Cmd + V`. Multi-paragraph blocks paste into any active window in sub-millisecond time.
- **Key Deliverables**:
  - Initial `dictate.py` script running a standard `ThreadingHTTPServer` on port `5050`.
  - Basic mobile textarea with immediate submission.
  - Zero third-party dependencies—relies entirely on Python 3 standard library (`subprocess`, `http.server`, `socket`).

---

## [v0.2.0] - 2026-09-25 &bull; 03:15
### Daemonization &bull; macOS TCC Privacy Sandbox & LaunchAgents

- **Context**: Manually launching a terminal window to run `python3 dictate.py` every time the Mac boots defeats the convenience of hands-free dictation. The bridge needed to run completely headless as an automatic background service on user login.
- **Root-Cause Discovery**:
  - The initial `launchd` plist registered under `~/Library/LaunchAgents/` repeatedly crashed on system reboot with exit code `2` (`ENOENT` / permission denied), even though it ran fine when triggered manually inside Terminal.
  - **Investigation**: macOS Transparency, Consent, and Control (TCC) enforces a strict privacy sandbox. LaunchAgent daemons spawned by `launchd` run without interactive user TCC context, so macOS silently blocks background processes from accessing protected user directories like `~/Downloads/`, `~/Documents/`, and `~/Desktop/`.
- **Architectural Solution**:
  - Relocated project execution out of `~/Downloads/` into a dedicated directory in user home: `~/VoiceBridge/voicebridge.py`.
  - Authored a clean LaunchAgent plist (`com.user.voicebridge.plist`) with `<key>RunAtLoad</key><true/>` and `<key>KeepAlive</key><true/>`.
  - Documented one-time macOS Accessibility permission requirements under **System Settings > Privacy & Security > Accessibility** for the running terminal/executable.

---

## [v0.5.0] - 2026-09-25 &bull; 04:45
### Dual Directionality &bull; Host-Aware Routing & Real-Time Sync

- **Context**: A phone-to-Mac dictation pipe solved 50% of the workflow friction. However, moving links, code snippets, and instructions from the Mac back to the phone still required emailing oneself or using cloud chat apps.
- **Architectural Enhancements**:
  - **Host Autodetection**: Configured the HTTP request handler to inspect client IP addresses. If the client connects via `127.0.0.1`, `::1`, or the Mac's own local IP, the UI automatically adapts into **Host Mode** with a primary `SEND TO PHONE` action. Mobile clients default to **Client Mode** with `SEND TO MAC`.
  - **In-Memory Notification Buffer**: Added thread-safe message mailboxes (`SERVER_STATE["phone_msg"]` and `SERVER_STATE["mac_msg"]`) with incremental IDs and timestamps.
  - **Long-Polling Synchronization**: Implemented the `/poll?after=<id>` endpoint. Mobile devices maintain an efficient, low-overhead HTTP poll connection that immediately returns when a new payload is broadcast from the Mac host.
  - **Mobile Action Card**: Receiving a payload on mobile surfaces a non-intrusive bottom notification card offering one-tap `COPY TO CLIPBOARD` or `INSERT TO BOX`.

---

## [v0.8.0] - 2026-09-25 &bull; 07:30
### Touch Ergonomics &bull; Zero Keyboard Collapse & Native Backspace

- **Context**: On mobile touchscreens, tapping any action button (`Send`, `Clear`, `Delete`) traditionally causes the browser textarea to lose focus, triggering the operating system to collapse the virtual keyboard. For continuous voice dictation with Rambler, having the keyboard close after every paste destroyed the flow.
- **Architectural Solutions**:
  - **Zero Keyboard Bounce**: Replaced standard click listeners with `pointerdown` handlers calling `e.preventDefault()`. Because pointerdown default behavior is intercepted before focus changes, tapping action buttons fires network requests while keeping the virtual keyboard open and the cursor position intact.
  - **Balanced Two-Row Mobile Layout**: Restructured the mobile header and input dock into a tight, ergonomic two-row layout that leaves maximum vertical real estate for text and keyboard. Placed real-time word and character counters alongside utility chips (`+ Bullet`, `+ Line`, `← Delete`).
  - **Native Hold-to-Repeat Backspace**: Re-engineered the `← Delete` utility chip to match native mobile keyboard backspace physics:
    - 400ms initial hold delay before repeating.
    - Continuous 50ms character deletion steps.
    - Progressive speed acceleration down to 25ms intervals.
    - Subtle haptic feedback ticks via `navigator.vibrate(8)` on deletion bursts without dropping focus or closing the Gboard microphone strip.

---

## [v0.9.0] - 2026-09-25 &bull; 09:45
### Persistence & Gesture UI &bull; History Drawer, Archiving & Swiping

- **Context**: Temporary speech errors or accidentally cleared texts risked permanent loss of ideas. The bridge needed persistent local storage without adding database engines or heavy disk I/O.
- **Architectural Solutions**:
  - **Dual-State Storage Engine**: Stored history in `~/.voicebridge/history.json`, maintaining two bounded collections: an active recent history list (last 60 entries) and an explicit long-term archive (last 100 entries).
  - **Touch Gesture Swipe Navigation**: Implemented touch-event gesture tracking on mobile history cards:
    - Right swipe (> 80px): Instantly moves the entry into the permanent Archive.
    - Left swipe (> 80px): Soft-deletes the entry.
    - Real-time CSS transform translation and resistance curves during swipe gestures.
  - **Instant Undo Toast System**: Added a floating non-blocking undo toast with a 5-second countdown timer allowing users to recover accidentally swiped or deleted items with zero friction.
  - **Export Capabilities**: Added one-tap `.txt` plain-text export for backing up entire dictation sessions or feeding them into external notes tools.

---

## [v1.0.0] - 2026-09-25 &bull; 11:30
### Production Lock-in &bull; The Zero-Watcher Architecture

- **Context**: A built-in Python file-polling loop (`file_watcher`) had been introduced during prototyping to auto-restart the server on file edits. However, running `os._exit(0)` from a background worker thread created race conditions when running under `launchd` and `nohup`, causing silent port hangs and orphan sockets.
- **Architectural Refinement**:
  - **Eliminated File Watcher**: Purged the fragile background file-watching thread entirely. Transferred process lifecycle management back to native Unix and macOS primitives:
    - `launchd` natively handles instant restarts when the process terminates via `<key>KeepAlive</key><true/>`.
    - Developers update the running daemon with a single clean command: `kill -9 $(lsof -ti :5050)`.
  - **ZeroG Architectural Compliance**:
    - Embedded the full mobile web application directly inside `voicebridge.py` as a single multi-line HTML/CSS/JS template.
    - Guaranteed zero build steps, zero external CDN requests, zero runtime heap bloat, and pure offline local-network operation.
    - Pre-allocated WebAudio synthesized beeps for feedback without bundling audio assets.
  - **Final Stability Lock-in**: Validated full pipeline from boot to dictation across macOS Sonoma/Sequoia and Android/iOS mobile devices.
