document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button');
    const timestampText = document.getElementById('timestamp-text');

    async function handleLogout() {
        await fetch('/logout');
        window.location.href = '/';
    }

    async function getTimestamp() {
        try {
            const response = await fetch('/api/get_league_timestamp');
            if (!response.ok) {
                throw new Error('Could not fetch timestamp');
            }
            const data = await response.json();
            if (data.timestamp) {
                const date = new Date(data.timestamp * 1000);
                timestampText.textContent = `League data last updated: ${date.toLocaleString()}`;
            } else {
                 timestampText.textContent = 'Could not retrieve last update time.';
            }
        } catch (error) {
            console.error('Error fetching timestamp:', error);
            timestampText.textContent = 'Error loading league data.';
        }
    }

    logoutButton.addEventListener('click', handleLogout);

    getTimestamp();
});
