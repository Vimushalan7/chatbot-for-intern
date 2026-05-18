/**
 * app.js
 * ──────
 * PaperMind Frontend Logic
 *
 * Handles:
 *  • PDF drag-and-drop / click upload
 *  • API communication with the FastAPI backend
 *  • Chat history management (current session)
 *  • Markdown rendering for assistant replies
 *  • Toast notifications
 *  • Quick-action buttons (summarize, section explanations)
 */

'use strict';

// ── Configuration ──────────────────────────────────────────────────────────────
// Automatically uses localhost/WiFi-IP for local testing (even when double-clicking index.html), and your deployed Render URL for production
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname.startsWith('192.168.') || window.location.hostname === ''
  ? `http://${window.location.hostname || 'localhost'}:8000/api`
  : 'https://chatbot-backend-fisf.onrender.com/api'; // <-- Dynamic Render Web Service URL

// ── State ──────────────────────────────────────────────────────────────────────
const state = {
  documentId:  null,        // active document ID returned by /upload
  filename:    '',          // human-readable filename
  chatHistory: [],          // array of { role, content } for multi-turn context
  isLoading:   false,       // prevents concurrent requests
};

// ── DOM References ─────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const dom = {
  sidebar:        $('sidebar'),
  menuToggle:     $('menuToggle'),
  uploadZone:     $('uploadZone'),
  fileInput:      $('fileInput'),
  uploadProgress: $('uploadProgress'),
  progressBar:    $('progressBar'),
  progressLabel:  $('progressLabel'),
  docInfoSection: $('docInfoSection'),
  docName:        $('docName'),
  docMeta:        $('docMeta'),
  sectionChips:   $('sectionChips'),
  quickActions:   $('quickActions'),
  statusDot:      $('statusDot'),
  statusText:     $('statusText'),
  modelName:      $('modelName'),
  chatWindow:     $('chatWindow'),
  welcomeState:   $('welcomeState'),
  messages:       $('messages'),
  questionInput:  $('questionInput'),
  sendBtn:        $('sendBtn'),
  charCount:      $('charCount'),
  topbarSubtitle: $('topbarSubtitle'),
  toastContainer: $('toastContainer'),
  btnSummarize:   $('btnSummarize'),
  btnAbstract:    $('btnAbstract'),
  btnMethodology: $('btnMethodology'),
  btnResults:     $('btnResults'),
  btnConclusion:  $('btnConclusion'),
  btnClear:       $('btnClear'),
  sidebarClose:   $('sidebarClose'),
  sidebarOverlay: $('sidebarOverlay'),
  themeToggle:    $('themeToggle'),
};

// ══════════════════════════════════════════════════════════════════════════════
// Toast Notifications
// ══════════════════════════════════════════════════════════════════════════════

