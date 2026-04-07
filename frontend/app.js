/**
 * DocuMind AI — Frontend Application Logic
 *
 * Handles file uploads, document management, Q&A chat,
 * and all interactions with the backend API.
 */

const API_BASE = '/api';

// ── State ──
let selectedDocId = null;
let currentConversationId = null;
let pollingIntervals = {};

// ── DOM Elements ──
const navTabs = document.querySelectorAll('.nav-tab');
const tabContents = document.querySelectorAll('.tab-content');
const uploadZone = document.getElementById('upload-zone');
const fileInput = document.getElementById('file-input');
const uploadProgressContainer = document.getElementById('upload-progress-container');
const uploadFilename = document.getElementById('upload-filename');
const uploadFilesize = document.getElementById('upload-filesize');
const uploadProgressBar = document.getElementById('upload-progress-bar');
const uploadStatusText = document.getElementById('upload-status-text');
const documentSelector = document.getElementById('document-selector');
const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const btnSend = document.getElementById('btn-send');
const btnNewChat = document.getElementById('btn-new-chat');
const chatDocName = document.getElementById('chat-doc-name');
const documentsGrid = document.getElementById('documents-grid');

// ── Tab Navigation ──
navTabs.forEach(tab => {
    tab.addEventListener('click', () => {
        const targetTab = tab.dataset.tab;
        navTabs.forEach(t => t.classList.remove('active'));
        tabContents.forEach(tc => tc.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`tab-${targetTab}`).classList.add('active');

        if (targetTab === 'qa') loadDocumentSelector();
        if (targetTab === 'documents') loadDocumentsList();
    });
});

// ── File Upload ──
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
});
uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('drag-over');
});
uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFileUpload(file);
});
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) handleFileUpload(file);
});

async function handleFileUpload(file) {
    // validate file type
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
        showToast('Only PDF and DOCX files are supported', 'error');
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showToast('File size exceeds 50MB limit', 'error');
        return;
    }

    // Show progress
    uploadProgressContainer.style.display = 'block';
    uploadFilename.textContent = file.name;
    uploadFilesize.textContent = formatFileSize(file.size);
    uploadProgressBar.style.width = '0%';
    uploadStatusText.textContent = 'Uploading...';

    // Simulate initial progress while uploading
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress = Math.min(progress + Math.random() * 15, 85);
        uploadProgressBar.style.width = `${progress}%`;
    }, 200);

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_BASE}/documents/upload`, {
            method: 'POST',
            body: formData,
        });

        clearInterval(progressInterval);

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Upload failed');
        }

        const data = await response.json();
        uploadProgressBar.style.width = '100%';
        uploadStatusText.textContent = 'Upload complete! Processing document...';
        showToast(`"${file.name}" uploaded successfully!`, 'success');

        // Start polling for status
        pollDocumentStatus(data.id);

    } catch (error) {
        clearInterval(progressInterval);
        uploadProgressBar.style.width = '0%';
        uploadStatusText.textContent = `Error: ${error.message}`;
        showToast(`Upload failed: ${error.message}`, 'error');
    }

    fileInput.value = '';
}

function pollDocumentStatus(docId) {
    if (pollingIntervals[docId]) clearInterval(pollingIntervals[docId]);

    pollingIntervals[docId] = setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/documents/${docId}/status`);
            const doc = await res.json();

            if (doc.status === 'READY') {
                clearInterval(pollingIntervals[docId]);
                delete pollingIntervals[docId];
                uploadStatusText.textContent = `Document ready! ${doc.chunk_count} chunks created.`;
                showToast(`Document processed: ${doc.chunk_count} chunks indexed`, 'success');
                loadDocumentSelector();
                loadDocumentsList();
            } else if (doc.status === 'FAILED') {
                clearInterval(pollingIntervals[docId]);
                delete pollingIntervals[docId];
                uploadStatusText.textContent = `Processing failed: ${doc.error_message || 'Unknown error'}`;
                showToast('Document processing failed', 'error');
            } else {
                uploadStatusText.textContent = `Status: ${doc.status}...`;
            }
        } catch (e) {
            // silently retry
        }
    }, 2000);
}

