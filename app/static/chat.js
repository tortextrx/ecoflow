const chatArea = document.getElementById('chatArea');
const msgInput = document.getElementById('msgInput');
const sendBtn = document.getElementById('sendBtn');
const fileInput = document.getElementById('fileInput');
const filePreview = document.getElementById('filePreview');
const fileName = document.getElementById('fileName');
const clearFile = document.getElementById('clearFile');
const typingArea = document.getElementById('typingArea');
const typingLabel = document.getElementById('typingLabel');
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const htmlEl = document.documentElement;

const SID = 'eco_' + Math.random().toString(36).slice(2, 10);
let pendingFile = null;
let internalConfig = null;
let configPromise = null;

// THEME HANDLING
const SUN_PATH = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>';
const MOON_PATH = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>';

function setTheme(theme) {
  htmlEl.setAttribute('data-theme', theme);
  themeIcon.innerHTML = theme === 'dark' ? SUN_PATH : MOON_PATH;
  localStorage.setItem('ecoflow-theme', theme);
}
themeToggle.addEventListener('click', () => {
  const current = htmlEl.getAttribute('data-theme');
  setTheme(current === 'dark' ? 'light' : 'dark');
});

const savedTheme = localStorage.getItem('ecoflow-theme') || 'dark';
setTheme(savedTheme);

// CONFIG HANDLING
async function initConfig() {
  try {
    const res = await fetch('/api/ecoflow/config/internal');
    if (res.ok) {
      internalConfig = await res.json();
      console.log('ecoFlow: Modo Desarrollo (Tokens cargados)');
    } else {
      console.log('ecoFlow: Modo Producción (Sin tokens internos)');
    }
  } catch (e) {
    console.error('ecoFlow: Error cargando configuración interna', e);
  }
}
configPromise = initConfig();

function md(s) {
  return s
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

function addBubble(text, side, isFile = false) {
  const row = document.createElement('div'); row.className = 'row' + (side === 'user' ? ' me' : '');
  const b = document.createElement('div'); b.className = 'bub ' + (side === 'user' ? 'me' : 'bot');

  if (isFile) {
    const ext = text.split('.').pop().toLowerCase();
    b.innerHTML = `<div class="file-card">
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ext === 'pdf' ? '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>' : '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>'}</svg>
      <span>${text}</span>
    </div>`;
  } else {
    b.innerHTML = md(text);
  }

  row.appendChild(b);
  chatArea.appendChild(row);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function showTyping(label = 'ecoFlow EST\u00c1 PROCESANDO\u2026') {
  typingLabel.textContent = label; typingArea.style.display = 'flex';
  chatArea.scrollTop = chatArea.scrollHeight;
}
function hideTyping() { typingArea.style.display = 'none'; }

msgInput.addEventListener('input', () => {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 160) + 'px';
});

msgInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});

sendBtn.addEventListener('click', sendMessage);

fileInput.addEventListener('change', e => {
  const f = e.target.files[0]; if (!f) return;
  pendingFile = f;
  fileName.textContent = f.name.length > 22 ? f.name.slice(0, 20) + '…' : f.name;
  filePreview.style.display = 'flex';
});

clearFile.addEventListener('click', () => {
  pendingFile = null; fileInput.value = ''; filePreview.style.display = 'none';
});

// Mensaje inicial
setTimeout(() => {
  addBubble('\u00a1Hola! Soy **ecoFlow**, tu asistente inteligente conectado a ecoSoftWEB.\n\nPuedo ayudarte con mucho m\u00e1s:\n\n\u00a0\u00a0\ud83d\udd0d **Entidades**: Localizar o crear clientes, proveedores, acreedores, etc.\n\u00a0\u00a0\ud83d\udcc4 **Facturaci\u00f3n**: A\u00f1adir compras y gastos.\n\u00a0\u00a0\u2705 **Gesti\u00f3n**: Generar servicios o tareas.\n\u00a0\u00a0\ud83d\udcdd **Historial servicios**: A\u00f1adir notas r\u00e1pidas de seguimiento.\n\u00a0\u00a0\ud83d\udce6 **Art\u00edculos**: Alta y consulta de art\u00edculos.\n\nSube una factura o dime qu\u00e9 necesitas gestionar hoy.', 'bot');
}, 300);

async function sendMessage() {
  const t = msgInput.value.trim();
  if (!t && !pendingFile) return;

  if (configPromise) await configPromise;

  sendBtn.disabled = true;
  if (pendingFile) addBubble(pendingFile.name, 'user', true);
  if (t) addBubble(t, 'user');

  msgInput.value = ''; msgInput.style.height = 'auto';
  showTyping(pendingFile ? 'Analizando documento\u2026' : 'Estoy pensando');

  const fd = new FormData();
  fd.append('session_id', SID); fd.append('message', t);
  if (pendingFile) fd.append('file', pendingFile);

  const headers = {};
  if (internalConfig) {
    headers['Authorization'] = `Bearer ${internalConfig.security_token}`;
    headers['X-EcoSoft-Authorization'] = internalConfig.demo_erp_token.startsWith('Bearer') ? internalConfig.demo_erp_token : `Bearer ${internalConfig.demo_erp_token}`;
  }

  try {
    const r = await fetch('/api/ecoflow/chat', { 
      method: 'POST', 
      body: fd,
      headers: headers
    });
    
    if (r.status === 401 || r.status === 403) {
      hideTyping();
      addBubble('\u274c **Error de Autenticaci\u00f3n**. El servidor ha rechazado el token de seguridad.', 'bot');
      sendBtn.disabled = false;
      return;
    }

    const d = await r.json();
    hideTyping();
    addBubble(d.reply, 'bot');
    if (d.state === 'done') setTimeout(() => addBubble('\u00bfNecesitas algo m\u00e1s?', 'bot'), 800);
  } catch (e) {
    hideTyping();
    addBubble('\u26a0\ufe0f ERROR // CONNECTION FAILED.', 'bot');
    console.error(e);
  }

  pendingFile = null; fileInput.value = ''; filePreview.style.display = 'none'; sendBtn.disabled = false;
}
