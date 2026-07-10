/**
 * SmartKrishi - Chat Interface JavaScript
 * Handles AI chatbot UI, message rendering, voice I/O, and session management
 */

'use strict';

// ── Chat State ────────────────────────────────────────────────────────────────
const Chat = {
    sessionId: null,
    isLoading: false,
    messages: [],
    ttsActive: localStorage.getItem('sk_tts') !== 'false',
};

// ── DOM References ────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const chatMessages = $('chatMessages');
const chatInput = $('chatInput');
const sendBtn = $('sendBtn');
const typingIndicator = $('typingIndicator');
const chatWelcome = $('chatWelcome');
const ragIndicator = $('ragIndicator');
const charCount = $('charCount');
const ttsToggle = $('ttsToggle');

// ── Initialization ─────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Set language from user preference
    if (typeof CURRENT_USER_LANGUAGE !== 'undefined') {
        const langSel = $('chatLangSelect');
        if (langSel) langSel.value = CURRENT_USER_LANGUAGE;
    }

    // Load initial session if provided
    if (typeof INITIAL_SESSION_ID !== 'undefined' && INITIAL_SESSION_ID) {
        loadSession(INITIAL_SESSION_ID);
    }

    // Event listeners
    sendBtn?.addEventListener('click', sendMessage);
    chatInput?.addEventListener('keydown', handleInputKeydown);
    chatInput?.addEventListener('input', handleInputChange);
    $('newChatBtn')?.addEventListener('click', startNewChat);
    $('clearChatBtn')?.addEventListener('click', clearChat);
    $('sessionsToggle')?.addEventListener('click', toggleSessionsPanel);

    ttsToggle?.addEventListener('click', () => {
        Chat.ttsActive = !Chat.ttsActive;
        localStorage.setItem('sk_tts', Chat.ttsActive);
        ttsToggle.innerHTML = Chat.ttsActive
            ? '<i class="bi bi-volume-up"></i>'
            : '<i class="bi bi-volume-mute"></i>';
        ttsToggle.title = Chat.ttsActive ? 'Voice output ON' : 'Voice output OFF';
        showToast(Chat.ttsActive ? 'Voice output enabled' : 'Voice output disabled', 'info', 2000);
    });

    // Update TTS toggle state
    if (ttsToggle && !Chat.ttsActive) {
        ttsToggle.innerHTML = '<i class="bi bi-volume-mute"></i>';
    }

    // Session item clicks
    document.querySelectorAll('.chat-session-item').forEach(item => {
        item.addEventListener('click', () => {
            const sid = parseInt(item.dataset.sessionId);
            if (sid) loadSession(sid);
        });
    });

    // Scroll to bottom on load
    scrollToBottom();
});

// ── Input Handling ─────────────────────────────────────────────────────────────
function handleInputKeydown(e) {
    if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        sendMessage();
    }
    // Shift+Enter = newline (default textarea behavior, no override needed)
}

function handleInputChange() {
    const len = chatInput.value.length;
    if (charCount) charCount.textContent = len;
    autoResizeTextarea(chatInput);

    // Show RAG indicator for farming-related queries
    const farmingKeywords = ['crop', 'disease', 'pest', 'soil', 'weather', 'fertilizer',
        'scheme', 'mandi', 'price', 'irrigation', 'seed', 'harvest', 'fungal', 'weed',
        'fasal', 'kisan', 'rog', 'keeda', 'mitti', 'khad', 'beej'];
    const query = chatInput.value.toLowerCase();
    const isAgrQuery = farmingKeywords.some(k => query.includes(k));
    if (ragIndicator) {
        ragIndicator.style.display = isAgrQuery && len > 5 ? 'inline-flex' : 'none';
    }
}

// ── Send Message ───────────────────────────────────────────────────────────────
async function sendMessage() {
    const message = chatInput?.value.trim();
    if (!message || Chat.isLoading) return;

    const language = $('chatLangSelect')?.value || SK.language || 'en';
    const contextType = $('contextType')?.value || 'general';

    // Clear input
    chatInput.value = '';
    if (charCount) charCount.textContent = '0';
    autoResizeTextarea(chatInput);
    if (ragIndicator) ragIndicator.style.display = 'none';

    // Hide welcome screen
    if (chatWelcome) chatWelcome.style.display = 'none';

    // Append user message
    appendMessage('user', message);

    // Show typing indicator
    showTyping(true);
    Chat.isLoading = true;
    sendBtn.disabled = true;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                session_id: Chat.sessionId,
                language,
                context_type: contextType,
                is_voice: false
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Request failed');
        }

        showTyping(false);

        // Store session ID
        if (data.session_id) {
            Chat.sessionId = data.session_id;
        }

        // Render AI response
        appendMessage('assistant', data.response, {
            ragUsed: data.rag_used,
            ragDocs: data.rag_docs_count,
            responseTime: data.response_time_ms,
            isDemo: data.is_demo
        });

        // Text-to-speech
        if (Chat.ttsActive && data.response) {
            const stripped = data.response.replace(/<[^>]*>/g, '');
            speakText(stripped, language);
        }

    } catch (err) {
        showTyping(false);
        appendMessage('assistant', `❌ Error: ${err.message || 'Could not get response. Please try again.'}`, { isError: true });
    } finally {
        Chat.isLoading = false;
        sendBtn.disabled = false;
        chatInput?.focus();
    }
}

