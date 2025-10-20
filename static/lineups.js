document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('lineups-container');
    const today = new Date();
    today.setHours(0, 0, 0, 0); // Normalize today's date

    function fetchLineups() {
        const selectedDb = localStorage.getItem('selectedDb');
        const selectedTeamId = localStorage.getItem('selectedTeamId');
        const selectedWeek = localStorage.getItem('selectedWeek');

        if (!selectedDb || !selectedTeamId || !selectedWeek) {
            container.innerHTML = '<div class="loader">Please select a league, team, and week from the Home page first.</div>';
            return;
        }

        container.innerHTML = '<div class="loader">Generating optimal lineups... This may take a moment.</div>';

        fetch(`/api/lineups?league_id=${selectedDb}&team_id=${selectedTeamId}&week=${selectedWeek}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                renderLineups(data);
            })
            .catch(error => {
                console.error('Error fetching lineup data:', error);
                container.innerHTML = `<div class="loader">Error loading lineups. Please try again.</div>`;
            });
    }

    function renderLineups(lineupData) {
        container.innerHTML = '';
        if (Object.keys(lineupData).length === 0) {
            container.innerHTML = '<div class="loader">No games found for your team in the selected week.</div>';
            return;
        }

        const sortedDates = Object.keys(lineupData).sort();

        sortedDates.forEach(dateStr => {
            const lineupDate = new Date(dateStr + 'T00:00:00'); // Treat date as local

            // Only show lineups from today onwards
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

            // Separate active and bench players
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
