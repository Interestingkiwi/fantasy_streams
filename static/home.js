document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button');
    const timestampText = document.getElementById('timestamp-text');

    async function handleLogout() {
        // Redirect to logout endpoint, which will clear the session
        window.location.href = '/logout';
    }

    async function getTimestamp() {
        try {
            // This API endpoint doesn't exist yet, so we'll just show a placeholder
            // const response = await fetch('/api/get_league_timestamp');
            // if (!response.ok) {
            //     throw new Error('Could not fetch timestamp');
            // }
            // const data = await response.json();
            // if (data.timestamp) {
            //     const date = new Date(data.timestamp * 1000);
            //     timestampText.textContent = `League data last updated: ${date.toLocaleString()}`;
            // } else {
            //      timestampText.textContent = 'Could not retrieve last update time.';
            // }
            timestampText.textContent = 'League data is loaded live from Yahoo.';
        } catch (error) {
            console.error('Error fetching timestamp:', error);
            timestampText.textContent = 'Error loading league data status.';
        }
    }

    if(logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }

    if(timestampText) {
        getTimestamp();
    }
});
