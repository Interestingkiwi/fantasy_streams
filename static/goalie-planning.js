(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const controlsDiv = document.getElementById('goalie-controls');
    const statsContainer = document.getElementById('stats-container');
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');

    let pageData = null; // To store weeks and teams

    async function init() {
        try {
            // Use the existing lineup_page_data endpoint to get weeks and teams
            const response = await fetch('/api/lineup_page_data');
            const data = await response.json();

            if (!response.ok || !data.db_exists) {
                throw new Error(data.error || 'Database has not been initialized.');
            }

            pageData = data;
            populateDropdowns();
            setupEventListeners();

            // Initial data load
            await fetchAndRenderStats();

            controlsDiv.classList.remove('hidden');

        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('hidden');
            controlsDiv.classList.add('hidden');
            statsContainer.classList.add('hidden');
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
        yourTeamSelect.innerHTML = pageData.teams.map(team =>
            `<option value="${team.name}">${team.name}</option>`
        ).join('');

        // Restore team selection from localStorage
        const savedTeam = localStorage.getItem('selectedTeam');
        if (savedTeam) {
            yourTeamSelect.value = savedTeam;
        }

        // Restore week selection
        if (!sessionStorage.getItem('fantasySessionStarted')) {
            const currentWeek = pageData.current_week;
            weekSelect.value = currentWeek;
            localStorage.setItem('selectedWeek', currentWeek);
            sessionStorage.setItem('fantasySessionStarted', 'true');
        } else {
            const savedWeek = localStorage.getItem('selectedWeek');
            weekSelect.value = savedWeek ? savedWeek : pageData.current_week;
        }
    }

    async function fetchAndRenderStats() {
        const selectedWeek = weekSelect.value;
        const yourTeamName = yourTeamSelect.value;

        if (!selectedWeek || !yourTeamName) {
            statsContainer.innerHTML = '<p class="text-gray-400">Please select a week and team.</p>';
            return;
        }

        statsContainer.innerHTML = '<p class="text-gray-400">Loading current goalie stats...</p>';

        try {
            const response = await fetch('/api/goalie_planning_stats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    week: selectedWeek,
                    team_name: yourTeamName,
                })
            });

            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Failed to fetch stats.');

            renderStatsTable(data, yourTeamName);

        } catch (error) {
            console.error('Error fetching stats:', error);
            statsContainer.innerHTML = `<p class="text-red-400">Error: ${error.message}</p>`;
        }
    }

    function renderStatsTable(data, teamName) {
        const { live_stats, goalie_starts } = data;

        // --- Calculate GAA and SV% on the client side, as requested ---
        const sv = live_stats['SV'] || 0;
        const sa = live_stats['SA'] || 0;
        const ga = live_stats['GA'] || 0;
        const toi = live_stats['TOI/G'] || 0;

        // Use 0 for display if denominator is 0 (vs. Infinity for comparison)
        const sv_pct = sa > 0 ? (sv / sa) : 0;
        const gaa = toi > 0 ? ((ga * 60) / toi) : 0;

        const w = live_stats['W'] || 0;
        const sho = live_stats['SHO'] || 0;

        // --- Build Stats Table ---
        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <h3 class="text-lg font-bold text-white p-3 bg-gray-800 rounded-t-lg">
                    Current Live Goalie Stats (${teamName})
                </h3>
                <table class="w-full divide-y divide-gray-700">
                    <thead class="bg-gray-700/50">
                        <tr>
                            <th class="px-3 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Stat</th>
                            <th class="px-3 py-2 text-right text-xs font-bold text-gray-300 uppercase tracking-wider">Value</th>
                        </tr>
                    </thead>
                    <tbody class="bg-gray-800 divide-y divide-gray-700">
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Goalie Starts</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right font-bold">${goalie_starts}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Wins (W)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right">${w.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Goals Against Avg (GAA)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right">${gaa.toFixed(3)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Save Pct (SV%)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right">${sv_pct.toFixed(3)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Shutouts (SHO)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right">${sho.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Saves (SV)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${sv.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Shots Against (SA)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${sa.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Goals Against (GA)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${ga.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Time on Ice (TOI)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${toi.toFixed(1)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
        statsContainer.innerHTML = tableHtml;
    }

    function setupEventListeners() {
        weekSelect.addEventListener('change', () => {
            localStorage.setItem('selectedWeek', weekSelect.value);
            fetchAndRenderStats();
        });
        yourTeamSelect.addEventListener('change', () => {
            localStorage.setItem('selectedTeam', yourTeamSelect.value);
            fetchAndRenderStats();
        });
    }

    init();
})();
