(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const controlsDiv = document.getElementById('lineup-controls');
    const tableContainer = document.getElementById('roster-table-container');
    const optimalLineupContainer = document.getElementById('optimal-lineup-container');
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');

    let pageData = null; // To store weeks and teams

    async function init() {
        try {
            const response = await fetch('/api/lineup_page_data');
            const data = await response.json();

            if (!response.ok || !data.db_exists) {
                throw new Error(data.error || 'Database has not been initialized.');
            }

            pageData = data;
            populateDropdowns();
            setupEventListeners();

            // Initial data load
            await fetchAndRenderTable();

            controlsDiv.classList.remove('hidden');

        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.classList.remove('hidden');
            controlsDiv.classList.add('hidden');
            tableContainer.classList.add('hidden');
            optimalLineupContainer.classList.add('hidden');
        }
    }

    function populateDropdowns() {
        // Populate Weeks
        weekSelect.innerHTML = pageData.weeks.map(week =>
            `<option value="${week.week_num}" ${week.week_num === pageData.current_week ? 'selected' : ''}>
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');

        // Populate Teams
        const teamOptions = pageData.teams.map(team =>
            `<option value="${team.name}">${team.name}</option>`
        ).join('');
        yourTeamSelect.innerHTML = teamOptions;
    }

    async function fetchAndRenderTable() {
        const selectedWeek = weekSelect.value;
        const yourTeamName = yourTeamSelect.value;

        if (!selectedWeek || !yourTeamName) {
            tableContainer.innerHTML = '<p class="text-gray-400">Please make all selections.</p>';
            return;
        }

        tableContainer.innerHTML = '<p class="text-gray-400">Loading roster...</p>';
        optimalLineupContainer.innerHTML = '<p class="text-gray-400">Calculating optimal lineup...</p>';

        try {
            const response = await fetch('/api/roster_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    week: selectedWeek,
                    team_name: yourTeamName,
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch roster.');

            renderTable(data.players, data.scoring_categories);
            renderOptimalLineup(data.optimal_lineup);


        } catch(error) {
            console.error('Error fetching roster:', error);
            tableContainer.innerHTML = `<p class="text-red-400">Error: ${error.message}</p>`;
            optimalLineupContainer.innerHTML = '';
        }
    }

    function renderTable(roster, scoringCategories) {
        const positionOrder = ['C', 'LW', 'RW', 'D', 'G', 'IR', 'IR+'];

        roster.sort((a, b) => {
            const posA = a.eligible_positions.split(',').map(p => p.trim());
            const posB = b.eligible_positions.split(',').map(p => p.trim());

            const maxIndexA = Math.max(...posA.map(p => positionOrder.indexOf(p)));
            const maxIndexB = Math.max(...posB.map(p => positionOrder.indexOf(p)));

            return maxIndexA - maxIndexB;
        });

        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <table class="min-w-full divide-y divide-gray-700">
                    <thead class="bg-gray-700/50">
                        <tr>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Player Name</th>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Team</th>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Positions</th>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Games This Week</th>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Games Next Week</th>
        `;

        scoringCategories.forEach(cat => {
            tableHtml += `<th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">${cat}</th>`;
        });

        tableHtml += `
                        </tr>
                    </thead>
                    <tbody class="bg-gray-800 divide-y divide-gray-700">
        `;

        roster.forEach(player => {
            tableHtml += `
                <tr class="hover:bg-gray-700/50">
                    <td class="px-2 py-1 whitespace-nowrap text-sm font-medium text-gray-300">${player.player_name}</td>
                    <td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${player.team}</td>
                    <td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${player.eligible_positions}</td>
                    <td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${player.games_this_week.join(', ')}</td>
                    <td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${player.games_next_week.join(', ')}</td>
            `;

            scoringCategories.forEach(cat => {
                const rank = player[cat + '_cat_rank'] !== null && player[cat + '_cat_rank'] !== undefined ? player[cat + '_cat_rank'] : '-';
                tableHtml += `<td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${rank}</td>`;
            });

            tableHtml += `
                </tr>
            `;
        });

        tableHtml += `
                    </tbody>
                </table>
            </div>
        `;
        tableContainer.innerHTML = tableHtml;
    }

    
    function renderOptimalLineup(lineup) {
        const positionOrder = ['C', 'LW', 'RW', 'D', 'G'];
        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <h2 class="text-xl font-bold text-white p-2">Optimal Lineup</h2>
                <table class="min-w-full divide-y divide-gray-700">
                    <thead class="bg-gray-700/50">
                        <tr>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Position</th>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Player Name</th>
                            <th scope="col" class="px-2 py-1 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Total Rank</th>
                        </tr>
                    </thead>
                    <tbody class="bg-gray-800 divide-y divide-gray-700">
        `;

        positionOrder.forEach(pos => {
            if (lineup[pos]) {
                lineup[pos].forEach(player => {
                    tableHtml += `
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-2 py-1 whitespace-nowrap text-sm font-medium text-gray-300">${pos}</td>
                            <td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${player.player_name}</td>
                            <td class="px-2 py-1 whitespace-nowrap text-sm text-gray-300">${player.total_rank}</td>
                        </tr>
                    `;
                });
            }
        });


        tableHtml += `
                    </tbody>
                </table>
            </div>
        `;
        optimalLineupContainer.innerHTML = tableHtml;
    }


    function setupEventListeners() {
        weekSelect.addEventListener('change', fetchAndRenderTable);
        yourTeamSelect.addEventListener('change', fetchAndRenderTable);
    }

    init();
})();