function showToast(message, type = 'info', duration = 4000) {
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type]}</span><span>${message}</span>`;
  dom.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.animation = 'toastIn 0.3s ease reverse';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

// ══════════════════════════════════════════════════════════════════════════════
// Sidebar & Theme Management
// ══════════════════════════════════════════════════════════════════════════════

function toggleSidebar(force = null) {
  if (force === true) {
    dom.sidebar.classList.add('open');
    dom.sidebarOverlay.classList.add('active');
  } else if (force === false) {
    dom.sidebar.classList.remove('open');
    dom.sidebarOverlay.classList.remove('active');
  } else {
    const isOpen = dom.sidebar.classList.toggle('open');
    dom.sidebarOverlay.classList.toggle('active', isOpen);
  }
}

function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'dark';
  if (savedTheme === 'light') {
    document.body.classList.add('light-mode');
    updateThemeIcons(true);
  } else {
    updateThemeIcons(false);
  }
}

function toggleTheme() {
  const isLight = document.body.classList.toggle('light-mode');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeIcons(isLight);
}

function updateThemeIcons(isLight) {
  const sunIcon = dom.themeToggle.querySelector('.sun-icon');
  const moonIcon = dom.themeToggle.querySelector('.moon-icon');
  if (isLight) {
    sunIcon.style.display = 'none';
    moonIcon.style.display = 'block';
  } else {
    sunIcon.style.display = 'block';
    moonIcon.style.display = 'none';
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Health Check
// ══════════════════════════════════════════════════════════════════════════════

async function checkHealth() {
  dom.statusDot.className  = 'status-dot loading';
  dom.statusText.textContent = 'Connecting…';
  try {
    const res  = await fetch(`${API_BASE}/health`);
    const data = await res.json();

    if (data.ollama?.status === 'online') {
      dom.statusDot.className   = 'status-dot online';
      dom.statusText.textContent = 'Ollama online';
      dom.modelName.textContent  = data.ollama.active_model || 'llama3.2';
    } else {
      dom.statusDot.className   = 'status-dot offline';
      dom.statusText.textContent = 'Ollama offline';
      showToast('⚠️ Ollama is not running. Run: ollama serve', 'error', 8000);
    }
  } catch {
    dom.statusDot.className   = 'status-dot offline';
    dom.statusText.textContent = 'Backend offline';
    showToast('Cannot reach backend. Is the server running on port 8000?', 'error', 8000);
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Upload PDF
// ══════════════════════════════════════════════════════════════════════════════

function setupUploadZone() {
  // Click to browse
  dom.uploadZone.addEventListener('click', () => dom.fileInput.click());
  dom.fileInput.addEventListener('change', e => {
    if (e.target.files[0]) handleFileUpload(e.target.files[0]);
  });

  // Drag and drop
  dom.uploadZone.addEventListener('dragover', e => {
    e.preventDefault();
    dom.uploadZone.classList.add('drag-over');
  });
  dom.uploadZone.addEventListener('dragleave', () => {
    dom.uploadZone.classList.remove('drag-over');
  });
  dom.uploadZone.addEventListener('drop', e => {
    e.preventDefault();
    dom.uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file?.type === 'application/pdf') handleFileUpload(file);
    else showToast('Please drop a PDF file.', 'error');
  });
}

async function handleFileUpload(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Only PDF files are supported.', 'error');
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    showToast('File is too large. Maximum is 50 MB.', 'error');
    return;
  }

  // Show progress
  dom.uploadProgress.classList.remove('hidden');
  dom.uploadZone.style.opacity = '0.5';
  dom.progressBar.style.width  = '20%';
  dom.progressLabel.textContent = 'Uploading…';

  const formData = new FormData();
  formData.append('file', file);

  try {
    // Animate progress while waiting
    let progress = 20;
    const progressInterval = setInterval(() => {
      if (progress < 80) {
        progress += Math.random() * 10;
        dom.progressBar.style.width = `${progress}%`;
        if (progress > 50) dom.progressLabel.textContent = 'Extracting text…';
        if (progress > 70) dom.progressLabel.textContent = 'Building embeddings…';
      }
    }, 600);

    const res  = await fetch(`${API_BASE}/upload`, { method: 'POST', body: formData });
    clearInterval(progressInterval);

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await res.json();

    // Update progress to 100%
    dom.progressBar.style.width  = '100%';
    dom.progressLabel.textContent = 'Complete!';

    setTimeout(() => {
      dom.uploadProgress.classList.add('hidden');
      dom.uploadZone.style.opacity = '1';
      dom.progressBar.style.width  = '0%';
    }, 1500);

    // Save state
    state.documentId  = data.document_id;
    state.filename    = data.filename;
    state.chatHistory = [];

    // Update UI
    dom.docInfoSection.style.display = 'block';
    dom.quickActions.style.display   = 'block';
    dom.docName.textContent          = data.filename;
    dom.docMeta.textContent          = `${data.page_count} pages · ${data.chunk_count} chunks`;
    dom.topbarSubtitle.textContent   = data.filename;

    // Render section chips
    dom.sectionChips.innerHTML = '';
    data.sections_found.forEach(sec => {
      const chip = document.createElement('button');
      chip.className   = 'section-chip';
      chip.textContent = sec;
      chip.addEventListener('click', () => fetchSection(sec));
      dom.sectionChips.appendChild(chip);
    });

    // Hide welcome state, show messages area
    dom.welcomeState.style.display = 'none';

    showToast(`✅ "${data.filename}" processed! Ask me anything.`, 'success');

    // Add a welcome message from assistant
    appendMessage('assistant',
      `I've analysed **${data.filename}** (${data.page_count} pages).\n\n` +
      `I detected the following sections: **${data.sections_found.join(', ')}**.\n\n` +
      `What would you like to know about this paper? 🎓`
    );

    // Auto-close sidebar on mobile after success
    if (window.innerWidth <= 768) toggleSidebar(false);

  } catch (err) {
    dom.uploadProgress.classList.add('hidden');
    dom.uploadZone.style.opacity = '1';
    dom.progressBar.style.width  = '0%';
    showToast(`Upload failed: ${err.message}`, 'error');
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Chat / Q&A
// ══════════════════════════════════════════════════════════════════════════════

function appendMessage(role, content, sources = []) {
  // Hide welcome on first message
  dom.welcomeState.style.display = 'none';

  const msg = document.createElement('div');
  msg.className = `message ${role}`;

  const avatarEmoji = role === 'user' ? '🎓' : '🤖';

  // Parse markdown for assistant messages
  const bubbleContent = role === 'assistant'
    ? marked.parse(content)
    : escapeHtml(content);

  msg.innerHTML = `
    <div class="msg-avatar">${avatarEmoji}</div>
    <div class="msg-content">
      <div class="msg-bubble">${bubbleContent}</div>
      <div class="msg-meta">
        <span>${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
        ${role === 'assistant' && sources.length > 0 ? `
          <button class="sources-toggle" onclick="toggleSources(this)">
            📎 ${sources.length} source${sources.length > 1 ? 's' : ''}
          </button>
          <div class="sources-list" style="display:none">
            ${sources.map(s => `
              <div class="source-item">
                ${escapeHtml(s.text)}
                <span class="source-score">${(s.score * 100).toFixed(0)}% match</span>
              </div>
            `).join('')}
          </div>
        ` : ''}
      </div>
    </div>
  `;

  dom.messages.appendChild(msg);
  dom.chatWindow.scrollTo({ top: dom.chatWindow.scrollHeight, behavior: 'smooth' });
  return msg;
}

function toggleSources(btn) {
  const list = btn.parentElement.querySelector('.sources-list');
  const open = list.style.display !== 'none';
  list.style.display = open ? 'none' : 'flex';
  btn.textContent    = open ? `📎 Sources` : `▾ Hide sources`;
}

function showTypingIndicator() {
  const el = document.createElement('div');
  el.className = 'message assistant';
  el.id = 'typingIndicator';
  el.innerHTML = `
    <div class="msg-avatar">🤖</div>
    <div class="msg-content">
      <div class="msg-bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>
  `;
  dom.messages.appendChild(el);
  dom.chatWindow.scrollTo({ top: dom.chatWindow.scrollHeight, behavior: 'smooth' });
}

function removeTypingIndicator() {
  const el = $('typingIndicator');
  if (el) el.remove();
}

async function sendQuestion(question) {
  if (!question.trim() || state.isLoading) return;
  state.isLoading = true;
  dom.sendBtn.disabled = true;

  // Add user message to UI and history
  appendMessage('user', question);
  
  // Auto-close sidebar on mobile
  if (window.innerWidth <= 768) toggleSidebar(false);

  // Add to chat history
  state.chatHistory.push({ role: 'user', content: question });

  // Clear input
  dom.questionInput.value = '';
  dom.questionInput.style.height = 'auto';
  dom.charCount.textContent = '0';

  showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        document_id:  state.documentId,
        chat_history: state.chatHistory.slice(-10), // last 10 turns
      }),
    });

    if (!res.ok) {
      const err = await res.json();
      let errorMsg = 'Request failed';
      if (typeof err.detail === 'string') {
        errorMsg = err.detail;
      } else if (Array.isArray(err.detail)) {
        // FastAPI validation errors
        errorMsg = err.detail.map(d => `${d.loc[d.loc.length - 1]}: ${d.msg}`).join(', ');
      }
      throw new Error(errorMsg);
    }

    const data = await res.json();
    removeTypingIndicator();

    appendMessage('assistant', data.answer, data.sources || []);
    state.chatHistory.push({ role: 'assistant', content: data.answer });

  } catch (err) {
    removeTypingIndicator();
    appendMessage('assistant', `❌ Sorry, I encountered an error: ${err.message}`);
    showToast(err.message, 'error');
  } finally {
    state.isLoading  = false;
    dom.sendBtn.disabled = false;
    dom.questionInput.focus();
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Quick Actions
// ══════════════════════════════════════════════════════════════════════════════

async function fetchSummary() {
  if (!state.documentId) { showToast('Upload a paper first.', 'info'); return; }
  if (state.isLoading) return;

  state.isLoading = true;
  appendMessage('user', '📋 Summarize this research paper for me.');
  showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/summarize`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id: state.documentId }),
    });
    const data = await res.json();
    removeTypingIndicator();
    if (!res.ok) {
      const errorMsg = typeof data.detail === 'string' ? data.detail : 'Summary failed';
      throw new Error(errorMsg);
    }
    appendMessage('assistant', `## 📋 Paper Summary\n\n${data.summary}`);
  } catch (err) {
    removeTypingIndicator();
    appendMessage('assistant', `❌ Summary failed: ${err.message}`);
  } finally {
    state.isLoading = false;
  }
}

