document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('lineups-container');
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    // Polling interval tracker
    let pollingInterval = null;
    let pollCount = 0;
    const maxPolls = 30; // Stop polling after 60 seconds (30 polls * 2s)

    function startLineupGeneration() {
        const selectedDb = localStorage.getItem('selectedDb');
        const selectedTeamId = localStorage.getItem('selectedTeamId');
        const selectedWeek = localStorage.getItem('selectedWeek');

        console.log("Attempting to start lineup generation with:", { selectedDb, selectedTeamId, selectedWeek });

        if (!selectedDb || !selectedTeamId || !selectedWeek) {
            container.innerHTML = '<div class="loader">Please select a league, team, and week from the Home page first.</div>';
            return;
        }

        container.innerHTML = '<div class="loader">Requesting lineup generation...</div>';

        // Step 1: Send a request to START the generation process
        fetch('/api/start_lineup_generation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                league_db_name: selectedDb,
                team_id: selectedTeamId,
                week: selectedWeek
            })
        })
        .then(response => {
            if (response.status === 202) { // 202 Accepted
                console.log("Server accepted the generation request. Starting to poll for results.");
                container.innerHTML = '<div class="loader">Generating optimal lineups... This may take a moment.</div>';
                // Step 2: If server accepts, start polling for the results
                pollForLineups();
            } else {
                throw new Error(`Server rejected the request with status: ${response.status}`);
            }
        })
        .catch(error => {
            console.error('Error starting lineup generation:', error);
            container.innerHTML = `<div class="loader">Error starting lineup generation: ${error.message}</div>`;
        });
    }

    function pollForLineups() {
        // Clear any existing polling interval
        if (pollingInterval) clearInterval(pollingInterval);
        pollCount = 0;

        const selectedDb = localStorage.getItem('selectedDb');
        const selectedTeamId = localStorage.getItem('selectedTeamId');
        const selectedWeek = localStorage.getItem('selectedWeek');

        const apiUrl = `/api/lineups?league_db_name=${encodeURIComponent(selectedDb)}&team_id=${encodeURIComponent(selectedTeamId)}&week=${encodeURIComponent(selectedWeek)}`;

        pollingInterval = setInterval(() => {
            if (pollCount >= maxPolls) {
                clearInterval(pollingInterval);
                container.innerHTML = '<div class="loader">Lineup generation is taking longer than expected. Please try refreshing the page later.</div>';
                console.error("Polling timed out.");
                return;
            }

            console.log(`Polling for results... (Attempt ${pollCount + 1})`);

            fetch(apiUrl)
                .then(response => {
                    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                    return response.json();
                })
                .then(data => {
                    // An empty object {} means the data is not ready yet
                    if (Object.keys(data).length > 0) {
                        console.log("Success! Received lineup data from server:", data);
                        clearInterval(pollingInterval);
                        renderLineups(data);
                    } else {
                        // Data not ready, continue polling
                        pollCount++;
                    }
                })
                .catch(error => {
                    console.error('Error fetching lineup data during poll:', error);
                    clearInterval(pollingInterval);
                    container.innerHTML = `<div class="loader">Error loading lineups: ${error.message}.</div>`;
                });
        }, 2000); // Poll every 2 seconds
    }

    function renderLineups(lineupData) {
        // This function remains the same as your latest version
        container.innerHTML = '';
        const sortedDates = Object.keys(lineupData).sort();

        sortedDates.forEach(dateStr => {
            const lineupDate = new Date(dateStr + 'T00:00:00');
            if (lineupDate < today) return;

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

    // Initial call to start the whole process
    startLineupGeneration();
});
