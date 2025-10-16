document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button');
    const timestampText = document.getElementById('timestamp-text');
    const refreshButton = document.getElementById('refresh-data-button');

    let statusInterval;
    let currentLeagueId;

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

    async function getCurrentLeagueId() {
        try {
            const response = await fetch('/api/get_current_league_id');
            const data = await response.json();
            if (data.league_id) {
                currentLeagueId = data.league_id;
            }
        } catch (error) {
            console.error("Error fetching league ID:", error);
        }
    }

    async function handleRefreshData() {
        if (!currentLeagueId) {
            alert('Could not identify the current league. Please refresh the page.');
            return;
        }

        refreshButton.disabled = true;
        refreshButton.textContent = 'Refreshing...';
        timestampText.textContent = 'Updating league data. This may take a few minutes...';

        try {
            const response = await fetch('/api/refresh_league', { method: 'POST' });
            const data = await response.json();
            if (data.status === 'refreshing') {
                statusInterval = setInterval(() => checkLeagueStatus(currentLeagueId), 5000);
            } else {
                throw new Error(data.message || 'Failed to start refresh.');
            }
        } catch (error) {
            console.error('Error refreshing league:', error);
            timestampText.textContent = 'Error starting data refresh.';
            refreshButton.disabled = false;
            refreshButton.textContent = 'Refresh League Data';
        }
    }

    async function checkLeagueStatus(leagueId) {
        try {
            const response = await fetch(`/api/league_status/${leagueId}`);
            const data = await response.json();

            if (data.status === 'complete') {
                clearInterval(statusInterval);
                window.location.reload(); // Reload the page to get fresh data
            } else if (data.status === 'error') {
                 clearInterval(statusInterval);
                 console.error('Database refresh failed:', data.message);
                 timestampText.textContent = 'Database refresh failed.';
                 refreshButton.disabled = false;
                 refreshButton.textContent = 'Refresh League Data';
            }
            // If status is 'refreshing' or 'initializing', continue polling.
        } catch (error) {
             clearInterval(statusInterval);
             console.error('Error checking league status:', error);
             timestampText.textContent = 'Error checking refresh status.';
             refreshButton.disabled = false;
             refreshButton.textContent = 'Refresh League Data';
        }
    }

    logoutButton.addEventListener('click', handleLogout);
    refreshButton.addEventListener('click', handleRefreshData);

    // Initial calls
    getCurrentLeagueId();
    getTimestamp();
});
