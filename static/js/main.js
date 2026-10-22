window.addEventListener('DOMContentLoaded', () => { loadPortfolioSummary(); });

function fmt(n) { return Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }

async function loadPortfolioSummary() {
    const box = document.getElementById('portfolio-summary');
    try {
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        if (!response.ok || data.error) { box.innerHTML = ''; box.appendChild(errorLine(data.error || 'Failed to load portfolio')); return; }
        const h = data.holdings, ccy = h.currency || 'USD';
        box.innerHTML = '';
        [['Total Value', `${ccy} ${fmt(h.total_value)}`], ['Cash', `${ccy} ${fmt(h.cash)}`], ['Holdings', h.holdings.length]]
            .forEach(([label, value]) => {
                const div = document.createElement('div');
                div.className = 'portfolio-item';
                const strong = document.createElement('strong');
                strong.textContent = label + ': ';
                div.appendChild(strong);
                div.appendChild(document.createTextNode(value));
                box.appendChild(div);
            });
    } catch (error) {
        console.error('Error loading portfolio:', error);
        box.innerHTML = '';
        box.appendChild(errorLine('Failed to load portfolio'));
    }
}

function errorLine(text) { const p = document.createElement('p'); p.style.color = '#d32f2f'; p.textContent = text; return p; }

function handleKeyPress(event) { if (event.key === 'Enter') { event.preventDefault(); sendMessage(); } }

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    const sendButton = document.getElementById('send-button');
    if (!message || sendButton.disabled) return;
    input.value = '';
    addMessage(message, 'user');
    sendButton.disabled = true;
    sendButton.textContent = 'Thinking...';
    document.getElementById('function-calls').innerHTML = '';
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await response.json();
        if (!response.ok || data.error) { addMessage(`Error: ${data.error || response.statusText}`, 'assistant'); }
        else {
            if (data.function_calls && data.function_calls.length > 0) { showFunctionCalls(data.function_calls); }
            addMessage(data.response, 'assistant');
        }
    } catch (error) {
        console.error('Error:', error);
        addMessage('Sorry, something went wrong. Please try again.', 'assistant');
    } finally {
        sendButton.disabled = false;
        sendButton.textContent = 'Send';
        input.focus();
    }
}

function sendQuickMessage(message) { document.getElementById('user-input').value = message; sendMessage(); }

function addMessage(content, role) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (role === 'assistant' && window.marked && window.DOMPurify) {
        contentDiv.innerHTML = DOMPurify.sanitize(marked.parse(content || ''));
    } else {
        contentDiv.textContent = content || '';
    }
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function showFunctionCalls(functionCalls) {
    const container = document.getElementById('function-calls');
    container.innerHTML = '<strong>🔧 Functions called:</strong>';
    functionCalls.forEach(call => {
        const callDiv = document.createElement('div');
        callDiv.className = 'function-call-item';
        const name = document.createElement('strong');
        name.textContent = call.name;
        callDiv.appendChild(name);
        if (call.arguments && Object.keys(call.arguments).length > 0) {
            const small = document.createElement('small');
            small.textContent = JSON.stringify(call.arguments);
            callDiv.appendChild(document.createElement('br'));
            callDiv.appendChild(small);
        }
        container.appendChild(callDiv);
    });
}

async function resetConversation() {
    if (!confirm('Are you sure you want to reset the conversation?')) { return; }
    try {
        await fetch('/api/reset', { method: 'POST' });
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.innerHTML = '';
        addMessage("**👋 Hello!**\n\nI'm your Portfolio Rebalancing Assistant. What would you like to know?", 'assistant');
        document.getElementById('function-calls').innerHTML = '';
    } catch (error) {
        console.error('Error resetting conversation:', error);
        alert('Failed to reset conversation');
    }
}
