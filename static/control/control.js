const channel = new BroadcastChannel('avatar-control');
const API_URL = 'http://127.0.0.1:8000'; 

const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const logElement = document.getElementById('log');
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');

const toggleLipsync = document.getElementById('toggle-lipsync');
const toggleEmotion = document.getElementById('toggle-emotion');
const toggleLLM = document.getElementById('toggle-llm');

//Condition toggles send immediately their state to backend to the avatar
toggleLipsync.addEventListener('change', () => {
    channel.postMessage({ type: 'set_lipsync', payload: { enabled: toggleLipsync.checked } });
});

toggleEmotion.addEventListener('change', () => {
    channel.postMessage({ type: 'set_emotion', payload: { enabled: toggleEmotion.checked } });
});

toggleLLM.addEventListener('change', () => {
    channel.postMessage({ type: 'set_llm', payload: { enabled: toggleLLM.checked } });
});

//Send message (enter key or button click)
sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) {
        return;
    }

    messageInput.value = '';
    logEntry('user', 'you: ' + message);
    setStatus('loading');

    // Send message to backend
    try {
        const response = await fetch(API_URL + '/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message: message, 
                lipsync: toggleLipsync.checked,
                emotion: toggleEmotion.checked,
                use_llm: toggleLLM.checked 
            }),
        });

        // Check for HTTP errors
        if (!response.ok) {
            throw new Error('Server error: ' + response.status);
        };

        // Parse JSON response
        const data = await response.json();
        logEntry('AI-Agent', 'AI-Agent: ' + data.response);
        setStatus('Response received');

        // broadcast response to avatar for speaking
        channel.postMessage({
            type: 'speak',
            payload: { text: data.response, options: { emotion: data.emotion ?? 'neutral' } },
        })
    }
    catch (error) {
        console.error('Error:', error);
        logEntry('system', 'Error: ' + error.message);
        setStatus('error', 'Error: ' + error.message);
    }
}

//status indicator
function setStatus(state) {
  statusIndicator.className = 'status-indicator';
  if (state === 'connected') {
    statusIndicator.classList.add('connected');
    statusText.textContent = 'connected';
  } else if (state === 'error') {
    statusIndicator.classList.add('error');
    statusText.textContent = 'error';
  } else {
    statusText.textContent = 'loading...';
  }
}

// Logging-function 
function logEntry(sender, message) {
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + sender;
    entry.textContent = `[${timestamp()}] ${message}`;
    logElement.appendChild(entry);
    logElement.scrollTop = logElement.scrollHeight;
}

function logSystem(message) {
    logEntry('system', `[System] ${message}`);

}

function timestamp() {
  return new Date().toLocaleTimeString('de-DE', { hour12: false });
}

//check connection to backend 
async function checkConnection() {
  try {
    await fetch(API_URL + '/health');
    setStatus('connected');
  } catch {
    setStatus('error');
  }
}

checkConnection();
