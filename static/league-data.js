// This script runs when the league-data.html content is loaded into the home page.
(function() {
    const terminalInput = document.getElementById('terminal-input');
    const terminalOutput = document.getElementById('terminal-output');
    const terminalOutputContainer = document.getElementById('terminal-output-container');

    // Check if the elements exist to avoid errors if this page is not loaded
    if (!terminalInput || !terminalOutput || !terminalOutputContainer) {
        // Silently return if the elements aren't on the page.
        // This can happen if the user navigates to another tab.
        return;
    }

    const appendToTerminal = (text, type = 'output') => {
        const line = document.createElement('div');
        line.style.whiteSpace = 'pre-wrap'; // Ensure long lines wrap
        if (type === 'input') {
            line.innerHTML = `<span class="text-gray-500 mr-2">$</span>${text}`;
        } else if (type === 'error') {
            line.innerHTML = `<span class="text-red-400">${text}</span>`;
        } else {
            line.textContent = text;
        }
        terminalOutput.appendChild(line);
        terminalOutputContainer.scrollTop = terminalOutputContainer.scrollHeight;
    };

    const handleTerminalInput = async (e) => {
        if (e.key === 'Enter') {
            const query = terminalInput.value;
            if (!query) return;

            appendToTerminal(query, 'input');
            terminalInput.value = '';

            try {
                const response = await fetch('/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });

                const data = await response.json();
                if (response.status === 401) {
                    appendToTerminal(`Error: ${data.error}`, 'error');
                    setTimeout(() => window.location.href = '/logout', 2000);
                    return;
                }
                if (!response.ok) {
                    throw new Error(data.error || 'An unknown error occurred.');
                }
                appendToTerminal(data.result);
            } catch (error) {
                appendToTerminal(`Error: ${error.message}`, 'error');
            }
        }
    };

    // To prevent adding multiple listeners, we'll use a flag on the element.
    if (!terminalInput.dataset.listenerAttached) {
        terminalInput.addEventListener('keydown', handleTerminalInput);
        terminalInput.dataset.listenerAttached = 'true';
    }

})();
