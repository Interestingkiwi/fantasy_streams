(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const controlsDiv = document.getElementById('matchup-controls');
    const tableContainer = document.getElementById('matchup-table-container');
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');
    const opponentSelect = document.getElementById('opponent-select');

    let pageData = null; // To store weeks, teams, matchups, etc.

    async function init() {
        try {
            const response = await fetch('/api/matchup_page_data');
            const data = await response.json();

            if (!response.ok || !data.db_exists) {
                throw new Error(data.error || 'Database has not been initialized.');
            }

            pageData = data;
            populateDropdowns();
            setupEventListeners();

            // Initial data load
            await updateOpponent();
            await fetchAndRenderTable();

        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.classList.remove('hidden');
            controlsDiv.classList.add('hidden');
            tableContainer.classList.add('hidden');
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
        opponentSelect.innerHTML = teamOptions;
    }

    async function updateOpponent() {
        const selectedWeek = parseInt(weekSelect.value, 10);
        const yourTeamName = yourTeamSelect.value;

        const matchup = pageData.matchups.find(m =>
            m.week === selectedWeek && (m.team1 === yourTeamName || m.team2 === yourTeamName)
        );

        if (matchup) {
            const opponentName = matchup.team1 === yourTeamName ? matchup.team2 : matchup.team1;
            opponentSelect.value = opponentName;
        } else {
            // If no matchup found (e.g., playoffs), just pick the next team in the list
            const yourTeamIndex = yourTeamSelect.selectedIndex;
            const opponentIndex = (yourTeamIndex + 1) % yourTeamSelect.options.length;
            if(yourTeamIndex === opponentIndex) { // handle league with only one team
                 opponentSelect.selectedIndex = yourTeamIndex;
            } else {
                 opponentSelect.selectedIndex = opponentIndex;
            }
        }
    }

    async function fetchAndRenderTable() {
        const selectedWeek = weekSelect.value;
        const yourTeamName = yourTeamSelect.value;
        const opponentName = opponentSelect.value;

        if (!selectedWeek || !yourTeamName || !opponentName) {
            tableContainer.innerHTML = '<p class="text-gray-400">Please make all selections.</p>';
            return;
        }

        tableContainer.innerHTML = '<p class="text-gray-400">Loading matchup stats...</p>';

        try {
            const response = await fetch('/api/matchup_team_stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    week: selectedWeek,
                    team1_name: yourTeamName,
                    team2_name: opponentName
                })
            });

            const stats = await response.json();
            if (!response.ok) throw new Error(stats.error || 'Failed to fetch stats.');

            renderTable(stats, yourTeamName, opponentName);

        } catch(error) {
            console.error('Error fetching stats:', error);
            tableContainer.innerHTML = `<p class="text-red-400">Error: ${error.message}</p>`;
        }
    }

    function renderTable(stats, yourTeamName, opponentName) {
        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <table class="min-w-full divide-y divide-gray-700">
                    <thead class="bg-gray-700/50">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Category</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-bold text-gray-300 uppercase tracking-wider">${yourTeamName} (Live)</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-bold text-gray-300 uppercase tracking-wider">${yourTeamName} (ROW)</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-bold text-gray-300 uppercase tracking-wider">${opponentName} (Live)</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-bold text-gray-300 uppercase tracking-wider">${opponentName} (ROW)</th>
                        </tr>
                    </thead>
                    <tbody class="bg-gray-800 divide-y divide-gray-700">
        `;

        const goalieCats = {
            'SV%': ['SV', 'SA'],
            'GAA': ['GA']
        };
        const allGoalieSubCats = Object.values(goalieCats).flat();
        const addedGoalieStats = new Set();

        pageData.scoring_categories.forEach(cat => {
            const category = cat.category;

            if (addedGoalieStats.has(category)) {
                return;
            }

            const isBold = !allGoalieSubCats.includes(category);
            const fontWeight = isBold ? 'font-bold' : 'font-normal';

            tableHtml += `
                <tr class="hover:bg-gray-700/50">
                    <td class="px-6 py-4 whitespace-nowrap text-sm ${fontWeight} text-gray-300">${category}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team1.live[category] || 0}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team1.row[category] || 0}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team2.live[category] || 0}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team2.row[category] || 0}</td>
                </tr>
            `;

            if (goalieCats[category]) {
                goalieCats[category].forEach(subCat => {
                    if(pageData.scoring_categories.some(c => c.category === subCat)) {
                        addedGoalieStats.add(subCat);
                        tableHtml += `
                            <tr class="hover:bg-gray-700/50">
                                <td class="px-6 py-4 whitespace-nowrap text-sm font-normal text-gray-400 pl-8">${subCat}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team1.live[subCat] || 0}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team1.row[subCat] || 0}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team2.live[subCat] || 0}</td>
                                <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${stats.team2.row[subCat] || 0}</td>
                            </tr>
                        `;
                    }
                });
            }
        });

        tableHtml += `
                    </tbody>
                </table>
            </div>
        `;
        tableContainer.innerHTML = tableHtml;
    }

    function setupEventListeners() {
        weekSelect.addEventListener('change', async () => {
            await updateOpponent();
            await fetchAndRenderTable();
        });
        yourTeamSelect.addEventListener('change', async () => {
            await updateOpponent();
            await fetchAndRenderTable();
        });
        opponentSelect.addEventListener('change', fetchAndRenderTable);
    }

    init();
})();
