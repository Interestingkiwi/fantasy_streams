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
        // Populate Week dropdown
        pageData.weeks.forEach(week => {
            const option = new Option(`Week ${week}`, week);
            weekSelect.add(option);
        });
        weekSelect.value = pageData.current_week;

        // Populate Your Team dropdown
        pageData.teams.forEach(team => {
            const option = new Option(team.name, team.team_id);
            yourTeamSelect.add(option);
        });
        yourTeamSelect.value = pageData.your_team_id;
    }

    async function updateOpponent() {
        const selectedWeek = weekSelect.value;
        const yourTeamId = yourTeamSelect.value;
        const currentOpponentId = opponentSelect.value;

        const matchup = pageData.matchups[selectedWeek].find(m => m.includes(parseInt(yourTeamId)));
        if (!matchup) {
            opponentSelect.innerHTML = ''; // no matchup found
            return;
        }

        const opponentId = matchup.find(id => id !== parseInt(yourTeamId));
        const opponent = pageData.teams.find(t => t.team_id === opponentId);

        opponentSelect.innerHTML = '';
        if (opponent) {
            const option = new Option(opponent.name, opponent.team_id);
            opponentSelect.add(option);
            opponentSelect.value = opponent.team_id;
        } else {
             // Handle case where opponent might not be in the teams list for some reason
             const placeholderOption = new Option('No Opponent Found', '');
             opponentSelect.add(placeholderOption);
        }
    }


    async function fetchAndRenderTable() {
        const week = weekSelect.value;
        const team1 = yourTeamSelect.value;
        const team2 = opponentSelect.value;

        if (!week || !team1 || !team2) return;

        try {
            const response = await fetch(`/api/matchup_stats?week=${week}&team1_id=${team1}&team2_id=${team2}`);
            if (!response.ok) {
                throw new Error('Failed to fetch matchup stats.');
            }
            const stats = await response.json();
            renderTable(stats);
        } catch (error) {
            console.error('Error fetching/rendering stats:', error);
            tableContainer.innerHTML = `<p class="error-message">Could not load matchup data.</p>`;
        }
    }

    function renderTable(stats) {
        const statCategories = {
            "Forwards/Defensemen": ["G", "A", "+/-", "PIM", "PPP", "SOG", "FW", "HIT", "BLK"],
            "Goaltending": ["GS", "W", "GA", "SV", "SHO", "GAA", "SV%"], // Reordered for better flow
            "Team": ["IR", "IR+", "NA", "Movers"]
        };

        let tableHtml = `
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-800">
                    <thead class="bg-gray-900/50">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider pl-8">Category</th>
                            <th scope="col" colspan="2" class="px-6 py-3 text-center text-xs font-medium text-gray-300 uppercase tracking-wider">${stats.team1.name}</th>
                            <th scope="col" colspan="2" class="px-6 py-3 text-center text-xs font-medium text-gray-300 uppercase tracking-wider">${stats.team2.name}</th>
                        </tr>
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider pl-8"></th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-300 uppercase tracking-wider">Live</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-300 uppercase tracking-wider">R.O.W.</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-300 uppercase tracking-wider">Live</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-300 uppercase tracking-wider">R.O.W.</th>
                        </tr>
                    </thead>
                    <tbody class="bg-gray-900/20 divide-y divide-gray-800">
        `;

        Object.keys(statCategories).forEach(category => {
            tableHtml += `
                <tr class="bg-gray-800/50">
                    <td class="px-6 py-3 whitespace-nowrap text-sm font-medium text-gray-200 pl-8" colspan="5">${category}</td>
                </tr>
            `;

            if (statCategories[category]) {
                statCategories[category].forEach(subCat => {
                    let t1_live_val, t1_row_val, t2_live_val, t2_row_val;

                    if (subCat === 'GAA') {
                        // FIX: Manually calculate GAA = GA / GS to ensure accuracy
                        t1_live_val = (stats.team1.live.GS && stats.team1.live.GS > 0) ? (stats.team1.live.GA / stats.team1.live.GS).toFixed(2) : '0.00';
                        t1_row_val = (stats.team1.row.GS && stats.team1.row.GS > 0) ? (stats.team1.row.GA / stats.team1.row.GS).toFixed(2) : '0.00';
                        t2_live_val = (stats.team2.live.GS && stats.team2.live.GS > 0) ? (stats.team2.live.GA / stats.team2.live.GS).toFixed(2) : '0.00';
                        t2_row_val = (stats.team2.row.GS && stats.team2.row.GS > 0) ? (stats.team2.row.GA / stats.team2.row.GS).toFixed(2) : '0.00';
                    } else if (subCat === 'SV%') {
                        // FIX: Manually calculate SV% = SV / (SV + GA) to ensure accuracy
                        const calc_sv_pct = (sv, ga) => {
                            const total_shots = (sv || 0) + (ga || 0);
                            // Format as .XXX, which is standard for SV%
                            return total_shots > 0 ? (sv / total_shots).toFixed(3).substring(1) : '.000';
                        };
                        t1_live_val = calc_sv_pct(stats.team1.live.SV, stats.team1.live.GA);
                        t1_row_val = calc_sv_pct(stats.team1.row.SV, stats.team1.row.GA);
                        t2_live_val = calc_sv_pct(stats.team2.live.SV, stats.team2.live.GA);
                        t2_row_val = calc_sv_pct(stats.team2.row.SV, stats.team2.row.GA);
                    } else {
                        // Default behavior for all other stats
                        t1_live_val = stats.team1.live[subCat] || 0;
                        t1_row_val = stats.team1.row[subCat] || 0;
                        t2_live_val = stats.team2.live[subCat] || 0;
                        t2_row_val = stats.team2.row[subCat] || 0;
                    }

                    tableHtml += `
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-normal text-gray-400 pl-8">${subCat}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${t1_live_val}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${t1_row_val}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${t2_live_val}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${t2_row_val}</td>
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

    // Initialize the page
    init();

})();
