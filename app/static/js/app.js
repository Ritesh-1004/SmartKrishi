/**
 * SmartKrishi - Core Application JavaScript
 * Dark mode, language selection, and global utilities
 */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────
const SK = {
    darkMode: false,
    language: localStorage.getItem('sk_language') || 'en',
    ttsEnabled: localStorage.getItem('sk_tts') !== 'false',
};

// ── Dark Mode ────────────────────────────────────────────────────────────────
function initDarkMode() {
    const saved = localStorage.getItem('sk_dark_mode');
    const prefersD = window.matchMedia('(prefers-color-scheme: dark)').matches;
    SK.darkMode = saved !== null ? saved === 'true' : prefersD;
    applyDarkMode(SK.darkMode);
}

function applyDarkMode(isDark) {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    const icon = document.getElementById('darkModeIcon') || document.querySelector('#darkModeToggleMobile i');
    if (icon) icon.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    SK.darkMode = isDark;
}

function toggleDarkMode() {
    SK.darkMode = !SK.darkMode;
    applyDarkMode(SK.darkMode);
    localStorage.setItem('sk_dark_mode', SK.darkMode);
    // Update all toggle icons
    document.querySelectorAll('[id*="darkModeIcon"]').forEach(el => {
        el.className = SK.darkMode ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    });
}

// ── Language ─────────────────────────────────────────────────────────────────
const LANG_LABELS = {
    en: 'EN', hi: 'HI', ta: 'TA', te: 'TE', kn: 'KN',
    bn: 'BN', mr: 'MR', gu: 'GU', pa: 'PA', ml: 'ML', or: 'OR'
};

function initLanguage() {
    const savedLang = localStorage.getItem('sk_language') || 'en';
    SK.language = savedLang;
    updateLanguageUI(savedLang);
}

function updateLanguageUI(lang) {
    const label = document.getElementById('currentLangLabel');
    if (label) label.textContent = LANG_LABELS[lang] || lang.toUpperCase();

    // Mark active in dropdown
    document.querySelectorAll('.lang-option').forEach(el => {
        el.classList.toggle('active', el.dataset.lang === lang);
    });
}

function setLanguage(lang) {
    SK.language = lang;
    localStorage.setItem('sk_language', lang);
    updateLanguageUI(lang);

    // Update chat language select if present
    const chatLangSel = document.getElementById('chatLangSelect');
    if (chatLangSel) chatLangSel.value = lang;
}

// ── Notification / Toast ─────────────────────────────────────────────────────
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer') || createToastContainer();
    const toast = document.createElement('div');
    const icons = { success: 'check-circle-fill', danger: 'exclamation-circle-fill', info: 'info-circle-fill', warning: 'exclamation-triangle-fill' };
    toast.className = `alert alert-${type} alert-dismissible fade show flash-alert`;
    toast.innerHTML = `<i class="bi bi-${icons[type] || icons.info} me-2"></i>${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>`;
    container.appendChild(toast);
    setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, duration);
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'flash-container';
    document.body.appendChild(container);
    return container;
}

// ── Markdown Renderer (simple) ───────────────────────────────────────────────
function renderMarkdown(text) {
    return text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code>$1</code>')
        .replace(/^### (.+)$/gm, '<h6 class="mt-2 mb-1">$1</h6>')
        .replace(/^## (.+)$/gm, '<h5 class="mt-2 mb-1">$1</h5>')
        .replace(/^# (.+)$/gm, '<h4 class="mt-2 mb-2">$1</h4>')
        .replace(/^• (.+)$/gm, '<li>$1</li>')
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
        .replace(/\n{2,}/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/(<li>[\s\S]+?<\/li>)+/g, match => `<ul>${match}</ul>`)
        .replace(/^(.+)$/gm, (m) => m.startsWith('<') ? m : `<p>${m}</p>`)
        .replace(/<p><\/p>/g, '')
        .replace(/(https?:\/\/[^\s<]+)/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
}

// ── Text-to-Speech ───────────────────────────────────────────────────────────
let currentUtterance = null;

function speakText(text, lang = 'en') {
    if (!window.speechSynthesis || !SK.ttsEnabled) return;

    // Stop current speech
    if (currentUtterance) {
        window.speechSynthesis.cancel();
    }

    // Strip HTML tags for TTS
    const stripped = text.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
    if (!stripped) return;

    const utterance = new SpeechSynthesisUtterance(stripped.substring(0, 3000));

    // Language mapping
    const langMap = {
        hi: 'hi-IN', ta: 'ta-IN', te: 'te-IN', kn: 'kn-IN',
        bn: 'bn-IN', mr: 'mr-IN', gu: 'gu-IN', pa: 'pa-IN',
        ml: 'ml-IN', or: 'or-IN', en: 'en-IN'
    };
    utterance.lang = langMap[lang] || 'en-IN';
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.volume = 0.9;

    currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);
}

function stopSpeech() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        currentUtterance = null;
    }
}

// ── Speech-to-Text ───────────────────────────────────────────────────────────
let recognition = null;
let isRecording = false;

function initSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return null;

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    return recognition;
}

