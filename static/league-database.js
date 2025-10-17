// This script will manage the league-database.html page
(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const statusText = document.getElementById('db-status-text');
    const actionButton = document.getElementById('db-action-button');

    if (!statusText || !actionButton) {
        console.error('Database page elements not found.');
        return;
    }

    try {
        const response = await fetch('/api/db_status');
        const data = await response.json();

        if (data.db_exists) {
            const date = new Date(data.timestamp * 1000);
            statusText.textContent = `Your league: '${data.league_name}'s data is up to date as of: ${date.toLocaleString()}`;
            actionButton.textContent = 'Update Database';
        } else {
            statusText.textContent = "Your league: [Unknown]'s data is not yet initialized. Please initialize the database.";
            actionButton.textContent = 'Initialize Database';
        }

        // Enable the button now that we have the status
        actionButton.disabled = false;
        actionButton.classList.remove('opacity-50', 'cursor-not-allowed');

    } catch (error) {
        console.error('Error fetching DB status:', error);
        statusText.textContent = 'Could not determine database status. Please try again later.';
        actionButton.textContent = 'Error';
    }
})();
