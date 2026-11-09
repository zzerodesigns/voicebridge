# VoiceBridge v1.0

A lightweight, zero-dependency local network bridge that turns any smartphone into an instantaneous voice-dictation and bidirectional clipboard controller for macOS.

---

## Overview

VoiceBridge allows you to dictate text using your smartphone's speech-to-text engine (Gboard, Apple Dictation, etc.) and have it instantly injected into whatever window or text field is currently active on your Mac. It also allows pushing text from your Mac back to your phone with a single click.

Unlike cloud-based tools or third-party apps:
- **Zero External Dependencies**: Runs entirely on Python 3 standard library tools built into macOS. No `pip install`, no Node.js, and no external binaries.
- **100% Private & Local**: Operates strictly within your local Wi-Fi network. No audio or text data ever leaves your machines.
- **True Instant Injection**: Instead of slow simulated typing, it uses native macOS clipboard injection (`pbcopy` + AppleScript `Cmd+V`) to paste entire multi-paragraph blocks in under a millisecond.
- **Platform Agnostic Client**: Works on any mobile device (Android, iOS) with a web browser.

---

## How It Works

```
┌─────────────────────────┐               Local Wi-Fi                ┌──────────────────────────┐
│      Mobile Device      │  ─────────── HTTP POST /paste ─────────> │        Mac Host          │
│ (Any Phone / Tablet)    │                                          │ (Python ThreadingServer) │
│                         │  <─────── HTTP GET /poll (Sync) ──────── │                          │
│ • Speech-to-Text Input  │                                          │ 1. Ingests payload       │
│ • WebAudio Sound Engine │  <─────── HTTP POST /send-to-phone ───── │ 2. Copies to `pbcopy`    │
│ • Touch-Docked UI       │                                          │ 3. Simulates `Cmd + V`   │
└─────────────────────────┘                                          └──────────────────────────┘
```

1. **Mac Host**: Runs a lightweight, multi-threaded Python server (`voicebridge.py`) listening on port `5050`.
2. **Mobile Client**: Serves a clean, mobile-optimized web app with a responsive textarea, persistent clipboard history, and touch-optimized controls.
3. **Injection Pipeline**: When text is submitted from the phone, the server writes the payload directly to the macOS clipboard via `pbcopy` and signals `System Events` to fire `Cmd + V` into whatever window has focus.

---

## Prerequisites

- **Mac Host**: macOS 10.14 (Mojave) or newer with Python 3.
- **Mobile Device**: Any smartphone or tablet connected to the same Wi-Fi network.
- **macOS Permissions**: Terminal (or Python) must be granted **Accessibility** permissions to allow keystroke simulation.

---

## Initial Setup (One-Time)

### 1. Grant Accessibility Permissions on Mac
To allow the script to execute `Cmd + V` into your active window:
1. Open **System Settings > Privacy & Security > Accessibility**.
2. Ensure your terminal application (e.g., **Terminal**, **iTerm2**, or your code editor) is toggled **ON**.

### 2. Recommended File Location
Place `voicebridge.py` in a dedicated directory inside your home folder, for example:
```text
~/VoiceBridge/voicebridge.py
```
> **Important macOS Security Note**: Do **not** place the file inside `~/Downloads`, `~/Documents`, or `~/Desktop` if you plan to run it as an automatic background service. macOS privacy sandbox rules (TCC) silently block background daemons from reading files inside those three specific folders. Using `~/VoiceBridge/` or any other user folder avoids this entirely.

---

## Running VoiceBridge

You have two choices for running VoiceBridge: **Manual/On-Demand** or **Automatic Background Service (Login Item)**.

### Option A: Running as an Automatic Background Service (Recommended)
This makes VoiceBridge start silently in the background every time your Mac turns on. It requires zero open terminal windows, automatically restarts if killed, and appears in **System Settings > General > Login Items & Extensions** under "Allow in the Background".

1. Register and start the background service with a single block in Terminal:
   ```bash
   mkdir -p "$HOME/Library/LaunchAgents"

   cat << 'EOF' > "$HOME/Library/LaunchAgents/com.user.voicebridge.plist"
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.user.voicebridge</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/bin/python3</string>
           <string>/Users/ethanfreeman/VoiceBridge/voicebridge.py</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   EOF

   launchctl unload "$HOME/Library/LaunchAgents/com.user.voicebridge.plist" 2>/dev/null
   launchctl load "$HOME/Library/LaunchAgents/com.user.voicebridge.plist"
   ```

2. Verify it is running:
   ```bash
   launchctl list | grep voicebridge
   ```
   *(A line showing a PID number followed by `0` confirms the service is active).*