function startRecording(targetInputId, lang = 'en') {
    if (!recognition) recognition = initSpeechRecognition();
    if (!recognition) {
        showToast('Voice input not supported in this browser. Try Chrome.', 'warning');
        return;
    }

    const langMap = {
        hi: 'hi-IN', ta: 'ta-IN', te: 'te-IN', kn: 'kn-IN',
        bn: 'bn-IN', mr: 'mr-IN', gu: 'gu-IN', pa: 'pa-IN', en: 'en-IN'
    };
    recognition.lang = langMap[lang] || 'en-IN';

    const input = document.getElementById(targetInputId);
    const voiceBtn = document.getElementById('voiceInputBtn');
    const voiceIcon = document.getElementById('voiceIcon');

    recognition.onstart = () => {
        isRecording = true;
        if (voiceBtn) voiceBtn.classList.add('recording');
        if (voiceIcon) voiceIcon.className = 'bi bi-mic-fill';
    };

    recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
            .map(r => r[0].transcript)
            .join('');
        if (input) {
            input.value = transcript;
            // Trigger auto-resize for textarea
            input.dispatchEvent(new Event('input'));
        }
    };

    recognition.onend = () => {
        isRecording = false;
        if (voiceBtn) voiceBtn.classList.remove('recording');
        if (voiceIcon) voiceIcon.className = 'bi bi-mic';
    };

    recognition.onerror = (e) => {
        isRecording = false;
        if (voiceBtn) voiceBtn.classList.remove('recording');
        if (voiceIcon) voiceIcon.className = 'bi bi-mic';
        if (e.error !== 'aborted') {
            showToast('Voice input error: ' + e.error, 'warning');
        }
    };

    try {
        recognition.start();
    } catch (e) {
        showToast('Could not start voice recording.', 'danger');
    }
}

function stopRecording() {
    if (recognition && isRecording) {
        recognition.stop();
    }
}

// ── Time/Date ─────────────────────────────────────────────────────────────────
function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
}

function timeAgo(isoString) {
    const now = new Date();
    const past = new Date(isoString);
    const diffMs = now - past;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
}

// ── Clipboard ─────────────────────────────────────────────────────────────────
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success', 2000);
    }).catch(() => {
        // Fallback
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        ta.remove();
        showToast('Copied!', 'success', 2000);
    });
}

// ── Auto-resize Textarea ─────────────────────────────────────────────────────
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// ── Debounce ─────────────────────────────────────────────────────────────────
function debounce(fn, delay) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
    };
}

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initDarkMode();
    initLanguage();

    // Dark mode toggles
    document.getElementById('darkModeToggle')?.addEventListener('click', toggleDarkMode);
    document.getElementById('darkModeToggleMobile')?.addEventListener('click', toggleDarkMode);

    // Language selector
    document.querySelectorAll('.lang-option').forEach(el => {
        el.addEventListener('click', (e) => {
            e.preventDefault();
            setLanguage(el.dataset.lang);
        });
    });

    // Sidebar toggle (dashboard pages)
    document.getElementById('sidebarToggle')?.addEventListener('click', () => {
        document.getElementById('sidebar')?.classList.toggle('sidebar-open');
    });

    // Close sidebar when clicking outside (mobile)
    document.addEventListener('click', (e) => {
        const sidebar = document.getElementById('sidebar');
        const toggle = document.getElementById('sidebarToggle');
        if (sidebar && sidebar.classList.contains('sidebar-open') &&
            !sidebar.contains(e.target) && !toggle?.contains(e.target)) {
            sidebar.classList.remove('sidebar-open');
        }
    });

    // Voice button (global, if present)
    const voiceBtn = document.getElementById('voiceInputBtn');
    if (voiceBtn) {
        voiceBtn.addEventListener('mousedown', () => {
            const lang = document.getElementById('chatLangSelect')?.value || SK.language;
            startRecording('chatInput', lang);
        });
        voiceBtn.addEventListener('mouseup', () => {
            setTimeout(stopRecording, 500);
        });
        voiceBtn.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const lang = document.getElementById('chatLangSelect')?.value || SK.language;
            startRecording('chatInput', lang);
        });
        voiceBtn.addEventListener('touchend', () => {
            setTimeout(stopRecording, 500);
        });
    }

    // Auto-dismiss flash messages
    setTimeout(() => {
        document.querySelectorAll('.flash-alert').forEach(el => {
            el.classList.remove('show');
        });
    }, 5000);
});
