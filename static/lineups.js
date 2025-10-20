document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('lineups-container');
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    function fetchLineups() {
        // Get data from localStorage
        const selectedDb = localStorage.getItem('selectedDb'); // This is the full filename
        const selectedTeamId = localStorage.getItem('selectedTeamId');
        const selectedWeek = localStorage.getItem('selectedWeek');

        // --- Debugging Logs ---
        console.log("Attempting to fetch lineups with the following data:");
        console.log("Selected DB (filename):", selectedDb);
        console.log("Selected Team ID:", selectedTeamId);
        console.log("Selected Week:", selectedWeek);

        if (!selectedDb || !selectedTeamId || !selectedWeek) {
            container.innerHTML = '<div class="loader">Please select a league, team, and week from the Home page first.</div>';
            console.error("Missing required data in localStorage.");
            return;
        }

        container.innerHTML = '<div class="loader">Generating optimal lineups... This may take a moment.</div>';

        // Construct the URL with the correct parameter name the backend now expects
        const apiUrl = `/api/lineups?league_db_name=${selectedDb}&team_id=${selectedTeamId}&week=${selectedWeek}`;

        // --- Debugging Log ---
        console.log("Fetching from URL:", apiUrl);

        fetch(apiUrl)
            .then(response => {
                if (!response.ok) {
                    // Try to get more error details from the response body
                    return response.json().then(err => {
                        throw new Error(`HTTP error! status: ${response.status}, message: ${err.error || 'Unknown error'}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                renderLineups(data);
            })
            .catch(error => {
                // Log the full error to the console for better debugging
                console.error('Error fetching lineup data:', error);
                container.innerHTML = `<div class="loader">Error loading lineups: ${error.message}. Please check the console for more details.</div>`;
            });
    }

    function renderLineups(lineupData) {
        // ... (The renderLineups function remains the same as before) ...
        container.innerHTML = '';
        if (Object.keys(lineupData).length === 0) {
            container.innerHTML = '<div class="loader">No games found for your team in the selected week.</div>';
            return;
        }

        const sortedDates = Object.keys(lineupData).sort();

        sortedDates.forEach(dateStr => {
            const lineupDate = new Date(dateStr + 'T00:00:00');

            if (lineupDate < today) {
                return;
            }

            const dayCard = document.createElement('div');
            dayCard.className = 'day-card';

            const formattedDate = lineupDate.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' });
            dayCard.innerHTML = `<h3>${formattedDate}</h3>`;

            const table = document.createElement('table');
            table.className = 'lineup-table';
            table.innerHTML = `<thead><tr><th>Pos</th><th>Player</th></tr></thead>`;

            const tbody = document.createElement('tbody');

            const players = lineupData[dateStr];

            const activePlayers = players.filter(p => p.status === 'ACTIVE');
            const benchPlayers = players.filter(p => p.status === 'BENCH');

            activePlayers.forEach(player => {
                const row = tbody.insertRow();
                row.innerHTML = `<td>${player.played_position}</td><td>${player.player_name}</td>`;
            });

            benchPlayers.forEach(player => {
                const row = tbody.insertRow();
                row.className = 'bench-row';
                row.innerHTML = `<td>${player.played_position}</td><td>${player.player_name}</td>`;
            });

            table.appendChild(tbody);
            dayCard.appendChild(table);
            container.appendChild(dayCard);
        });

        if (container.innerHTML === '') {
             container.innerHTML = '<div class="loader">All games for the selected week have already passed.</div>';
        }
    }

    fetchLineups();
});
