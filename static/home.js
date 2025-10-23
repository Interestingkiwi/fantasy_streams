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

        // --- EDITED SECTION ---
        // Restore team selection from localStorage
        const savedTeam = localStorage.getItem('selectedTeam');
        if (savedTeam) {
            yourTeamSelect.value = savedTeam;
        }

        // Check if a session has started to handle the week selection
        if (!sessionStorage.getItem('fantasySessionStarted')) {
            // This is a new session. Default to the current week.
            const currentWeek = pageData.current_week;
            weekSelect.value = currentWeek;
            // Save it to localStorage so it persists during navigation
            localStorage.setItem('selectedWeek', currentWeek);
            // Mark the session as started
            sessionStorage.setItem('fantasySessionStarted', 'true');
        } else {
            // A session is active. Restore the last selected week from localStorage.
            const savedWeek = localStorage.getItem('selectedWeek');
            if (savedWeek) {
                weekSelect.value = savedWeek;
            } else {
                 // As a fallback, use the current week if nothing is in localStorage
                weekSelect.value = pageData.current_week;
            }
        }
        // --- END EDITED SECTION ---
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