async function fetchSection(sectionName) {
  if (!state.documentId) { showToast('Upload a paper first.', 'info'); return; }
  if (state.isLoading) return;

  state.isLoading = true;
  const capitalised = sectionName.charAt(0).toUpperCase() + sectionName.slice(1);
  appendMessage('user', `📖 Explain the **${capitalised}** section.`);
  showTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/section`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ document_id: state.documentId, section_name: sectionName }),
    });
    const data = await res.json();
    removeTypingIndicator();
    if (!res.ok) {
      const errorMsg = typeof data.detail === 'string' ? data.detail : 'Could not fetch section';
      throw new Error(errorMsg);
    }
    appendMessage('assistant',
      `## 📖 ${capitalised}\n\n${data.explanation}` +
      (data.text ? `\n\n---\n> **Excerpt:** ${data.text.substring(0, 400)}…` : '')
    );
  } catch (err) {
    removeTypingIndicator();
    appendMessage('assistant', `❌ Could not fetch section: ${err.message}`);
  } finally {
    state.isLoading = false;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// UI Helpers
// ══════════════════════════════════════════════════════════════════════════════

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function setupTextarea() {
  dom.questionInput.addEventListener('input', function () {
    // Auto-resize
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 160) + 'px';

    // Character count
    dom.charCount.textContent = this.value.length;

    // Enable/disable send button
    dom.sendBtn.disabled = !this.value.trim();
  });

  // Submit on Enter (Shift+Enter = new line)
  dom.questionInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!dom.sendBtn.disabled) sendQuestion(this.value.trim());
    }
  });
}

