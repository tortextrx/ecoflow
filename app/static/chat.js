const chatArea = document.getElementById('chatArea');
const msgInput = document.getElementById('msgInput');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const previewArea = document.getElementById('previewArea');
const previewName = document.getElementById('previewName');
const clearFile = document.getElementById('clearFile');
const typingArea = document.getElementById('typingArea');
const typingLabel = document.getElementById('typingLabel');

const SESSION_ID = 'session_' + Math.random().toString(36).substr(2, 9);
let pendingFile = null;

// Auto-grow textarea
msgInput.addEventListener('input', () => {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
});

// Enter to send (Shift+Enter for newline)
msgInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

sendBtn.addEventListener('click', sendMessage);

// FILE HANDLING
fileInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  pendingFile = file;
  previewName.textContent = file.name.length > 22 ? file.name.slice(0,20) + '...' : file.name;
  previewArea.style.display = 'flex';
});

clearFile.addEventListener('click', () => {
  pendingFile = null;
  fileInput.value = '';
  previewArea.style.display = 'none';
});

function addBubble(text, side, isFile = false) {
  const wrap = document.createElement('div');
  wrap.className = 'bubble-wrap' + (side === 'user' ? ' user-wrap' : '');
  const bubble = document.createElement('div');
  bubble.className = 'bubble ' + side + (isFile ? ' file-bubble' : '');
  if (isFile) {
    const ext = text.split('.').pop().toLowerCase();
    const icon = document.createElement('span');
    icon.className = 'file-icon';
    icon.textContent = ext === 'pdf' ? '📄' : '🖼️';
    const name = document.createElement('span');
    name.textContent = text;
    bubble.appendChild(icon);
    bubble.appendChild(name);
  } else {
    // Simple markdown-ish rendering
    bubble.innerHTML = text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\n/g, '<br>');
  }
  wrap.appendChild(bubble);
  chatArea.appendChild(wrap);
  chatArea.scrollTop = chatArea.scrollHeight;
  return bubble;
}

function showTyping(label = 'ecoFlow está procesando...') {
  typingLabel.textContent = label;
  typingArea.style.display = 'flex';
  chatArea.scrollTop = chatArea.scrollHeight;
}

function hideTyping() {
  typingArea.style.display = 'none';
}

async function sendMessage() {
  const text = msgInput.value.trim();
  if (!text && !pendingFile) return;

  sendBtn.disabled = true;

  // Mostrar burbuja de usuario
  if (pendingFile) addBubble(pendingFile.name, 'user', true);
  if (text) addBubble(text, 'user');

  msgInput.value = '';
  msgInput.style.height = 'auto';

  showTyping(pendingFile ? 'ecoFlow está analizando el documento...' : 'ecoFlow está pensando...');

  const formData = new FormData();
  formData.append('session_id', SESSION_ID);
  formData.append('message', text);
  if (pendingFile) formData.append('file', pendingFile);

  try {
    const res = await fetch('/api/ecoflow/chat', { method: 'POST', body: formData });
    const data = await res.json();
    hideTyping();
    addBubble(data.reply, 'bot');

    if (data.state === 'done') {
      setTimeout(() => addBubble('¿Hay algo más en lo que pueda ayudarte?', 'bot'), 800);
    }
  } catch (err) {
    hideTyping();
    addBubble('⚠️ Error de comunicación con el servidor. Inténtalo de nuevo.', 'bot');
    console.error(err);
  }

  // Limpiar archivo
  pendingFile = null;
  fileInput.value = '';
  previewArea.style.display = 'none';
  sendBtn.disabled = false;
}