// ── Document Selector (Q&A Sidebar) ──
async function loadDocumentSelector() {
    try {
        const res = await fetch(`${API_BASE}/documents/`);
        const data = await res.json();

        if (!data.documents || data.documents.length === 0) {
            documentSelector.innerHTML = '<p class="empty-state">No documents yet. Upload one first!</p>';
            return;
        }

        documentSelector.innerHTML = data.documents.map(doc => `
            <div class="doc-select-item ${doc.id === selectedDocId ? 'selected' : ''}"
                 data-id="${doc.id}" data-name="${doc.original_filename}" data-status="${doc.status}">
                <span class="doc-name">${escapeHtml(doc.original_filename)}</span>
                <span class="doc-meta">
                    <span class="doc-status-badge ${doc.status.toLowerCase()}">${doc.status}</span>
                    ${doc.chunk_count ? `· ${doc.chunk_count} chunks` : ''}
                </span>
            </div>
        `).join('');

        // Click handlers on doc items
        documentSelector.querySelectorAll('.doc-select-item').forEach(item => {
            item.addEventListener('click', () => {
                if (item.dataset.status !== 'READY') {
                    showToast('Document is not ready yet', 'info');
                    return;
                }
                selectDocument(parseInt(item.dataset.id), item.dataset.name);
                documentSelector.querySelectorAll('.doc-select-item').forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
            });
        });
    } catch (e) {
        documentSelector.innerHTML = '<p class="empty-state">Failed to load documents</p>';
    }
}

function selectDocument(docId, docName) {
    selectedDocId = docId;
    currentConversationId = null;
    chatDocName.textContent = docName;
    chatInput.disabled = false;
    btnSend.disabled = false;
    clearChat();
}

function clearChat() {
    currentConversationId = null;
    chatMessages.innerHTML = `
        <div class="chat-welcome">
            <div class="welcome-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
            </div>
            <h3>Ask anything about this document</h3>
            <p>Your questions will be answered based solely on the document content.<br>AI will not hallucinate or make up information.</p>
        </div>
    `;
}

// ── New Chat Button ──
btnNewChat.addEventListener('click', () => {
    if (selectedDocId) clearChat();
});

// ── Chat Input ──
chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

btnSend.addEventListener('click', sendMessage);

async function sendMessage() {
    const question = chatInput.value.trim();
    if (!question || !selectedDocId) return;

    // Remove welcome screen if present
    const welcome = chatMessages.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Add user message to UI
    appendMessage('user', question);

    // Clear input
    chatInput.value = '';
    chatInput.style.height = 'auto';
    btnSend.disabled = true;
    chatInput.disabled = true;

    // Show typing indicator
    const typingEl = showTypingIndicator();

    try {
        const payload = {
            question,
            document_id: selectedDocId,
        };
        if (currentConversationId) {
            payload.conversation_id = currentConversationId;
        }

        const res = await fetch(`${API_BASE}/questions/ask`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        // Remove typing indicator
        typingEl.remove();

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Failed to get answer');
        }

        const data = await res.json();
        currentConversationId = data.conversation_id;

        // Add assistant message with source chunks
        appendMessage('assistant', data.answer, data.source_chunks);

    } catch (error) {
        typingEl.remove();
        appendMessage('assistant', `Sorry, something went wrong: ${error.message}`);
        showToast(`Error: ${error.message}`, 'error');
    }

    btnSend.disabled = false;
    chatInput.disabled = false;
    chatInput.focus();
}