function setupSendButton() {
  dom.sendBtn.addEventListener('click', () => {
    sendQuestion(dom.questionInput.value.trim());
  });
}

function setupSidebarToggle() {
  // Mobile hamburger menu
  dom.menuToggle.addEventListener('click', () => toggleSidebar(true));

  // Sidebar close button (mobile)
  dom.sidebarClose.addEventListener('click', () => toggleSidebar(false));

  // Overlay click to close (mobile)
  dom.sidebarOverlay.addEventListener('click', () => toggleSidebar(false));
}

function setupThemeToggle() {
  dom.themeToggle.addEventListener('click', toggleTheme);
}

function setupQuickActions() {
  dom.btnSummarize.addEventListener('click', fetchSummary);
  dom.btnAbstract.addEventListener('click',   () => fetchSection('abstract'));
  dom.btnMethodology.addEventListener('click', () => fetchSection('methodology'));
  dom.btnResults.addEventListener('click',    () => fetchSection('results'));
  dom.btnConclusion.addEventListener('click', () => fetchSection('conclusion'));

  dom.btnClear.addEventListener('click', () => {
    state.chatHistory = [];
    dom.messages.innerHTML = '';
    dom.welcomeState.style.display = 'flex';
    showToast('Chat cleared.', 'info');
  });
}

function setupExampleChips() {
  document.querySelectorAll('.example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const q = chip.dataset.q;
      dom.questionInput.value = q;
      dom.questionInput.dispatchEvent(new Event('input'));
      sendQuestion(q);
    });
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// Initialise
// ══════════════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupUploadZone();
  setupTextarea();
  setupSendButton();
  setupSidebarToggle();
  setupThemeToggle();
  setupQuickActions();
  setupExampleChips();
  checkHealth();

  // Re-check health every 30 seconds
  setInterval(checkHealth, 30_000);

  // Focus input
  dom.questionInput.focus();
});

// Expose for inline onclick usage
window.toggleSources = toggleSources;
