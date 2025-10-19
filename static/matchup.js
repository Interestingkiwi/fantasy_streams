(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const controlsDiv = document.getElementById('matchup-controls');
    const skaterTableContainer = document.getElementById('skater-stats-container');
    const goalieTableContainer = document.getElementById('goalie-stats-container');
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
            await fetchAndRenderTables();

        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.classList.remove('hidden');
            controlsDiv.classList.add('hidden');
            skaterTableContainer.classList.add('hidden');
            goalieTableContainer.classList.add('hidden');
        }
    }

    function populateDropdowns() {
        // Populate Week dropdown
        weekSelect.innerHTML = '';
        pageData.weeks.forEach(week => {
            const option = document.createElement('option');
            option.value = week;
            option.textContent = `Week ${week}`;
            weekSelect.appendChild(option);
        });
        weekSelect.value = pageData.current_week;

        // Populate Your Team dropdown
        yourTeamSelect.innerHTML = '';
        pageData.teams.forEach(team => {
            const option = document.createElement('option');
            option.value = team.team_id;
            option.textContent = team.team_name;
            yourTeamSelect.appendChild(option);
        });
    }

    async function updateOpponent() {
        const selectedWeek = weekSelect.value;
        const yourTeamId = yourTeamSelect.value;
        const matchup = pageData.matchups[selectedWeek]?.find(m => m.team1_id == yourTeamId || m.team2_id == yourTeamId);

        if (matchup) {
            const opponentId = matchup.team1_id == yourTeamId ? matchup.team2_id : matchup.team1_id;
            const opponent = pageData.teams.find(t => t.team_id == opponentId);
            if (opponent) {
                opponentSelect.innerHTML = `<option value="${opponent.team_id}">${opponent.team_name}</option>`;
                opponentSelect.disabled = false;
            }
        } else {
            opponentSelect.innerHTML = '<option>No matchup found</option>';
            opponentSelect.disabled = true;
        }
    }

    async function fetchAndRenderTables() {
        const week = weekSelect.value;
        const yourTeamId = yourTeamSelect.value;
        const opponentId = opponentSelect.value;

        if (!week || !yourTeamId || !opponentId || opponentSelect.disabled) {
            skaterTableContainer.innerHTML = '<p class="text-center text-gray-400">Please select a valid matchup.</p>';
            goalieTableContainer.innerHTML = '';
            return;
        }

        try {
            const response = await fetch(`/api/matchup_data?week=${week}&team1_id=${yourTeamId}&team2_id=${opponentId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch matchup data.');
            }
            const stats = await response.json();
            renderTables(stats);
        } catch (error) {
            console.error('Error fetching matchup data:', error);
            skaterTableContainer.innerHTML = `<p class="text-center text-red-400">Error loading data: ${error.message}</p>`;
            goalieTableContainer.innerHTML = '';
        }
    }

    function renderTables(stats) {
        // Clear previous content
        skaterTableContainer.innerHTML = '';
        goalieTableContainer.innerHTML = '';

        if (!stats || !stats.categories || Object.keys(stats.categories).length === 0) {
            skaterTableContainer.innerHTML = '<p class="text-center text-gray-400">No stats to display for this matchup.</p>';
            return;
        }

        const team1Name = yourTeamSelect.options[yourTeamSelect.selectedIndex].text;
        const team2Name = opponentSelect.options[opponentSelect.selectedIndex].text;

        const tableHeaderHtml = (title, team1Name, team2Name) => `
            <h2 class="text-2xl font-semibold text-white mb-4">${title}</h2>
            <div class="overflow-x-auto rounded-lg shadow-md">
                <table class="min-w-full divide-y divide-gray-700">
                    <thead class="bg-gray-800">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-white uppercase tracking-wider pl-8" style="width: 20%;">Category</th>
                            <th scope="col" colspan="2" class="px-6 py-3 text-center text-xs font-medium text-white uppercase tracking-wider" style="width: 40%;">${team1Name}</th>
                            <th scope="col" colspan="2" class="px-6 py-3 text-center text-xs font-medium text-white uppercase tracking-wider" style="width: 40%;">${team2Name}</th>
                        </tr>
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider pl-8"></th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Live</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Proj.</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Live</th>
                            <th scope="col" class="px-6 py-3 text-center text-xs font-medium text-gray-400 uppercase tracking-wider">Proj.</th>
                        </tr>
                    </thead>
                    <tbody class="bg-gray-900 divide-y divide-gray-800">
        `;
        const tableFooterHtml = `
                    </tbody>
                </table>
            </div>
        `;

        // --- SKATER STATS ---
        const offensiveCatKey = Object.keys(stats.categories).find(k => k.toLowerCase() === 'offensive');
        if (offensiveCatKey && stats.categories[offensiveCatKey].length > 0) {
            let skaterTableHtml = tableHeaderHtml('Skater Stats', team1Name, team2Name);
            stats.categories[offensiveCatKey].forEach(subCat => {
                const team1Live = stats.team1?.live?.[subCat] || 0;
                const team1Proj = stats.team1?.row?.[subCat] || 0;
                const team2Live = stats.team2?.live?.[subCat] || 0;
                const team2Proj = stats.team2?.row?.[subCat] || 0;
                skaterTableHtml += `
                    <tr class="hover:bg-gray-700/50">
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-normal text-gray-400 pl-8">${subCat}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1Live}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1Proj}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2Live}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2Proj}</td>
                    </tr>
                `;
            });
            skaterTableHtml += tableFooterHtml;
            skaterTableContainer.innerHTML = skaterTableHtml;
        }

        // --- GOALIE STATS ---
        const goaltendingCatKey = Object.keys(stats.categories).find(k => k.toLowerCase() === 'goaltending');
        if (goaltendingCatKey && stats.categories[goaltendingCatKey].length > 0) {
            let goalieTableHtml = tableHeaderHtml('Goaltending Stats', team1Name, team2Name);
            stats.categories[goaltendingCatKey].forEach(subCat => {
                if (subCat === 'GAA') {
                    const team1_ga_live = stats.team1?.live?.['GA'] || 0;
                    const team1_toi_live = stats.team1?.live?.['TOI'] || 0;
                    const team1_gaa_live = team1_toi_live > 0 ? ((team1_ga_live * 60) / team1_toi_live).toFixed(2) : '0.00';

                    const team1_ga_proj = stats.team1?.row?.['GA'] || 0;
                    const team1_toi_proj = stats.team1?.row?.['TOI'] || 0;
                    const team1_gaa_proj = team1_toi_proj > 0 ? ((team1_ga_proj * 60) / team1_toi_proj).toFixed(2) : '0.00';

                    const team2_ga_live = stats.team2?.live?.['GA'] || 0;
                    const team2_toi_live = stats.team2?.live?.['TOI'] || 0;
                    const team2_gaa_live = team2_toi_live > 0 ? ((team2_ga_live * 60) / team2_toi_live).toFixed(2) : '0.00';

                    const team2_ga_proj = stats.team2?.row?.['GA'] || 0;
                    const team2_toi_proj = stats.team2?.row?.['TOI'] || 0;
                    const team2_gaa_proj = team2_toi_proj > 0 ? ((team2_ga_proj * 60) / team2_toi_proj).toFixed(2) : '0.00';

                    goalieTableHtml += `
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-300 pl-8">${subCat}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team1_gaa_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team1_gaa_proj}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team2_gaa_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team2_gaa_proj}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-normal text-gray-400 pl-12">GA</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1_ga_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1_ga_proj}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2_ga_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2_ga_proj}</td>
                        </tr>
                    `;
                } else if (subCat === 'SV%') {
                    const team1_sv_live = stats.team1?.live?.['SV'] || 0;
                    const team1_ga_live = stats.team1?.live?.['GA'] || 0;
                    const team1_sv_pct_live = (team1_sv_live + team1_ga_live > 0) ? (team1_sv_live / (team1_sv_live + team1_ga_live)).toFixed(3) : '.000';

                    const team1_sv_proj = stats.team1?.row?.['SV'] || 0;
                    const team1_ga_proj = stats.team1?.row?.['GA'] || 0;
                    const team1_sv_pct_proj = (team1_sv_proj + team1_ga_proj > 0) ? (team1_sv_proj / (team1_sv_proj + team1_ga_proj)).toFixed(3) : '.000';

                    const team2_sv_live = stats.team2?.live?.['SV'] || 0;
                    const team2_ga_live = stats.team2?.live?.['GA'] || 0;
                    const team2_sv_pct_live = (team2_sv_live + team2_ga_live > 0) ? (team2_sv_live / (team2_sv_live + team2_ga_live)).toFixed(3) : '.000';

                    const team2_sv_proj = stats.team2?.row?.['SV'] || 0;
                    const team2_ga_proj = stats.team2?.row?.['GA'] || 0;
                    const team2_sv_pct_proj = (team2_sv_proj + team2_ga_proj > 0) ? (team2_sv_proj / (team2_sv_proj + team2_ga_proj)).toFixed(3) : '.000';

                    goalieTableHtml += `
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-bold text-gray-300 pl-8">${subCat}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team1_sv_pct_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team1_sv_pct_proj}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team2_sv_pct_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center font-bold text-gray-300">${team2_sv_pct_proj}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-normal text-gray-400 pl-12">Saves</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1_sv_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1_sv_proj}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2_sv_live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2_sv_proj}</td>
                        </tr>
                    `;
                } else if (subCat !== 'GA' && subCat !== 'SV' && subCat !== 'TOI') {
                    const team1Live = stats.team1?.live?.[subCat] || 0;
                    const team1Proj = stats.team1?.row?.[subCat] || 0;
                    const team2Live = stats.team2?.live?.[subCat] || 0;
                    const team2Proj = stats.team2?.row?.[subCat] || 0;
                    goalieTableHtml += `
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-normal text-gray-400 pl-8">${subCat}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1Live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team1Proj}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2Live}</td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-center text-gray-300">${team2Proj}</td>
                        </tr>
                    `;
                }
            });
            goalieTableHtml += tableFooterHtml;
            goalieTableContainer.innerHTML = goalieTableHtml;
        }
    }


    function setupEventListeners() {
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

    init();

})();
