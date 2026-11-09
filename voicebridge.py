import os
import subprocess
import socket
import json
import time
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HISTORY_FILE = os.path.expanduser("~/.voicebridge/history.json")

def load_data():
    default_data = {"history": [], "archive": []}
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, list): return {"history": d, "archive": []}
                return d
    except Exception: pass
    return default_data

def save_data(data):
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"history": data.get("history", [])[:60], "archive": data.get("archive", [])[:100]}, f, ensure_ascii=False, indent=2)
    except Exception: pass

DATA_STORE = load_data()

SERVER_STATE = {
    "phone_msg": {"id": 0, "text": "", "time": ""},
    "mac_msg": {"id": 0, "text": "", "time": ""},
    "history": DATA_STORE.get("history", []),
    "archive": DATA_STORE.get("archive", [])
}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, interactive-widget=resizes-content">
    <meta name="color-scheme" content="light dark">
    <meta name="theme-color" content="#f8fafc" id="meta-theme-color">
    <title>VoiceBridge v1.0</title>
    <style>
        :root {
            --bg: #f8fafc; --panel: #ffffff; --panel-border: rgba(0, 0, 0, 0.09);
            --textarea-bg: #f1f5f9; --textarea-border: #cbd5e1;
            --accent: #1a73e8; --accent-hover: #1557b0; --accent-glow: rgba(26, 115, 232, 0.25);
            --accent-green: #0f9d58; --text: #0f172a; --text-dim: #64748b; --placeholder: #94a3b8;
            --card-bg: #e8f0fe; --card-border: #b3d7ff; --chip-bg: rgba(0, 0, 0, 0.05);
            --chip-border: rgba(0, 0, 0, 0.1); --chip-hover-bg: rgba(0, 0, 0, 0.09);
            --clear-hover-bg: #fee2e2; --clear-hover-border: #ef4444; --clear-hover-text: #b91c1c;
            --history-bg: #ffffff; --history-item-bg: #f8fafc;
            --scrollbar-thumb: rgba(0, 0, 0, 0.15); --scrollbar-thumb-hover: #1a73e8;
            --shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #070a0e; --panel: #0d141e; --panel-border: rgba(51, 204, 255, 0.2);
                --textarea-bg: #0a0f16; --textarea-border: rgba(51, 204, 255, 0.2);
                --accent: #0099ff; --accent-hover: #0080d5; --accent-glow: rgba(0, 153, 255, 0.4);
                --accent-green: #00ffaa; --text: #e6f0fa; --text-dim: #557799; --placeholder: #335577;
                --card-bg: rgba(0, 153, 255, 0.12); --card-border: rgba(0, 153, 255, 0.5);
                --chip-bg: rgba(10, 20, 30, 0.6); --chip-border: rgba(255, 255, 255, 0.1);
                --chip-hover-bg: rgba(255, 255, 255, 0.1); --clear-hover-bg: rgba(220, 38, 38, 0.2);
                --clear-hover-border: #ef4444; --clear-hover-text: #f87171;
                --history-bg: #070a0e; --history-item-bg: #0d141e;
                --scrollbar-thumb: rgba(255, 255, 255, 0.18); --scrollbar-thumb-hover: #0099ff;
                --shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
            }
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        html, body {
            width: 100%; min-height: 100%; height: 100%; background: var(--bg); color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            overscroll-behavior-y: auto !important; overflow-y: auto !important; overflow-x: hidden;
            transition: background-color 0.2s ease, color 0.2s ease;
        }
        #app-root {
            display: flex; flex-direction: column; width: 100%; height: 100dvh;
            position: relative; overflow: hidden; transition: height 0.18s cubic-bezier(0.2, 0.9, 0.3, 1);
        }
        header {
            display: flex; justify-content: space-between; align-items: center; padding: 12px 18px;
            background: var(--panel); border-bottom: 1px solid var(--panel-border); flex-shrink: 0;
            box-shadow: var(--shadow); z-index: 120;
        }
        .brand { display: flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 800; letter-spacing: 1.5px; text-transform: uppercase; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--accent-green); box-shadow: 0 0 10px var(--accent-green); }
        .version-tag { font-size: 10px; color: var(--accent); font-weight: 800; background: var(--chip-bg); padding: 2px 6px; border-radius: 4px; border: 1px solid var(--panel-border); letter-spacing: 0.5px; text-transform: none; }
        .header-actions { display: flex; gap: 8px; align-items: center; }
        .icon-btn { background: var(--chip-bg); border: 1px solid var(--panel-border); color: var(--text); width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 18px; font-weight: 700; line-height: 1; transition: all 0.2s ease; }
        .icon-btn:hover { box-shadow: 0 0 10px var(--accent-glow); border-color: var(--accent); color: var(--accent); background: var(--chip-hover-bg); }
        .icon-btn:active { transform: scale(0.95); }
        .btn-header { background: var(--chip-bg); border: 1px solid var(--panel-border); color: var(--text); font-size: 12px; font-weight: 800; letter-spacing: 0.5px; height: 36px; width: 88px; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease; text-align: center; }
        .btn-header:hover { box-shadow: 0 0 10px var(--accent-glow); border-color: var(--accent); background: var(--chip-hover-bg); }
        .btn-header:active { transform: scale(0.97); }
        .btn-header.active-close { background: rgba(220, 38, 38, 0.12); border-color: rgba(220, 38, 38, 0.4); color: #ef4444; }
        
        #incoming-card { display: none; margin: 12px 14px 0 14px; padding: 14px 16px; border-radius: 12px; background: var(--card-bg); border: 1px solid var(--card-border); flex-direction: column; gap: 10px; flex-shrink: 0; box-shadow: var(--shadow); animation: slideDown 0.2s ease-out; }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
        .incoming-header { display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 800; color: var(--accent); letter-spacing: 1px; text-transform: uppercase; }
        .incoming-body { font-size: 15px; line-height: 1.45; max-height: 120px; overflow-y: auto; word-break: break-word; user-select: text !important; -webkit-user-select: text !important; color: var(--text); }
        .incoming-actions { display: flex; gap: 8px; }
        .incoming-btn { flex: 1; padding: 10px 14px; font-size: 13px; border-radius: 8px; border: 1px solid var(--accent); background: var(--accent); color: #fff; font-weight: 800; cursor: pointer; letter-spacing: 0.5px; text-align: center; transition: all 0.2s ease; }
        .incoming-btn:active { transform: scale(0.97); }
        .incoming-btn.secondary { background: var(--panel); border-color: var(--panel-border); color: var(--text); }
        .incoming-btn.success { background: #00c853 !important; border-color: #00c853 !important; }

        main { flex: 1; display: flex; flex-direction: column; padding: 12px 14px 4px 14px; gap: 8px; min-height: 0; }
        .textarea-wrapper { flex: 1; display: flex; min-height: 0; }
        textarea { flex: 1; width: 100%; background: var(--textarea-bg); border: 1px solid var(--textarea-border); border-radius: 14px; color: var(--text); font-size: 17px; line-height: 1.55; padding: 16px; outline: none; resize: none; font-family: inherit; user-select: text !important; -webkit-user-select: text !important; -webkit-appearance: none; scroll-behavior: smooth; }
        textarea:focus { border-color: var(--accent); }
        textarea::placeholder { color: var(--placeholder); font-size: 16px; }

        /* Mapped utility row: counter on top left below textarea, stacked chips on right */
        .utility-row { display: flex; justify-content: space-between; align-items: flex-start; padding: 2px 2px; flex-shrink: 0; }
        .tag-counter { font-size: 11px; font-family: monospace; color: var(--text-dim); background: var(--chip-bg); padding: 6px 10px; border-radius: 8px; border: 1px solid var(--panel-border); font-weight: 600; margin-top: 1px; margin-bottom: 0; }
        .right-chips { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
        .chip-row { display: flex; gap: 6px; }
        .chip { display: inline-flex; align-items: center; justify-content: center; gap: 5px; background: var(--chip-bg); border: 1px solid var(--chip-border); color: var(--text); font-size: 11px; font-family: monospace; padding: 6px 14px; border-radius: 8px; cursor: pointer; white-space: nowrap; font-weight: 700; transition: all 0.2s ease; user-select: none; -webkit-user-select: none; -webkit-touch-callout: none; }
        .chip:hover { box-shadow: 0 0 8px var(--accent-glow); border-color: var(--accent); background: var(--chip-hover-bg); }
        .chip:active { transform: scale(0.96); background: var(--accent); color: #fff; }

        footer { display: flex; gap: 10px; padding: 6px 14px 14px 14px; flex-shrink: 0; }
        button { border: none; border-radius: 12px; font-weight: 800; cursor: pointer; font-family: inherit; }
        .btn-clear { background: var(--panel); border: 1px solid var(--panel-border); color: var(--text-dim); font-size: 13px; padding: 0 18px; height: 56px; min-width: 70px; transition: all 0.2s ease; }
        .btn-clear:hover { background: var(--clear-hover-bg); border-color: var(--clear-hover-border); color: var(--clear-hover-text); box-shadow: 0 0 10px rgba(239, 68, 68, 0.25); }
        .btn-clear:active { transform: scale(0.96); }
        #send-btn { flex: 1; height: 56px; background: var(--accent); color: #fff; font-size: 17px; letter-spacing: 1px; text-transform: uppercase; box-shadow: 0 4px 14px var(--accent-glow); transition: all 0.2s ease; }
        #send-btn:hover { background: var(--accent-hover); box-shadow: 0 0 20px var(--accent-glow); filter: brightness(1.06); }
        #send-btn:active { transform: scale(0.98); }
        #send-btn.success { background: #00c853 !important; box-shadow: 0 0 20px rgba(0, 200, 83, 0.5) !important; }

        #history-sheet { position: absolute; top: 61px; bottom: 0; left: 0; right: 0; background: var(--history-bg); display: none; flex-direction: column; z-index: 110; overflow-x: hidden !important; animation: fadeIn 0.15s ease-out; }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        #history-sheet.open { display: flex; }
        .drawer-sub-header { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px 10px 18px; flex-shrink: 0; }
        .drawer-title { font-weight: 800; letter-spacing: 1px; font-size: 13px; color: var(--text-dim); text-transform: uppercase; }
        .drawer-top-action { background: var(--chip-bg); border: 1px solid var(--panel-border); color: var(--accent); font-size: 11px; font-weight: 800; padding: 6px 12px; border-radius: 6px; cursor: pointer; transition: all 0.2s ease; }
        .history-list { flex: 1; overflow-y: auto; overflow-x: hidden !important; display: flex; flex-direction: column; padding: 4px 18px 14px 18px; scrollbar-width: thin; scrollbar-color: var(--scrollbar-thumb) transparent; }
        .history-list::-webkit-scrollbar { width: 5px; }
        .history-list::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 4px; }
        .history-item-wrapper { flex-shrink: 0 !important; margin-bottom: 12px; position: relative; overflow: visible; border-radius: 12px; transition: max-height 0.26s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease, margin-bottom 0.26s cubic-bezier(0.4, 0, 0.2, 1); }
        .history-item-wrapper.collapsing { overflow: hidden !important; }
        .history-item-wrapper.restoring { animation: cardRestoreIn 0.28s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
        @keyframes cardRestoreIn { from { max-height: 0; opacity: 0; transform: scale(0.96); margin-bottom: 0; } to { max-height: 250px; opacity: 1; transform: scale(1); margin-bottom: 12px; } }
        .swipe-underlay { position: absolute; inset: 0; display: flex; justify-content: space-between; align-items: center; padding: 0 22px; font-size: 11px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; border-radius: 12px; pointer-events: none; background: #0f172a; }
        .underlay-left { color: #0099ff; opacity: 0.35; transition: opacity 0.15s ease, transform 0.15s ease; display: inline-flex; align-items: center; gap: 7px; line-height: 1; }
        .underlay-right { color: #ef4444; opacity: 0.35; transition: opacity 0.15s ease, transform 0.15s ease; display: inline-flex; align-items: center; gap: 7px; line-height: 1; }
        .underlay-left.primed, .underlay-right.primed { opacity: 1; transform: scale(1.08); }
        .history-item { flex-shrink: 0 !important; background: var(--history-item-bg); border: 1px solid var(--panel-border); border-radius: 12px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; box-shadow: var(--shadow); position: relative; z-index: 2; cursor: pointer; transition: border-color 0.2s ease; touch-action: pan-y; }
        .history-item:hover { border-color: var(--accent); }
        .history-meta { display: flex; justify-content: space-between; align-items: center; font-size: 11px; font-weight: 700; color: var(--accent); }
        .history-meta-right { font-size: 11px; color: var(--text-dim); font-family: monospace; }
        .history-text { font-size: 14px; line-height: 1.5; color: var(--text); user-select: text !important; -webkit-user-select: text !important; word-break: break-word; }
        .history-actions { display: flex; justify-content: space-between; align-items: center; width: 100%; margin-top: 2px; }
        .history-left-group { display: flex; gap: 6px; align-items: center; }
        .card-btn { background: var(--chip-bg); border: 1px solid var(--panel-border); color: var(--text); font-size: 11px; font-weight: 700; padding: 6px 14px; border-radius: 6px; cursor: pointer; transition: all 0.15s ease; }
        .card-btn.copy { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 800; letter-spacing: 0.5px; }
        .card-btn.delete { color: var(--text-dim); }
        .card-btn.archive-desktop { color: var(--text-dim); display: none; }
        @media (hover: hover) and (pointer: fine) { .card-btn.archive-desktop { display: inline-block; } .history-actions { opacity: 0.7; transition: opacity 0.15s ease; } .history-item:hover .history-actions { opacity: 1; } }
        .drawer-bottom-bar { padding: 12px 18px; background: var(--panel); border-top: 1px solid var(--panel-border); display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.05); z-index: 10; }
        .btn-bottom-action { background: var(--chip-bg); border: 1px solid var(--panel-border); color: var(--text); font-size: 11px; font-weight: 800; padding: 10px 14px; border-radius: 8px; cursor: pointer; letter-spacing: 0.5px; transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; gap: 7px; line-height: 1; text-align: center; }
        .btn-bottom-action.left-btn { width: 145px; } .btn-bottom-action.right-btn { width: 140px; }
        .btn-bottom-action.danger { background: rgba(220, 38, 38, 0.08); border-color: rgba(220, 38, 38, 0.25); color: #ef4444; }
        .arrow-glyph { font-size: 15px; font-weight: 900; line-height: 1; display: inline-flex; align-items: center; justify-content: center; transform: translateY(-0.5px); }
        
        #toast {
            position: fixed; bottom: 85px; left: 50%; transform: translateX(-50%) translateY(14px);
            opacity: 0; visibility: hidden; pointer-events: none;
            background: var(--panel); border: 1px solid var(--panel-border); color: var(--text);
            padding: 10px 18px; border-radius: 10px; font-size: 13px; font-weight: 700;
            display: flex; align-items: center; gap: 14px; box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            z-index: 200; transition: opacity 0.2s ease, transform 0.25s cubic-bezier(0.16, 1, 0.3, 1), visibility 0.2s;
            white-space: nowrap; max-width: 90vw; user-select: none !important; -webkit-user-select: none !important; -webkit-touch-callout: none !important;
        }
        #toast.show { opacity: 1; visibility: visible; pointer-events: auto; transform: translateX(-50%) translateY(0); }
        .toast-undo { color: var(--accent); background: none; border: none; font-size: 13px; font-weight: 800; cursor: pointer; text-transform: uppercase; touch-action: manipulation; user-select: none !important; -webkit-user-select: none !important; -webkit-tap-highlight-color: transparent; outline: none; }
    </style>
</head>
<body>
    <div id="app-root">
        <header>
            <div class="brand"><div class="status-dot"></div>VoiceBridge<span class="version-tag">v1.0</span></div>
            <div class="header-actions">
                <button class="icon-btn" onclick="window.location.reload()">&#x21bb;</button>
                <button class="btn-header" id="history-toggle-btn" onclick="toggleHistoryDrawer()">HISTORY</button>
            </div>
        </header>

        <div id="incoming-card">
            <div class="incoming-header"><span>Received from Mac</span><span style="font-size:18px; cursor:pointer; padding:2px 8px;" onclick="closeIncoming()">&#x2715;</span></div>
            <div class="incoming-body" id="incoming-text"></div>
            <div class="incoming-actions">
                <button class="incoming-btn" id="copy-btn" onclick="copyIncoming()">COPY TO CLIPBOARD</button>
                <button class="incoming-btn secondary" onclick="insertIncoming()">INSERT TO BOX</button>
            </div>
        </div>

        <main>
            <div class="textarea-wrapper"><textarea id="input" autofocus></textarea></div>
            <div class="utility-row">
                <div class="tag-counter" id="counter">0w &bull; 0c</div>
                <div class="right-chips">
                    <div class="chip-row">
                        <button class="chip delete-chip" id="delete-btn" onpointerdown="startDelete(event)" onpointerup="stopDelete(event)" onpointerleave="stopDelete(event)" onpointercancel="stopDelete(event)" oncontextmenu="event.preventDefault()"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="transform:translateY(-0.5px);"><path d="M19 12H5M12 19l-7-7 7-7"/></svg><span>Delete</span></button>
                    </div>
                    <div class="chip-row">
                        <button class="chip" onpointerdown="event.preventDefault()" onclick="insertText('&bull; ')">+ Bullet</button>
                        <button class="chip" onpointerdown="event.preventDefault()" onclick="insertText('\\n')">+ Line</button>
                    </div>
                </div>
            </div>
        </main>

        <footer>
            <button class="btn-clear" onclick="clearText()">CLEAR</button>
            <button id="send-btn" onpointerdown="handlePointerDown(event)" onclick="handleSend()">SEND TO MAC</button>
        </footer>

        <div id="history-sheet">
            <div class="drawer-sub-header">
                <div class="drawer-title" id="drawer-view-title">CLIPBOARD HISTORY</div>
                <button class="drawer-top-action" id="drawer-top-action" style="display:none;" onclick="exportArchive()">EXPORT (.TXT)</button>
            </div>
            <div class="history-list" id="drawer-items"></div>
            <div class="drawer-bottom-bar" id="drawer-bottom-bar"></div>
        </div>
    </div>

    <div id="toast"><span id="toast-text">Action completed</span><button class="toast-undo" onclick="undoAction()">UNDO</button></div>

    <script>
        const input = document.getElementById('input');
        const counter = document.getElementById('counter');
        const sendBtn = document.getElementById('send-btn');
        const incomingCard = document.getElementById('incoming-card');
        const incomingText = document.getElementById('incoming-text');
        const historySheet = document.getElementById('history-sheet');
        const drawerItems = document.getElementById('drawer-items');
        const drawerBottomBar = document.getElementById('drawer-bottom-bar');
        const drawerTitle = document.getElementById('drawer-view-title');
        const historyToggleBtn = document.getElementById('history-toggle-btn');
        const toast = document.getElementById('toast');
        const toastText = document.getElementById('toast-text');

        let lastSeenId = 0, activeHistory = [], archivedHistory = [], currentDrawerView = 'history', isDrawerOpen = false;
        let lastActionBuffer = null, toastTimeout = null;

        const isMac = !/Android|iPhone|iPad|Mobile/i.test(navigator.userAgent);
        const SVG_ARROW_RIGHT = '<svg class="arrow-svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
        const SVG_ARROW_LEFT = '<svg class="arrow-svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>';

        if (isMac) { sendBtn.innerText = "SEND TO PHONE"; input.placeholder = "Type or paste on Mac to push over to your phone..."; } 
        else { sendBtn.innerText = "SEND TO MAC"; input.placeholder = "Tap mic on Gboard to dictate..."; }

        function handlePointerDown(e) { if (!isMac) e.preventDefault(); }

        const themeQuery = window.matchMedia('(prefers-color-scheme: dark)');
        function applyThemeMeta(e) { const m = document.getElementById('meta-theme-color'); if(m) m.setAttribute('content', e.matches ? '#070a0e' : '#f8fafc'); }
        themeQuery.addEventListener('change', applyThemeMeta); applyThemeMeta(themeQuery);

        function copyToClipboard(text) {
            if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
            return fallbackCopy(text);
        }
        function fallbackCopy(text) {
            const ta = document.createElement("textarea"); ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
            document.body.appendChild(ta); ta.focus(); ta.select();
            try { document.execCommand('copy'); return Promise.resolve(); } catch(e) { return Promise.reject(e); } finally { document.body.removeChild(ta); }
        }

        input.addEventListener('input', updateCount);
        function updateCount() {
            const v = input.value.trim(), c = input.value.length, w = v ? v.split(/\\s+/).length : 0;
            counter.innerHTML = `${w}w &bull; ${c}c`;
        }

        function clearText() { input.value = ''; updateCount(); input.focus(); }
        
        function insertText(str) {
            const s = input.selectionStart, e = input.selectionEnd;
            input.value = input.value.substring(0, s) + str + input.value.substring(e);
            input.selectionStart = input.selectionEnd = s + str.length;
            updateCount(); scrollToCursor();
        }

        let deleteTimer = null, deleteInterval = null, deleteCount = 0;

        function deleteLastChar() {
            const s = input.selectionStart, e = input.selectionEnd;
            if (s > 0 || s !== e) {
                if (s === e) {
                    input.value = input.value.substring(0, s - 1) + input.value.substring(e);
                    input.selectionStart = input.selectionEnd = s - 1;
                } else {
                    input.value = input.value.substring(0, s) + input.value.substring(e);
                    input.selectionStart = input.selectionEnd = s;
                }
                updateCount(); scrollToCursor();
                if (navigator.vibrate) navigator.vibrate(8);
            }
        }

        function startDelete(e) {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            stopDelete();
            deleteLastChar();
            deleteCount = 1;
            deleteTimer = setTimeout(() => {
                let intervalMs = 60;
                deleteInterval = setInterval(() => {
                    deleteLastChar();
                    deleteCount++;
                    if (deleteCount > 12 && intervalMs > 30) {
                        clearInterval(deleteInterval);
                        intervalMs = 30;
                        deleteInterval = setInterval(deleteLastChar, intervalMs);
                    }
                }, intervalMs);
            }, 380);
        }

        function stopDelete(e) {
            if (deleteTimer) { clearTimeout(deleteTimer); deleteTimer = null; }
            if (deleteInterval) { clearInterval(deleteInterval); deleteInterval = null; }
            deleteCount = 0;
        }

        function scrollToCursor() { requestAnimationFrame(() => { input.scrollTop = input.scrollHeight; }); }

        function handleSend() {
            const text = input.value; if (!text.trim()) return;
            if (navigator.vibrate) navigator.vibrate(30);
            sendBtn.classList.add('success'); const o = sendBtn.innerText;
            if (isMac) {
                sendBtn.innerText = 'SENT TO PHONE!';
                fetch('/send-to-phone', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text}) }).then(() => { setTimeout(() => { sendBtn.classList.remove('success'); sendBtn.innerText = o; }, 1000); });
            } else {
                sendBtn.innerText = 'SENT!';
                fetch('/paste', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text}) }).then(() => { input.value = ''; updateCount(); setTimeout(() => { sendBtn.classList.remove('success'); sendBtn.innerText = o; }, 400); });
            }
        }

        function pollSync() {
            fetch('/poll').then(r=>r.json()).then(d => {
                if(d && !isMac) { const m = d.phone_msg; if(m && m.id > lastSeenId && m.text) { lastSeenId = m.id; showIncoming(m.text); } }
            }).catch(()=>{}).finally(()=>setTimeout(pollSync, 1000));
        } pollSync();

        function showIncoming(txt) { incomingText.innerText = txt; incomingCard.style.display = 'flex'; if(navigator.vibrate) navigator.vibrate([30,40,30]); }
        function closeIncoming() { incomingCard.style.display = 'none'; }
        function copyIncoming() { copyToClipboard(incomingText.innerText).then(() => { const b = document.getElementById('copy-btn'); b.innerText = 'COPIED!'; b.classList.add('success'); setTimeout(()=>{b.innerText='COPY TO CLIPBOARD';b.classList.remove('success');}, 900); }); }
        function insertIncoming() { insertText(incomingText.innerText); closeIncoming(); }

        function toggleHistoryDrawer() {
            isDrawerOpen = !isDrawerOpen;
            if (isDrawerOpen) {
                historyToggleBtn.innerText = 'CLOSE'; historyToggleBtn.classList.add('active-close');
                fetch('/history').then(r=>r.json()).then(d => { activeHistory = d.history || []; archivedHistory = d.archive || []; renderDrawerView(); historySheet.classList.add('open'); });
            } else {
                historyToggleBtn.innerText = 'HISTORY'; historyToggleBtn.classList.remove('active-close'); historySheet.classList.remove('open'); currentDrawerView = 'history';
                setTimeout(() => { input.focus(); input.selectionStart = input.selectionEnd = input.value.length; scrollToCursor(); }, 50);
            }
        }

        function switchDrawerView(v) { currentDrawerView = v; renderDrawerView(); }

        function renderDrawerView(restoredId = null) {
            const isArc = currentDrawerView === 'archive', items = isArc ? archivedHistory : activeHistory;
            drawerTitle.innerText = isArc ? 'ARCHIVED MESSAGES' : 'CLIPBOARD HISTORY';
            document.getElementById('drawer-top-action').style.display = isArc ? 'block' : 'none';

            if (items.length === 0) { drawerItems.innerHTML = `<div style="color:var(--text-dim); text-align:center; margin-top:40px; font-size:13px;">${isArc ? 'No archived messages.' : 'No active history yet.'}</div>`; } 
            else {
                drawerItems.innerHTML = items.map((it, idx) => {
                    const words = it.text.trim() ? it.text.trim().split(/\\s+/).length : 0, chars = it.text.length, rc = (it.id === restoredId) ? 'restoring' : '';
                    return `<div class="history-item-wrapper ${rc}" id="history-wrapper-${it.id}">
                        <div class="swipe-underlay"><span class="underlay-left" id="ul-${it.id}"><span>ARCHIVE</span>${SVG_ARROW_RIGHT}</span><span class="underlay-right" id="ur-${it.id}">${SVG_ARROW_LEFT}<span>DELETE</span></span></div>
                        <div class="history-item" id="history-card-${it.id}" ${!isMac ? `ontouchstart="handleTouchStart(event, ${it.id})" ontouchmove="handleTouchMove(event, ${it.id})" ontouchend="handleTouchEnd(event, ${it.id})"` : ''}>
                            <div class="history-meta"><span>FROM ${it.from.toUpperCase()} &bull; ${words}w ${chars}c</span><span class="history-meta-right">${it.time}</span></div>
                            <div class="history-text" onclick="handleCardClick(${idx})">${escapeHtml(it.text)}</div>
                            <div class="history-actions"><div class="history-left-group"><button class="card-btn delete" onclick="event.stopPropagation(); triggerDismissAnimation(${it.id}, 'delete')">DELETE</button>${(!isArc && isMac) ? `<button class="card-btn archive-desktop" onclick="event.stopPropagation(); triggerDismissAnimation(${it.id}, 'archive')">ARCHIVE</button>` : ''}</div><button class="card-btn copy" onclick="event.stopPropagation(); copyHistoryText('${escapeJsString(it.text)}', this)">COPY</button></div>
                        </div></div>`;
                }).join('');
            }
            if (isArc) drawerBottomBar.innerHTML = `<button class="btn-bottom-action left-btn danger" onclick="clearScope('archive')">CLEAR ARCHIVE</button><button class="btn-bottom-action right-btn secondary" onclick="switchDrawerView('history')">${SVG_ARROW_LEFT} BACK</button>`;
            else drawerBottomBar.innerHTML = `<button class="btn-bottom-action left-btn danger" onclick="clearScope('history')">CLEAR HISTORY</button><button class="btn-bottom-action right-btn secondary" onclick="switchDrawerView('archive')">ARCHIVE (${archivedHistory.length}) ${SVG_ARROW_RIGHT}</button>`;
        }

        function handleCardClick(idx) {
            const it = (currentDrawerView === 'archive' ? archivedHistory : activeHistory)[idx];
            if(it) { input.value = it.text; updateCount(); copyToClipboard(it.text); isDrawerOpen=false; historyToggleBtn.innerText='HISTORY'; historyToggleBtn.classList.remove('active-close'); historySheet.classList.remove('open'); currentDrawerView='history'; showToast("Loaded & Copied"); }
        }

        function copyHistoryText(t, b) { copyToClipboard(t).then(() => { b.innerText='COPIED!'; b.classList.add('success'); setTimeout(()=>{b.innerText='COPY';b.classList.remove('success');}, 800); }); }

        function triggerDismissAnimation(id, act) {
            const c = document.getElementById(`history-card-${id}`), w = document.getElementById(`history-wrapper-${id}`); if(!c||!w) return;
            w.style.maxHeight = w.offsetHeight + 'px'; w.classList.add('collapsing');
            c.style.transition = isMac ? 'transform 0.35s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.28s ease' : 'transform 0.24s cubic-bezier(0.2, 0.9, 0.3, 1)';
            c.style.transform = act === 'delete' ? (isMac ? 'translateX(-40px)' : 'translateX(-110%)') : (isMac ? 'translateX(40px)' : 'translateX(110%)');
            if(isMac) c.style.opacity = '0';
            setTimeout(() => { w.style.maxHeight='0px'; w.style.marginBottom='0px'; w.style.opacity='0'; setTimeout(()=>{ if(act==='delete') deleteItem(id); else archiveItem(id); }, 240); }, isMac ? 60 : 25);
        }

        let tsX=0, tsY=0, isH=false, activeId=null, hHap=false;
        function handleTouchStart(e, id) { tsX=e.touches[0].clientX; tsY=e.touches[0].clientY; isH=false; hHap=false; activeId=id; const c=document.getElementById(`history-card-${id}`); if(c) c.style.transition='none'; }
        function handleTouchMove(e, id) {
            if(activeId!==id) return; const dx=e.touches[0].clientX-tsX, dy=e.touches[0].clientY-tsY;
            if(!isH && Math.abs(dx)>8) { if(Math.abs(dx)>Math.abs(dy)) isH=true; }
            if(isH) {
                if(e.cancelable) e.preventDefault();
                const c = document.getElementById(`history-card-${id}`), ul = document.getElementById(`ul-${id}`), ur = document.getElementById(`ur-${id}`);
                if(c) {
                    let fx = dx;
                    if(dx < -75) { fx = -75 + (dx + 75) * 0.4; if(!hHap && navigator.vibrate) { navigator.vibrate(15); hHap=true; } if(ur) ur.classList.add('primed'); }
                    else if(dx > 75) { fx = 75 + (dx - 75) * 0.4; if(!hHap && currentDrawerView==='history' && navigator.vibrate) { navigator.vibrate(15); hHap=true; } if(ul) ul.classList.add('primed'); }
                    else { hHap=false; if(ur) ur.classList.remove('primed'); if(ul) ul.classList.remove('primed'); }
                    c.style.transform = `translateX(${fx}px)`;
                }
            }
        }
        function handleTouchEnd(e, id) {
            if(activeId!==id) return; activeId=null; const c=document.getElementById(`history-card-${id}`); if(!c) return;
            const mx = new WebKitCSSMatrix(window.getComputedStyle(c).transform).m41;
            if(mx < -75) triggerDismissAnimation(id, 'delete'); else if(mx > 75 && currentDrawerView==='history') triggerDismissAnimation(id, 'archive'); else { c.style.transition = 'transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)'; c.style.transform = 'translateX(0)'; }
        }

        function archiveItem(id) { const ix=activeHistory.findIndex(i=>i.id===id); if(ix===-1)return; const it=activeHistory[ix]; activeHistory.splice(ix,1); archivedHistory.unshift(it); renderDrawerView(); fetch('/history/archive',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}); lastActionBuffer={action:'archive',item:it,index:ix}; showToast("Archived"); }
        function deleteItem(id) { const isArc=currentDrawerView==='archive', l=isArc?archivedHistory:activeHistory, ix=l.findIndex(i=>i.id===id); if(ix===-1)return; const it=l[ix]; l.splice(ix,1); renderDrawerView(); fetch('/history/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,from_archive:isArc})}); lastActionBuffer={action:'delete',item:it,index:ix,wasArchive:isArc}; showToast("Deleted"); }
        function clearScope(scp) { const isArc=scp==='archive', itms=isArc?[...archivedHistory]:[...activeHistory]; if(itms.length===0)return; lastActionBuffer={action:'clear',target:scp,items:itms}; if(isArc) archivedHistory=[]; else activeHistory=[]; renderDrawerView(); fetch('/history/clear',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:scp})}); showToast(isArc?"Archive cleared":"History cleared"); }
        
        function undoAction() {
            if(!lastActionBuffer) return; const b = lastActionBuffer;
            if(b.action==='delete') { const l=b.wasArchive?archivedHistory:activeHistory; l.splice(b.index,0,b.item); renderDrawerView(b.item.id); fetch('/history/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item:b.item,target:b.wasArchive?'archive':'history'})}); }
            else if(b.action==='archive') { archivedHistory=archivedHistory.filter(i=>i.id!==b.item.id); activeHistory.splice(b.index,0,b.item); renderDrawerView(b.item.id); fetch('/history/restore',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item:b.item,target:'history',remove_from_archive:true})}); }
            else if(b.action==='clear') { if(b.target==='archive') archivedHistory=b.items; else activeHistory=b.items; renderDrawerView(); fetch('/history/restore-all',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({target:b.target,items:b.items})}); }
            hideToast(); if(navigator.vibrate) navigator.vibrate(25);
        }

        function showToast(t) { toastText.innerText=t; toast.classList.add('show'); if(toastTimeout) clearTimeout(toastTimeout); toastTimeout=setTimeout(hideToast, 5000); }
        function hideToast() { toast.classList.remove('show'); lastActionBuffer=null; }
        function exportArchive() { if(archivedHistory.length===0)return; const f=archivedHistory.map(i=>`[${i.time}] FROM ${i.from.toUpperCase()}:\\n${i.text}\\n`).join('\\n---\\n\\n'), b=new Blob([f],{type:'text/plain;charset=utf-8'}), u=URL.createObjectURL(b), a=document.createElement('a'); a.href=u; a.download=`voicebridge-archive-${new Date().toISOString().slice(0,10)}.txt`; document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(u); }
        function escapeHtml(s) { return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#039;"); }
        function escapeJsString(s) { return s.replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'").replace(/"/g,'\\\\"').replace(/\\n/g,'\\\\n').replace(/\\r/g,'\\\\r'); }

        function focusInput() {
            if (input) {
                input.focus();
                input.selectionStart = input.selectionEnd = input.value.length;
            }
        }
        focusInput();
        window.addEventListener('DOMContentLoaded', () => { setTimeout(focusInput, 60); setTimeout(focusInput, 250); });
    </script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def send_no_cache_headers(self, content_type='text/html; charset=utf-8', status=200):
        self.send_response(status)
        self.send_header('Content-type', content_type)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Connection', 'close')
        self.end_headers()

    def do_GET(self):
        if self.path.startswith('/poll'):
            self.send_no_cache_headers('application/json')
            self.wfile.write(json.dumps({"phone_msg": SERVER_STATE["phone_msg"], "mac_msg": SERVER_STATE["mac_msg"]}).encode('utf-8'))
        elif self.path == '/history':
            self.send_no_cache_headers('application/json')
            self.wfile.write(json.dumps({"history": SERVER_STATE["history"], "archive": SERVER_STATE["archive"]}).encode('utf-8'))
        else:
            self.send_no_cache_headers('text/html; charset=utf-8')
            self.wfile.write(HTML.encode('utf-8'))

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length).decode('utf-8')) if length > 0 else {}

        if self.path == '/paste':
            text = body.get('text', '')
            if text:
                p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                p.communicate(text.encode('utf-8'))
                subprocess.run(['osascript', '-e', 'tell application "System Events" to keystroke "v" using command down'])
                cur_id = int(time.time() * 1000)
                now_str = time.strftime("%H:%M:%S")
                SERVER_STATE["mac_msg"] = {"id": cur_id, "text": text, "time": now_str}
                SERVER_STATE["history"].insert(0, {"id": cur_id, "text": text, "from": "phone", "time": now_str})
                save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == '/send-to-phone':
            text = body.get('text', '')
            if text:
                cur_id = int(time.time() * 1000)
                now_str = time.strftime("%H:%M:%S")
                SERVER_STATE["phone_msg"] = {"id": cur_id, "text": text, "time": now_str}
                SERVER_STATE["history"].insert(0, {"id": cur_id, "text": text, "from": "mac", "time": now_str})
                save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(json.dumps({"status": "ok", "id": cur_id}).encode('utf-8'))

        elif self.path == '/history/archive':
            msg_id = body.get('id')
            item = next((it for it in SERVER_STATE["history"] if it.get("id") == msg_id), None)
            if item:
                SERVER_STATE["history"] = [it for it in SERVER_STATE["history"] if it.get("id") != msg_id]
                SERVER_STATE["archive"].insert(0, item)
                save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == '/history/delete':
            msg_id = body.get('id')
            target = "archive" if body.get('from_archive', False) else "history"
            SERVER_STATE[target] = [it for it in SERVER_STATE[target] if it.get("id") != msg_id]
            save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == '/history/restore':
            item = body.get('item')
            target = body.get('target', 'history')
            if item:
                if body.get('remove_from_archive', False):
                    SERVER_STATE["archive"] = [it for it in SERVER_STATE["archive"] if it.get("id") != item.get("id")]
                SERVER_STATE[target].insert(0, item)
                save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == '/history/restore-all':
            SERVER_STATE[body.get('target', 'history')] = body.get('items', [])
            save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(b'{"status":"ok"}')

        elif self.path == '/history/clear':
            SERVER_STATE[body.get('target', 'history')] = []
            save_data(SERVER_STATE)
            self.send_no_cache_headers('application/json', 200)
            self.wfile.write(b'{"status":"ok"}')

    def log_message(self, format, *args): return

if __name__ == '__main__':
    port = 5050
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
    except Exception:
        local_ip = 'localhost'
    finally:
        s.close()
    
    print(f"VoiceBridge v1.0 running at: http://{local_ip}:{port}")
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()