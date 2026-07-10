/**
 * SmartKrishi - Landing Page JavaScript
 * Hero chat demo, animations, and page interactions
 */

'use strict';

document.addEventListener('DOMContentLoaded', () => {
    initHeroDemo();
    initScrollAnimations();
});

// ── Hero Demo Chat ────────────────────────────────────────────────────────────
function initHeroDemo() {
    const heroInput = document.getElementById('heroInput');
    const heroSendBtn = document.getElementById('heroSendBtn');
    const heroVoiceBtn = document.getElementById('heroVoiceBtn');
    const heroChat = document.getElementById('heroChat');

    if (!heroInput || !heroSendBtn || !heroChat) return;

    async function sendHeroMessage() {
        const message = heroInput.value.trim();
        if (!message) return;

        // Add user message to preview
        const userBubble = document.createElement('div');
        userBubble.className = 'chat-bubble user';
        userBubble.innerHTML = `
            <div class="bubble-text">${escapeHtmlSimple(message)}</div>
            <div class="bubble-avatar">👨‍🌾</div>
        `;
        heroChat.appendChild(userBubble);
        heroInput.value = '';

        // Scroll hero chat
        heroChat.scrollTop = heroChat.scrollHeight;

        // Show typing
        const typing = document.createElement('div');
        typing.className = 'chat-bubble bot';
        typing.id = 'heroTyping';
        typing.innerHTML = `
            <div class="bubble-avatar">🌾</div>
            <div class="bubble-text">
                <span class="typing-dots"><span></span><span></span><span></span></span>
            </div>
        `;
        heroChat.appendChild(typing);
        heroChat.scrollTop = heroChat.scrollHeight;

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, language: 'en' })
            });
            const data = await res.json();

            // Remove typing
            document.getElementById('heroTyping')?.remove();

            // Add response
            const botBubble = document.createElement('div');
            botBubble.className = 'chat-bubble bot';
            const shortResponse = (data.response || '').substring(0, 300);
            const truncated = data.response?.length > 300 ? shortResponse + '...' : shortResponse;
            botBubble.innerHTML = `
                <div class="bubble-avatar">🌾</div>
                <div class="bubble-text">${truncated || 'I can help with that! Login for full advice.'}</div>
            `;
            heroChat.appendChild(botBubble);

        } catch (e) {
            document.getElementById('heroTyping')?.remove();
            const errBubble = document.createElement('div');
            errBubble.className = 'chat-bubble bot';
            errBubble.innerHTML = `
                <div class="bubble-avatar">🌾</div>
                <div class="bubble-text">Please <a href="/auth/login">login</a> to get full AI farming advice!</div>
            `;
            heroChat.appendChild(errBubble);
        }

        heroChat.scrollTop = heroChat.scrollHeight;
    }

    heroSendBtn.addEventListener('click', sendHeroMessage);
    heroInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendHeroMessage();
    });

    // Hero voice button
    heroVoiceBtn?.addEventListener('click', () => {
        startRecording('heroInput', SK.language || 'en');
        setTimeout(stopRecording, 3000);
    });
}

// ── Scroll Animations ─────────────────────────────────────────────────────────
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    // Add initial hidden state and observe
    document.querySelectorAll('[data-aos]').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = `opacity 0.6s ease ${el.dataset.aosDelay || '0'}ms, transform 0.6s ease ${el.dataset.aosDelay || '0'}ms`;
        observer.observe(el);
    });
}

function escapeHtmlSimple(text) {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
