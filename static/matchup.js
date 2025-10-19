(async function() {
    // This delay is critical because the HTML is loaded dynamically by another script.
    // It ensures the DOM elements are available before the script tries to access them.
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const controlsDiv = document.getElementById('matchup-controls');
    const skaterTableContainer = document.getElementById('skater-stats-container');
    const goalieTableContainer = document.getElementById('goalie-stats-container');
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');
    const opponentSelect = document.getElementById('opponent-select');

    // Stat ID mappings
    const skaterStatIds = new Set([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 31, 32, 29, 33, 34]);
    const goalieStatIds = new Set([18, 19, 20, 22, 23, 24, 25, 26, 27, 28, 30]);

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

            // Initial data load, following the original working file's logic
            await updateOpponent();
            await fetchAndRenderTables();

        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.textContent = `Error: ${error.message}`;
            errorDiv.classList.remove('hidden');
            controlsDiv.classList.add('hidden');
            skaterTableContainer.classList.add('hidden');
            goalieTableContainer.classList.add('hidden');
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

    async function fetchAndRenderTables() {
        // This function's logic is identical to the original, but calls a new rendering function.
        const team1Key = yourTeamSelect.value;
        const team2Key = opponentSelect.value;
        const week = weekSelect.value;

        if (!team1Key || !team2Key || !week || team2Key === "") {
            skaterTableContainer.innerHTML = '<p class="text-center text-gray-400">Please select a valid matchup.</p>';
            goalieTableContainer.innerHTML = '';
            return;
        }

        try {
            const response = await fetch(`/api/matchup_data?team1_key=${team1Key}&team2_key=${team2Key}&week=${week}`);
            if (!response.ok) throw new Error('Failed to fetch matchup data.');
            const stats = await response.json();
            renderSplitTables(stats); // Call the new rendering function
        } catch (error) {
            console.error('Error fetching matchup data:', error);
            skaterTableContainer.innerHTML = `<p class="text-center text-red-400">Could not load matchup data.</p>`;
            goalieTableContainer.innerHTML = '';
        }
    }

    function renderSplitTables(stats) {
        // New function to handle splitting the data into two tables.
        if (!stats || !pageData || !pageData.categories) {
            skaterTableContainer.innerHTML = '<p class="text-center text-gray-400">No data to display.</p>';
            goalieTableContainer.innerHTML = '';
            return;
        }

        const skaterCategories = pageData.categories.filter(cat => skaterStatIds.has(cat.stat_id));
        const goalieCategories = pageData.categories.filter(cat => goalieStatIds.has(cat.stat_id));

        skaterTableContainer.innerHTML = generateTableHtml('Skater Stats', skaterCategories, stats);
        goalieTableContainer.innerHTML = generateTableHtml('Goalie Stats', goalieCategories, stats);
    }

    function generateTableHtml(title, categories, stats) {
        // New helper function to generate the HTML for a single table.
        // This contains the rendering logic from the original file.
        if (categories.length === 0) return '';

        let tableHtml = `
            <h2 class="text-xl font-semibold text-white mb-2">${title}</h2>
            <div class="overflow-x-auto relative shadow-md rounded-lg">
                <table class="w-full text-sm text-left text-gray-400">
                    <thead class="text-xs uppercase bg-gray-700 text-gray-300">
                        <tr>
                            <th scope="col" class="px-6 py-3">Category</th>
                            <th scope="col" class="px-6 py-3 text-center">${stats.team1.name} (Live)</th>
                            <th scope="col" class="px-6 py-3 text-center">${stats.team1.name} (RoW)</th>
                            <th scope="col" class="px-6 py-3 text-center">${stats.team2.name} (Live)</th>
                            <th scope="col" class="px-6 py-3 text-center">${stats.team2.name} (RoW)</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        categories.forEach(category => {
            const catName = category.name;
            const isBetter = category.is_better;

            let team1Live = stats.team1.live[catName] || 0;
            let team2Live = stats.team2.live[catName] || 0;
            let team1Row = stats.team1.row[catName] || 0;
            let team2Row = stats.team2.row[catName] || 0;

            if (catName === 'SV%') {
                const t1_sv_live = stats.team1.live['SV'] || 0;
                const t1_sa_live = stats.team1.live['SA'] || 0;
                team1Live = t1_sa_live > 0 ? (t1_sv_live / t1_sa_live).toFixed(3) : '0.000';

                const t2_sv_live = stats.team2.live['SV'] || 0;
                const t2_sa_live = stats.team2.live['SA'] || 0;
                team2Live = t2_sa_live > 0 ? (t2_sv_live / t2_sa_live).toFixed(3) : '0.000';

                const t1_sv_row = stats.team1.row['SV'] || 0;
                const t1_sa_row = stats.team1.row['SA'] || 0;
                team1Row = t1_sa_row > 0 ? (t1_sv_row / t1_sa_row).toFixed(3) : '0.000';

                const t2_sv_row = stats.team2.row['SV'] || 0;
                const t2_sa_row = stats.team2.row['SA'] || 0;
                team2Row = t2_sa_row > 0 ? (t2_sv_row / t2_sa_row).toFixed(3) : '0.000';
            }

            if (catName === 'GAA') {
                const t1_ga_live = stats.team1.live['GA'] || 0;
                const t1_toi_live = stats.team1.live['TOI/G'] || 0;
                team1Live = t1_toi_live > 0 ? ((t1_ga_live * 60) / t1_toi_live).toFixed(2) : '0.00';

                const t2_ga_live = stats.team2.live['GA'] || 0;
                const t2_toi_live = stats.team2.live['TOI/G'] || 0;
                team2Live = t2_toi_live > 0 ? ((t2_ga_live * 60) / t2_toi_live).toFixed(2) : '0.00';

                const t1_ga_row = stats.team1.row['GA'] || 0;
                const t1_toi_row = stats.team1.row['TOI/G'] || 0;
                team1Row = t1_toi_row > 0 ? ((t1_ga_row * 60) / t1_toi_row).toFixed(2) : '0.00';

                const t2_ga_row = stats.team2.row['GA'] || 0;
                const t2_toi_row = stats.team2.row['TOI/G'] || 0;
                team2Row = t2_toi_row > 0 ? ((t2_ga_row * 60) / t2_toi_row).toFixed(2) : '0.00';
            }

            let team1LiveClass = 'text-gray-300';
            let team2LiveClass = 'text-gray-300';

            if (isBetter === 'is_higher_better') {
                if (parseFloat(team1Live) > parseFloat(team2Live)) {
                    team1LiveClass = 'text-green-400 font-bold';
                    team2LiveClass = 'text-red-400';
                } else if (parseFloat(team2Live) > parseFloat(team1Live)) {
                    team2LiveClass = 'text-green-400 font-bold';
                    team1LiveClass = 'text-red-400';
                }
            } else if (isBetter === 'is_lower_better') {
                if (parseFloat(team1Live) !== 0 || parseFloat(team2Live) !== 0) {
                     if (parseFloat(team1Live) < parseFloat(team2Live) && parseFloat(team1Live) !== 0) {
                        team1LiveClass = 'text-green-400 font-bold';
                        team2LiveClass = 'text-red-400';
                    } else if (parseFloat(team2Live) < parseFloat(team1Live) && parseFloat(team2Live) !== 0) {
                        team2LiveClass = 'text-green-400 font-bold';
                        team1LiveClass = 'text-red-400';
                    }
                }
            }

            tableHtml += `
                <tr class="border-b border-gray-700 bg-gray-800 hover:bg-gray-700/50">
                    <th scope="row" class="px-6 py-4 font-medium whitespace-nowrap text-white">${catName}</th>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center ${team1LiveClass}">${team1Live}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1Row}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center ${team2LiveClass}">${team2Live}</td>
                    <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2Row}</td>
                </tr>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        return tableHtml;
    }

    function setupEventListeners() {
        // This function is identical to the original, working version.
        weekSelect.addEventListener('change', async () => {
            await updateOpponent();
            await fetchAndRenderTables();
        });
        yourTeamSelect.addEventListener('change', async () => {
            await updateOpponent();
            await fetchAndRenderTables();
        });
        opponentSelect.addEventListener('change', fetchAndRenderTables);
    }

    // Initialize the page
    init();
})();
