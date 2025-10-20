document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button');
    const timestampText = document.getElementById('timestamp-text');
    const weekDropdown = document.getElementById('global-week-dropdown');
    const teamDropdown = document.getElementById('global-your-team-dropdown');

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

    function populateWeekDropdown() {
        const savedWeek = localStorage.getItem('selectedWeek') || '1';
        for (let i = 1; i <= 26; i++) {
            const option = document.createElement('option');
            option.value = i;
            option.textContent = `Week ${i}`;
            if (i == savedWeek) {
                option.selected = true;
            }
            weekDropdown.appendChild(option);
        }
        localStorage.setItem('selectedWeek', weekDropdown.value);
    }

    async function initializeApp() {
        populateWeekDropdown();

        try {
            const response = await fetch('/get_teams');
            const teams = await response.json();

            teamDropdown.innerHTML = ''; // Clear existing options
            const savedTeam = localStorage.getItem('selectedTeam');

            teams.forEach(team => {
                const option = document.createElement('option');
                option.value = team;
                option.textContent = team;
                if (team === savedTeam) {
                    option.selected = true;
                }
                teamDropdown.appendChild(option);
            });

            // If no team was saved or the saved team is not in the list, default to the first team
            if (!savedTeam || !teams.includes(savedTeam)) {
                if (teams.length > 0) {
                    teamDropdown.value = teams[0];
                    localStorage.setItem('selectedTeam', teams[0]);
                }
            } else {
                 localStorage.setItem('selectedTeam', savedTeam);
            }

        } catch (error) {
            console.error('Failed to fetch teams:', error);
        }

        // Load the initial page after dropdowns are populated
        loadPage(currentPage);
    }



    weekDropdown.addEventListener('change', () => {
        localStorage.setItem('selectedWeek', weekDropdown.value);
        loadPage(currentPage); // Reload the current page content to reflect the change
    });

    teamDropdown.addEventListener('change', () => {
        localStorage.setItem('selectedTeam', teamDropdown.value);
        // Also clear the opponent, as the old one might be the new "your team"
        localStorage.removeItem('selectedOpponent');
        loadPage(currentPage); // Reload the current page content
    });


    if(logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }

    if(timestampText) {
        getTimestamp();
    }
    initializeApp();
});