// ── Message Rendering ──────────────────────────────────────────────────────────
function appendMessage(role, content, meta = {}) {
    const isUser = role === 'user';
    const row = document.createElement('div');
    row.className = `message-row ${isUser ? 'user-row' : ''}`;
    row.setAttribute('data-role', role);

    const timestamp = new Date().toISOString();
    const timeStr = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });

    const renderedContent = isUser ? escapeHtml(content) : renderMarkdown(content);

    // Avatar initials for user
    const userInitial = document.querySelector('.farmer-avatar')?.textContent || 'F';

    row.innerHTML = `
        <div class="message-avatar">${isUser ? userInitial : '🌾'}</div>
        <div class="message-content">
            <div class="message-bubble ${isUser ? 'user-bubble' : 'bot-bubble'} ${meta.isError ? 'border-danger' : ''}">
                ${renderedContent}
            </div>
            <div class="message-meta">
                <span>${timeStr}</span>
                ${meta.ragUsed ? `<span class="rag-badge"><i class="bi bi-database-fill-check me-1"></i>Verified Knowledge</span>` : ''}
                ${meta.responseTime ? `<span>${meta.responseTime}ms</span>` : ''}
                ${meta.isDemo ? `<span class="badge bg-warning text-dark" style="font-size:0.65rem">Demo Mode</span>` : ''}
            </div>
            ${!isUser ? `<div class="message-actions">
                <button class="msg-action-btn" onclick="copyMsgContent(this)" title="Copy">
                    <i class="bi bi-clipboard"></i>
                </button>
                <button class="msg-action-btn" onclick="speakMsgContent(this, '${$('chatLangSelect')?.value || 'en'}')" title="Speak">
                    <i class="bi bi-volume-up"></i>
                </button>
            </div>` : ''}
        </div>
    `;

    chatMessages.appendChild(row);
    scrollToBottom();

    Chat.messages.push({ role, content, timestamp });
}

// ── Copy / Speak message actions ──────────────────────────────────────────────
function copyMsgContent(btn) {
    const bubble = btn.closest('.message-content').querySelector('.message-bubble');
    const text = bubble?.textContent || '';
    copyToClipboard(text.trim());
}

function speakMsgContent(btn, lang) {
    const bubble = btn.closest('.message-content').querySelector('.message-bubble');
    const text = bubble?.textContent || '';
    speakText(text.trim(), lang);
}

// Keep global for inline onclick compatibility
window.copyMsgContent = copyMsgContent;
window.speakMsgContent = speakMsgContent;

// ── Quick Prompts ──────────────────────────────────────────────────────────────
function useQuickPrompt(btn) {
    const text = btn.textContent.trim().replace(/^[^a-zA-Z\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F]+/, '').trim();
    if (chatInput) {
        chatInput.value = text;
        chatInput.dispatchEvent(new Event('input'));
        chatInput.focus();
        sendMessage();
    }
}
window.useQuickPrompt = useQuickPrompt;

// ── Load Session ───────────────────────────────────────────────────────────────
async function loadSession(sessionId) {
    try {
        const res = await fetch(`/api/chat/sessions/${sessionId}/messages`);
        if (!res.ok) return;

        const data = await res.json();
        Chat.sessionId = sessionId;

        // Clear current messages
        chatMessages.innerHTML = '';

        if (data.messages && data.messages.length > 0) {
            if (chatWelcome) chatWelcome.style.display = 'none';
            data.messages.forEach(msg => {
                appendMessage(msg.role, msg.content, {
                    ragUsed: msg.rag_context_used
                });
            });
        } else {
            if (chatWelcome) chatWelcome.style.display = 'block';
        }

        // Update active session in sidebar
        document.querySelectorAll('.chat-session-item').forEach(item => {
            item.classList.toggle('active', parseInt(item.dataset.sessionId) === sessionId);
        });

        // Close sessions panel on mobile
        $('chatSessionsPanel')?.classList.remove('panel-open');

    } catch (err) {
        showToast('Could not load conversation history.', 'warning');
    }
}

// ── New Chat ────────────────────────────────────────────────────────────────────
function startNewChat() {
    Chat.sessionId = null;
    Chat.messages = [];
    chatMessages.innerHTML = '';
    if (chatWelcome) chatWelcome.style.display = 'block';
    if (chatInput) chatInput.focus();

    document.querySelectorAll('.chat-session-item').forEach(el => el.classList.remove('active'));
}

// ── Clear Chat ──────────────────────────────────────────────────────────────────
function clearChat() {
    if (confirm('Clear current conversation display? (History is preserved)')) {
        chatMessages.innerHTML = '';
        if (chatWelcome) chatWelcome.style.display = 'block';
        stopSpeech();
    }
}

// ── Sessions Panel ──────────────────────────────────────────────────────────────
function toggleSessionsPanel() {
    $('chatSessionsPanel')?.classList.toggle('panel-open');
}

// ── Typing Indicator ────────────────────────────────────────────────────────────
function showTyping(show) {
    if (typingIndicator) {
        typingIndicator.style.display = show ? 'flex' : 'none';
    }
    if (show) scrollToBottom();
}

// ── Scroll ──────────────────────────────────────────────────────────────────────
function scrollToBottom() {
    if (chatMessages) {
        requestAnimationFrame(() => {
            chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: 'smooth' });
        });
    }
}

// ── HTML Escape ─────────────────────────────────────────────────────────────────
function escapeHtml(text) {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;')
        .replace(/\n/g, '<br>');
}
