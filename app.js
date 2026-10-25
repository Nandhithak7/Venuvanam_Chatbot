const chatBody = document.getElementById('chatBody');
const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendButton = chatForm.querySelector('button[type="submit"]');
const suggestions = document.getElementById('suggestions');

function scrollToBottom() { chatBody.scrollTop = chatBody.scrollHeight; }
function addMessage(text, role, sources = [], extraClass = '') {
  const wrap = document.createElement('div');
  wrap.className = `message ${role === 'user' ? 'user-message' : 'assistant-message'} ${extraClass}`.trim();
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  wrap.appendChild(bubble);
  if (role !== 'user') {
    const stamp = document.createElement('span');
    stamp.className = 'message-time';
    stamp.textContent = 'VENU VANAM AI';
    wrap.appendChild(stamp);
  }
  if (sources.length) {
    const sourceBox = document.createElement('div');
    sourceBox.className = 'sources';
    sources.forEach(source => {
      try {
        const url = new URL(source.url);
        if (url.protocol !== 'https:' && url.protocol !== 'http:') return;
        const a = document.createElement('a');
        a.href = url.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
        a.textContent = `↗ ${source.title || 'Open article'}`;
        sourceBox.appendChild(a);
      } catch (_) { /* Ignore malformed source URLs. */ }
    });
    if (sourceBox.children.length) wrap.appendChild(sourceBox);
  }
  chatBody.appendChild(wrap);
  scrollToBottom();
  return wrap;
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message) return;
  if (suggestions) suggestions.remove();
  addMessage(message, 'user');
  messageInput.value = '';
  messageInput.style.height = 'auto';
  sendButton.disabled = true;
  const pending = addMessage('Thinking through your question…', 'assistant', [], 'typing');
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message})
    });
    const data = await response.json();
    pending.remove();
    if (!response.ok) throw new Error(data.error || 'Request failed.');
    addMessage(data.answer || 'Sorry, I could not find an answer.', 'assistant', data.sources || []);
  } catch (error) {
    pending.remove();
    addMessage(`Sorry, something went wrong. ${error.message || 'Please try again.'}`, 'assistant');
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
}

chatForm.addEventListener('submit', event => { event.preventDefault(); sendMessage(messageInput.value); });
messageInput.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); chatForm.requestSubmit(); }
});
messageInput.addEventListener('input', () => { messageInput.style.height = 'auto'; messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`; });
document.querySelectorAll('[data-prompt]').forEach(button => button.addEventListener('click', () => sendMessage(button.dataset.prompt)));
document.getElementById('clearChat').addEventListener('click', () => window.location.reload());
