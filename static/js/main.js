window.addEventListener('DOMContentLoaded', () => { loadPortfolioSummary(); });

async function loadPortfolioSummary() {
    try {
        const response = await fetch('/api/portfolio');
        const data = await response.json();
        if (data.error) {
            document.getElementById('portfolio-summary').innerHTML = `<p style="color: #d32f2f;">${data.error}</p>`;
            return;
        }
        const holdings = data.holdings;
        let html = `<div class="portfolio-item"><strong>Total Value:</strong> $${holdings.total_value.toLocaleString()}</div>
                    <div class="portfolio-item"><strong>Cash:</strong> $${holdings.cash.toLocaleString()}</div>
                    <div class="portfolio-item"><strong>Holdings:</strong> ${holdings.holdings.length}</div>`;
        document.getElementById('portfolio-summary').innerHTML = html;
    } catch (error) {
        console.error('Error loading portfolio:', error);
        document.getElementById('portfolio-summary').innerHTML = '<p style="color: #d32f2f;">Failed to load portfolio</p>';
    }
}

function handleKeyPress(event) { if (event.key === 'Enter') { sendMessage(); } }

async function sendMessage() {
    const input = document.getElementById('user-input');
    const message = input.value.trim();
    if (!message) return;
    input.value = '';
    addMessage(message, 'user');
    const sendButton = document.getElementById('send-button');
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
        if (data.error) { addMessage(`Error: ${data.error}`, 'assistant'); }
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
    if (role === 'assistant') { contentDiv.innerHTML = marked.parse(content); }
    else { contentDiv.textContent = content; }
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
        callDiv.innerHTML = `<strong>${call.name}</strong>${Object.keys(call.arguments).length > 0 ? `<br><small>${JSON.stringify(call.arguments)}</small>` : ''}`;
        container.appendChild(callDiv);
    });
}

async function resetConversation() {
    if (!confirm('Are you sure you want to reset the conversation?')) { return; }
    try {
        await fetch('/api/reset', { method: 'POST' });
        const messagesContainer = document.getElementById('chat-messages');
        messagesContainer.innerHTML = `<div class="message assistant-message"><div class="message-content"><strong>👋 Hello!</strong><br><br>I'm your Portfolio Rebalancing Assistant. What would you like to know?</div></div>`;
        document.getElementById('function-calls').innerHTML = '';
    } catch (error) {
        console.error('Error resetting conversation:', error);
        alert('Failed to reset conversation');
    }
}
