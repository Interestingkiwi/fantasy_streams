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

    const updateStatus = (data) => {
        if (data.db_exists) {
            const date = new Date(data.timestamp * 1000);
            statusText.textContent = `Your league: '${data.league_name}'s data is up to date as of: ${date.toLocaleString()}`;
            actionButton.textContent = 'Update Database';
        } else {
            statusText.textContent = "Your league's data has not been initialized. Please initialize the database.";
            actionButton.textContent = 'Initialize Database';
        }
    };

    const fetchStatus = async () => {
        try {
            const response = await fetch('/api/db_status');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch status');
            updateStatus(data);
        } catch (error) {
            console.error('Error fetching DB status:', error);
            statusText.textContent = `Could not determine database status. ${error.message}`;
            actionButton.textContent = 'Error';
        } finally {
            actionButton.disabled = false;
            actionButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
    };

    const handleDbAction = async () => {
        actionButton.disabled = true;
        actionButton.classList.add('opacity-50', 'cursor-not-allowed');
        const originalText = actionButton.textContent;
        actionButton.textContent = 'Processing...';
        // Set temporary text while the database is being built
        statusText.textContent = 'Building database file, this may take a few minutes.';

        try {
            const response = await fetch('/api/update_db', { method: 'POST' });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(data.error || 'An unknown error occurred during the update.');
            }

            // Instead of manually updating, just re-fetch the status from the server
            // This ensures the UI is correctly updated with the new timestamp.
            await fetchStatus();

        } catch (error) {
            console.error('Error performing DB action:', error);
            statusText.textContent = `Error: ${error.message}`;
            actionButton.textContent = originalText; // Revert button text on error
            // Re-enable the button on failure
            actionButton.disabled = false;
            actionButton.classList.remove('opacity-50', 'cursor-not-allowed');
        }
        // The finally block in fetchStatus will re-enable the button on success.
    };

    actionButton.addEventListener('click', handleDbAction);

    // Initial load
    fetchStatus();

})();
