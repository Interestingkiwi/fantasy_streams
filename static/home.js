document.addEventListener('DOMContentLoaded', () => {
    const logoutButton = document.getElementById('logout-button');
    const timestampText = document.getElementById('timestamp-text');
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');

    let pageData = null; // To store weeks, teams, etc.

    async function handleLogout() {
        // Redirect to logout endpoint, which will clear the session
        window.location.href = '/logout';
    }

    async function getTimestamp() {
        try {
            timestampText.textContent = 'League data is loaded live from Yahoo.';
        } catch (error) {
            console.error('Error setting timestamp:', error);
            timestampText.textContent = 'Error loading league data status.';
        }
    }

    async function initDropdowns() {
        try {
            const response = await fetch('/api/matchup_page_data');
            const data = await response.json();

            if (!response.ok || !data.db_exists) {
                throw new Error(data.error || 'Database has not been initialized.');
            }

            pageData = data;
            populateDropdowns();

        } catch (error) {
            console.error('Initialization error for dropdowns:', error);
            // Optionally hide or disable dropdowns
            weekSelect.style.display = 'none';
            yourTeamSelect.style.display = 'none';
        }
    }

    function populateDropdowns() {
        // Populate Weeks
        weekSelect.innerHTML = pageData.weeks.map(week =>
            `<option value="${week.week_num}">
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');

        // Populate Teams
        const teamOptions = pageData.teams.map(team =>
            `<option value="${team.name}">${team.name}</option>`
        ).join('');
        yourTeamSelect.innerHTML = teamOptions;

        // Restore and set default dropdown values
        const savedWeek = localStorage.getItem('selectedWeek');
        if (savedWeek) {
            weekSelect.value = savedWeek;
        } else {
            // Set to current week if nothing is saved
            weekSelect.value = pageData.current_week;
        }

        const savedTeam = localStorage.getItem('selectedTeam');
        if (savedTeam) {
            yourTeamSelect.value = savedTeam;
        }
    }

    if(logoutButton) {
        logoutButton.addEventListener('click', handleLogout);
    }

    if(timestampText) {
        getTimestamp();
    }

    // Add event listeners to save dropdown values
    weekSelect.addEventListener('change', () => {
        localStorage.setItem('selectedWeek', weekSelect.value);
    });

    yourTeamSelect.addEventListener('change', () => {
        localStorage.setItem('selectedTeam', yourTeamSelect.value);
    });


    // Initialize the dropdowns
    initDropdowns();
});
