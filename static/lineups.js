document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('lineups-container');
    const contentDiv = document.getElementById('lineups-content');
    const errorDiv = document.getElementById('db-error-message');
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    let pollingInterval = null;
    let pollCount = 0;
    const maxPolls = 30; // Stop polling after 60 seconds

    async function init() {
        const selectedDb = localStorage.getItem('selectedDb');
        const selectedTeamId = localStorage.getItem('selectedTeamId');
        const selectedWeek = localStorage.getItem('selectedWeek');
        const useTestDb = localStorage.getItem('use_test_db') === 'true';

        try {
            // 1. Client-side check for selected values
            if (!selectedDb || !selectedTeamId || !selectedWeek) {
                throw new Error("Please select a League, Team, and Week on the Home page.");
            }

            // 2. Server-side check to ensure DB file exists
            const precheckUrl = `/api/lineups_precheck?league_db_name=${encodeURIComponent(selectedDb)}&use_test_db=${useTestDb}`;
            const response = await fetch(precheckUrl);
            const precheckData = await response.json();

            if (!response.ok || !precheckData.db_exists) {
                throw new Error(precheckData.error || "The selected database file could not be found on the server.");
            }

            // 3. If all checks pass, start the generation process
            startLineupGeneration(selectedDb, selectedTeamId, selectedWeek, useTestDb);

        } catch (error) {
            console.error('Initialization failed:', error);
            errorDiv.querySelector('.text-sm').textContent = error.message;
            errorDiv.classList.remove('hidden');
            contentDiv.classList.add('hidden');
        }
    }

    function startLineupGeneration(selectedDb, selectedTeamId, selectedWeek, useTestDb) {
        console.log("Attempting to start lineup generation with:", { selectedDb, selectedTeamId, selectedWeek, useTestDb });
        container.innerHTML = '<div class="loader">Requesting lineup generation...</div>';

        fetch('/api/start_lineup_generation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                league_db_name: selectedDb,
                team_id: selectedTeamId,
                week: selectedWeek,
                use_test_db: useTestDb
            })
        })
        .then(response => {
            if (response.status === 202) {
                console.log("Server accepted request. Starting to poll for results.");
                container.innerHTML = '<div class="loader">Generating optimal lineups... This may take a moment.</div>';
                pollForLineups(selectedDb, selectedTeamId, selectedWeek, useTestDb);
            } else {
                 return response.json().then(err => { throw new Error(err.error || `Server rejected the request with status: ${response.status}`) });
            }
        })
        .catch(error => {
            console.error('Error starting lineup generation:', error);
            container.innerHTML = `<div class="loader error-message">Error starting process: ${error.message}</div>`;
        });
    }

    function pollForLineups(selectedDb, selectedTeamId, selectedWeek, useTestDb) {
        if (pollingInterval) clearInterval(pollingInterval);
        pollCount = 0;

        const apiUrl = `/api/lineups?league_db_name=${encodeURIComponent(selectedDb)}&team_id=${encodeURIComponent(selectedTeamId)}&week=${encodeURIComponent(selectedWeek)}&use_test_db=${useTestDb}`;

        pollingInterval = setInterval(() => {
            if (pollCount >= maxPolls) {
                clearInterval(pollingInterval);
                container.innerHTML = '<div class="loader error-message">Process timed out. The server is taking too long to generate lineups. Please try again later.</div>';
                return;
            }

            console.log(`Polling for results... (Attempt ${pollCount + 1})`);
            fetch(apiUrl)
                .then(response => {
                    if (!response.ok) return response.json().then(err => { throw new Error(err.error || `HTTP error! status: ${response.status}`) });
                    return response.json();
                })
                .then(data => {
                    if (Object.keys(data).length > 0) {
                        console.log("Success! Received lineup data:", data);
                        clearInterval(pollingInterval);
                        renderLineups(data);
                    } else {
                        pollCount++;
                    }
                })
                .catch(error => {
                    console.error('Error during polling:', error);
                    clearInterval(pollingInterval);
                    container.innerHTML = `<div class="loader error-message">Error fetching lineup data: ${error.message}.</div>`;
                });
        }, 2000);
    }

    function renderLineups(lineupData) {
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

    // Start the process
    init();
});
