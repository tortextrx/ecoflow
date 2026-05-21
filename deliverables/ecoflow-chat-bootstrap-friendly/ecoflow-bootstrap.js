(function () {
  const root = document.documentElement;
  const chatArea = document.getElementById('chatArea');
  const msgInput = document.getElementById('msgInput');
  const sendBtn = document.getElementById('sendBtn');
  const fileInput = document.getElementById('fileInput');
  const previewArea = document.getElementById('previewArea');
  const previewName = document.getElementById('previewName');
  const clearFile = document.getElementById('clearFile');
  const typingArea = document.getElementById('typingArea');
  const typingLabel = document.getElementById('typingLabel');

  const API_BASE = window.ECOFLOW_API_BASE || root.getAttribute('data-api-base') || '';
  const CHAT_URL = (API_BASE ? API_BASE.replace(/\/$/, '') : '') + '/api/ecoflow/chat';
  const SESSION_ID = 'session_' + Math.random().toString(36).slice(2, 11);
  let pendingFile = null;

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function renderText(text) {
    return escapeHtml(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }

  function addBubble(text, side, isFile) {
    const row = document.createElement('div');
    row.className = 'efb-row' + (side === 'user' ? ' efb-row-user' : '');

    const bubble = document.createElement('div');
    bubble.className = 'efb-bubble ' + (side === 'user' ? 'efb-bubble-user' : 'efb-bubble-bot');

    if (isFile) {
      bubble.classList.add('efb-bubble-file');
      bubble.innerHTML = '<span>📎</span><span>' + escapeHtml(text) + '</span>';
    } else {
      bubble.innerHTML = renderText(text);
    }

    row.appendChild(bubble);
    chatArea.appendChild(row);
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function showTyping(label) {
    typingLabel.textContent = label || 'ecoFlow está pensando...';
    typingArea.classList.remove('d-none');
    chatArea.scrollTop = chatArea.scrollHeight;
  }

  function hideTyping() {
    typingArea.classList.add('d-none');
  }

  msgInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = Math.min(this.scrollHeight, 130) + 'px';
  });

  msgInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  fileInput.addEventListener('change', function (e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    pendingFile = file;
    previewName.textContent = file.name;
    previewArea.classList.remove('d-none');
  });

  clearFile.addEventListener('click', function () {
    pendingFile = null;
    fileInput.value = '';
    previewArea.classList.add('d-none');
  });

  sendBtn.addEventListener('click', sendMessage);

  async function sendMessage() {
    const text = msgInput.value.trim();
    if (!text && !pendingFile) return;

    sendBtn.disabled = true;
    if (pendingFile) addBubble(pendingFile.name, 'user', true);
    if (text) addBubble(text, 'user', false);

    msgInput.value = '';
    msgInput.style.height = 'auto';
    showTyping(pendingFile ? 'ecoFlow está analizando el archivo...' : 'ecoFlow está pensando...');

    const formData = new FormData();
    formData.append('session_id', SESSION_ID);
    formData.append('message', text);
    if (pendingFile) formData.append('file', pendingFile);

    try {
      const res = await fetch(CHAT_URL, { method: 'POST', body: formData });
      const data = await res.json();
      hideTyping();
      addBubble(data.reply || 'Sin respuesta del servidor.', 'bot', false);
    } catch (err) {
      hideTyping();
      addBubble('⚠️ Error de comunicación con ecoFlow. Revisa la URL del endpoint.', 'bot', false);
      console.error(err);
    }

    pendingFile = null;
    fileInput.value = '';
    previewArea.classList.add('d-none');
    sendBtn.disabled = false;
    msgInput.focus();
  }
})();
