(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const aggregateStatsContainer = document.getElementById('stats-container');
    const individualStartsContainer = document.getElementById('individual-starts-container'); // NEW

    // Get references to the dropdowns *in home.html*
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');

    async function init() {
        try {
            if (!weekSelect || !yourTeamSelect) {
                 throw new Error("Could not find main dropdowns (week-select or your-team-select).");
            }
            // Initial data load
            await fetchAndRenderStats();
        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.textContent = error.message;
            errorDiv.classList.remove('hidden');
            aggregateStatsContainer.classList.add('hidden');
            individualStartsContainer.classList.add('hidden'); // NEW
        }
    }

    async function fetchAndRenderStats() {
        // Read values directly from the home.html dropdowns
        const selectedWeek = weekSelect.value;
        const yourTeamName = yourTeamSelect.value;

        if (!selectedWeek || !yourTeamName) {
            aggregateStatsContainer.innerHTML = '<p class="text-gray-400">Please select a week and team.</p>';
            individualStartsContainer.innerHTML = ''; // NEW
            return;
        }

        aggregateStatsContainer.innerHTML = '<p class="text-gray-400">Loading current goalie stats...</p>';
        individualStartsContainer.innerHTML = ''; // NEW

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

            // Call render functions for each table
            renderAggregateStatsTable(data, yourTeamName);
            renderIndividualStartsTable(data.individual_starts); // MODIFIED: Pass all data

        } catch (error) {
            console.error('Error fetching stats:', error);
            aggregateStatsContainer.innerHTML = `<p class="text-red-400">Error: ${error.message}</p>`;
            individualStartsContainer.innerHTML = ''; // NEW
        }
    }

    // Renamed from renderStatsTable
    function renderAggregateStatsTable(data, teamName) {
        const { live_stats, goalie_starts } = data;

        const sv = live_stats['SV'] || 0;
        const sa = live_stats['SA'] || 0;
        const ga = live_stats['GA'] || 0;
        const toi = live_stats['TOI/G'] || 0;

        const sv_pct = sa > 0 ? (sv / sa) : 0;
        const gaa = toi > 0 ? ((ga * 60) / toi) : 0;

        const w = live_stats['W'] || 0;
        const sho = live_stats['SHO'] || 0;

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
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Goals Against (GA)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${ga.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Time on Ice (TOI)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${toi.toFixed(1)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Save Pct (SV%)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right">${sv_pct.toFixed(3)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Saves (SV)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${sv.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/5A0">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-normal text-gray-400 pl-6">Shots Against (SA)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-400 text-right">${sa.toFixed(0)}</td>
                        </tr>
                        <tr class="hover:bg-gray-700/50">
                            <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">Shutouts (SHO)</td>
                            <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300 text-right">${sho.toFixed(0)}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        `;
        aggregateStatsContainer.innerHTML = tableHtml;
    }

    // --- MODIFIED FUNCTION ---
    function renderIndividualStartsTable(starts) {
        if (!starts) { // Handle case where starts might be undefined
            individualStartsContainer.innerHTML = '';
            return;
        }

        // Define headers
        const headers = ['Start #', 'Date', 'Player', 'W', 'GA', 'SV', 'SA', 'SV%', 'GAA', 'SHO'];

        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <h3 class="text-lg font-bold text-white p-3 bg-gray-800 rounded-t-lg">
                    Individual Goalie Starts
                </h3>
                <div class="overflow-x-auto">
                    <table class="w-full divide-y divide-gray-700">
                        <thead class="bg-gray-700/50">
                            <tr>
                                ${headers.map(h => `<th class="px-3 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">${h}</th>`).join('')}
                            </tr>
                        </thead>
                        <tbody class="bg-gray-800 divide-y divide-gray-700">
        `;

        // --- NEW: Calculate Totals ---
        let totalW = 0, totalGA = 0, totalSV = 0, totalSA = 0, totalSHO = 0, totalTOI = 0;

        // Create a row for each start
        starts.forEach((start, index) => {
            // Accumulate totals
            totalW += (start.W || 0);
            totalGA += (start.GA || 0);
            totalSV += (start.SV || 0);
            totalSA += (start.SA || 0);
            totalSHO += (start.SHO || 0);
            totalTOI += (start['TOI/G'] || 0); // Already includes SHO fix from backend

            tableHtml += `<tr class="hover:bg-gray-700/50">
                <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">${index + 1}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${start.date}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm font-medium text-gray-300">${start.player_name}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start.W || 0).toFixed(0)}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start.GA || 0).toFixed(0)}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start.SV || 0).toFixed(0)}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start.SA || 0).toFixed(0)}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start['SV%'] || 0).toFixed(3)}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start.GAA || 0).toFixed(3)}</td>
                <td class="px-3 py-2 whitespace-nowrap text-sm text-gray-300">${(start.SHO || 0).toFixed(0)}</td>
            </tr>`;
        });

        // --- NEW: Calculate Final Averages ---
        const totalGAA = totalTOI > 0 ? (totalGA * 60) / totalTOI : 0;
        const totalSVpct = totalSA > 0 ? totalSV / totalSA : 0;

        // --- NEW: Add the Total Row ---
        // Only show total row if there are starts
        if (starts.length > 0) {
            tableHtml += `
                <tr class="bg-gray-700/50 border-t-2 border-gray-500">
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${starts.length}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white"></td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">TOTALS</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalW.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalGA.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalSV.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalSA.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalSVpct.toFixed(3)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalGAA.toFixed(3)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-bold text-white">${totalSHO.toFixed(0)}</td>
                </tr>
            `;
        }

        tableHtml += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
        individualStartsContainer.innerHTML = tableHtml;
    }

    init();
})();