**Managing the Background Service:**
- **To Restart after updating code**:
  ```bash
  kill -9 $(lsof -ti :5050)
  ```
- **To Stop / Disable**:
  ```bash
  launchctl unload "$HOME/Library/LaunchAgents/com.user.voicebridge.plist"
  ```

---

### Option B: Manual / On-Demand Execution
If you prefer running VoiceBridge only when needed without registering a persistent system service:

```bash
kill -9 $(lsof -ti :5050) 2>/dev/null; nohup python3 "$HOME/VoiceBridge/voicebridge.py" >/dev/null 2>&1 &
```
This frees port 5050, launches the server in the background, and lets you close the Terminal window.

---

## Connecting Your Phone

1. **Find your Mac's local IP address**:
   - Hold the `Option` key and click the **Wi-Fi icon** in your Mac's menu bar.
   - Look for **IP Address** (e.g., `192.168.1.45`).
   
   *Or run in Terminal:*
   ```bash
   ipconfig getifaddr en0
   ```

2. **Open the Web App on Your Phone**:
   - Open Chrome, Safari, or Brave on your phone.
   - Navigate to:
     ```text
     http://<YOUR-MAC-IP>:5050
     ```

3. **Install as a PWA / Web App (Recommended)**:
   - **Android (Chrome/Brave)**: Tap the menu (three dots) > **Add to Home Screen** / **Install App**.
   - **iOS (Safari)**: Tap the Share button > **Add to Home Screen**.
   - This opens VoiceBridge full-screen without browser address bars, behaving like a native application.

---

## Usage & Workflows

### Phone $\to$ Mac (Dictation)
1. On your Mac, place your text cursor inside any application (chat window, code editor, email client, document).
2. On your phone, open VoiceBridge.
3. Tap the text area and activate your keyboard's microphone (e.g., Gboard voice typing, Apple Dictation).
4. When finished speaking, tap **SEND TO MAC**.
5. The text will instantly paste into your active Mac window.

### Mac $\to$ Phone (Wireless Clipboard)
1. Open `http://localhost:5050` on your Mac browser. The interface will automatically recognize it is running on the host machine.
2. Type or paste any text or links into the box and click **SEND TO PHONE**.
3. On your phone, an incoming card will appear immediately with:
   - **COPY TO CLIPBOARD**: Copies the received text straight into your mobile clipboard.
   - **INSERT TO BOX**: Appends the text into the phone's text area.

---

## Features

- **Device-Aware Interface**: Automatically configures the UI depending on whether it is accessed from the Mac host (`SEND TO PHONE`) or a mobile device (`SEND TO MAC`).
- **Zero Keyboard Bounce**: Mobile touch handlers prevent the virtual keyboard from blurring/collapsing when tapping Send, allowing uninterrupted dictation sessions.
- **Instant Auto-Focus**: Automatically focuses the text area and positions the cursor on app launch so your keyboard pops open immediately with zero extra taps.
- **Balanced Two-Row Mobile Layout & Hold-to-Repeat Delete**: The live word/character counter sits directly beneath the text box level with the Delete chip. Holding Delete behaves identically to a native keyboard backspace—featuring an initial hold delay, rapid continuous deletion, speed acceleration, and subtle haptic ticks without dropping focus or closing the virtual keyboard.
- **Persistent Universal History & Archive**: Dual-view drawer for active history and long-term archiving saved in `~/.voicebridge/history.json`, complete with gesture swipe-to-dismiss, instant undo toast, export to `.txt`, and individual copy controls.
- **Adaptive System Theming**: Automatically synchronizes with system-level Light and Dark modes (`prefers-color-scheme`) with custom high-contrast palettes.
- **Local WebAudio Feedback**: Synthesizes soft status chimes directly via the browser's WebAudio API without loading external sound files.

---

## Troubleshooting

### "This site can't be reached" on mobile
1. Ensure both your Mac and your mobile device are connected to the exact same Wi-Fi network.
2. Verify that your router does not have "Client Isolation" or "Guest Mode" enabled, which prevents local devices from communicating.
3. Check if the macOS Application Firewall is blocking incoming connections:
   - Go to **System Settings > Network > Firewall**. If enabled, ensure Python is allowed to accept incoming connections.

### Text does not paste on the Mac
1. Ensure the window on your Mac is actively focused and has a blinking text cursor.
2. Verify Accessibility permissions:
   - Go to **System Settings > Privacy & Security > Accessibility**.
   - Ensure Terminal / Python has permissions toggled ON.

### Address already in use (`Errno 48`)
A previous instance is still holding port 5050. Run:
```bash
kill -9 $(lsof -ti :5050)
```