function appendMessage(role, content, sources = []) {
    const avatar = role === 'user' ? 'U' : 'AI';
    let sourcesHtml = '';

    if (sources && sources.length > 0) {
        const sourceItems = sources.map((s, i) => `
            <div class="source-chunk">
                <span class="source-score">Source ${i + 1} · Score: ${s.relevance_score.toFixed(3)}</span>
                <p>${escapeHtml(s.content)}</p>
            </div>
        `).join('');

        sourcesHtml = `
            <div class="message-sources">
                <details>
                    <summary>📚 ${sources.length} source chunks used</summary>
                    ${sourceItems}
                </details>
            </div>
        `;
    }

    const msgHtml = `
        <div class="message ${role}">
            <div class="message-avatar">${avatar}</div>
            <div class="message-bubble">
                ${formatMessageContent(content)}
                ${sourcesHtml}
            </div>
        </div>
    `;

    chatMessages.insertAdjacentHTML('beforeend', msgHtml);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTypingIndicator() {
    const html = `
        <div class="message assistant typing-message">
            <div class="message-avatar">AI</div>
            <div class="message-bubble">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        </div>
    `;
    chatMessages.insertAdjacentHTML('beforeend', html);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return chatMessages.querySelector('.typing-message');
}

// ── Documents List (Documents Tab) ──
async function loadDocumentsList() {
    try {
        const res = await fetch(`${API_BASE}/documents/`);
        const data = await res.json();

        if (!data.documents || data.documents.length === 0) {
            documentsGrid.innerHTML = `
                <div class="empty-state-card">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <polyline points="14 2 14 8 20 8"/>
                    </svg>
                    <h3>No documents yet</h3>
                    <p>Upload your first document to get started</p>
                </div>
            `;
            return;
        }

        documentsGrid.innerHTML = data.documents.map(doc => `
            <div class="doc-card" data-id="${doc.id}">
                <div class="doc-card-header">
                    <span class="doc-card-title">${escapeHtml(doc.original_filename)}</span>
                    <span class="doc-status-badge ${doc.status.toLowerCase()}">${doc.status}</span>
                </div>
                <div class="doc-card-details">
                    <span class="doc-card-detail">📄 ${doc.file_type.toUpperCase()}</span>
                    ${doc.file_size ? `<span class="doc-card-detail">💾 ${formatFileSize(doc.file_size)}</span>` : ''}
                    ${doc.chunk_count ? `<span class="doc-card-detail">🧩 ${doc.chunk_count} chunks</span>` : ''}
                    <span class="doc-card-detail">📅 ${formatDate(doc.created_at)}</span>
                </div>
                ${doc.error_message ? `<div style="color:var(--error);font-size:12px;">Error: ${escapeHtml(doc.error_message)}</div>` : ''}
                <div class="doc-card-actions">
                    ${doc.status === 'READY' ? `<button class="btn-card-action primary" onclick="goToChat(${doc.id}, '${escapeAttr(doc.original_filename)}')">Ask Questions</button>` : ''}
                    <button class="btn-card-action danger" onclick="deleteDocument(${doc.id})">Delete</button>
                </div>
            </div>
        `).join('');

        // Poll for any processing documents
        data.documents.forEach(doc => {
            if (doc.status === 'PROCESSING' || doc.status === 'UPLOADING') {
                pollDocumentStatus(doc.id);
            }
        });

    } catch (e) {
        documentsGrid.innerHTML = '<div class="empty-state-card"><p>Failed to load documents</p></div>';
    }
}

// these need to be global for onclick in template
window.goToChat = function(docId, docName) {
    selectDocument(docId, docName);
    // Switch to Q&A tab
    navTabs.forEach(t => t.classList.remove('active'));
    tabContents.forEach(tc => tc.classList.remove('active'));
    document.getElementById('nav-qa').classList.add('active');
    document.getElementById('tab-qa').classList.add('active');
    loadDocumentSelector();
};

window.deleteDocument = async function(docId) {
    if (!confirm('Are you sure you want to delete this document?')) return;
    try {
        const res = await fetch(`${API_BASE}/documents/${docId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Document deleted', 'success');
            loadDocumentsList();
            if (selectedDocId === docId) {
                selectedDocId = null;
                chatDocName.textContent = 'Select a document to begin';
                chatInput.disabled = true;
                btnSend.disabled = true;
                clearChat();
            }
        } else {
            showToast('Failed to delete document', 'error');
        }
    } catch (e) {
        showToast('Error deleting document', 'error');
    }
};

// ── Utilities ──
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeAttr(text) {
    return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function formatMessageContent(text) {
    // Basic markdown-like formatting
    let html = escapeHtml(text);
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    return html;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ── Initial Load ──
document.addEventListener('DOMContentLoaded', () => {
    loadDocumentsList();
});
