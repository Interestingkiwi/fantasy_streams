(async function() {
    // A short delay to ensure the page elements are in the DOM
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const aggregateStatsContainer = document.getElementById('stats-container');
    const individualStartsContainer = document.getElementById('individual-starts-container');

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
            individualStartsContainer.classList.add('hidden');
        }
    }

    async function fetchAndRenderStats() {
        // Read values directly from the home.html dropdowns
        const selectedWeek = weekSelect.value;
        const yourTeamName = yourTeamSelect.value;

        if (!selectedWeek || !yourTeamName) {
            aggregateStatsContainer.innerHTML = '<p class="text-gray-400">Please select a week and team.</p>';
            individualStartsContainer.innerHTML = '';
            return;
        }

        aggregateStatsContainer.innerHTML = '<p class="text-gray-400">Loading current goalie stats...</p>';
        individualStartsContainer.innerHTML = '';

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
            renderIndividualStartsTable(data.individual_starts); // Pass the individual starts array

        } catch (error) {
            console.error('Error fetching stats:', error);
            aggregateStatsContainer.innerHTML = `<p class="text-red-400">Error: ${error.message}</p>`;
            individualStartsContainer.innerHTML = '';
        }
    }

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
                        <tr class="hover:bg-gray-700/50">
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

    function renderIndividualStartsTable(starts) {
        if (!starts) {
            individualStartsContainer.innerHTML = '';
            return;
        }

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

        // --- Calculate Totals ---
        let totalW = 0, totalGA = 0, totalSV = 0, totalSA = 0, totalSHO = 0, totalTOI = 0;

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

        // --- Calculate Final Averages ---
        const totalGAA = totalTOI > 0 ? (totalGA * 60) / totalTOI : 0;
        const totalSVpct = totalSA > 0 ? totalSV / totalSA : 0;

        // --- Add the Total Row ---
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

        // --- [START] NEW SCENARIO LOGIC ---

        const nextStartNum = starts.length + 1;

        // Define scenario deltas (W is assumed 0 unless it's a shutout, can be changed)
        const scenarios = [
            // Assuming a W for a Shutout, L for 4/GA/Pulled, otherwise 0
            { name: "Shutout",       w: 1, l: 0, ga: 0, sv: 30, sa: 30, toi: 60, sho: 1 },
            { name: "1GA",           w: 0, l: 0, ga: 1, sv: 29, sa: 30, toi: 60, sho: 0 },
            { name: "2GA",           w: 0, l: 0, ga: 2, sv: 28, sa: 30, toi: 60, sho: 0 },
            { name: "3GA",           w: 0, l: 0, ga: 3, sv: 27, sa: 30, toi: 60, sho: 0 },
            { name: "4GA",           w: 0, l: 0, ga: 4, sv: 26, sa: 30, toi: 60, sho: 0 },
            { name: "5GA",           w: 0, l: 0, ga: 5, sv: 25, sa: 30, toi: 60, sho: 0 },
            { name: "6GA",           w: 0, l: 0, ga: 6, sv: 24, sa: 30, toi: 60, sho: 0 },
            { name: "4/GA/Pulled",   w: 0, l: 1, ga: 4, sv: 11, sa: 15, toi: 20, sho: 0 }
        ];

        // Loop and render each scenario
        scenarios.forEach(scenario => {
            // Calculate new cumulative stats by adding scenario delta to totals
            const newW = totalW + scenario.w;
            const newGA = totalGA + scenario.ga;
            const newSV = totalSV + scenario.sv;
            const newSA = totalSA + scenario.sa;
            const newSHO = totalSHO + scenario.sho;
            const newTOI = totalTOI + scenario.toi;

            // Calculate new cumulative averages
            const newGAA = newTOI > 0 ? (newGA * 60) / newTOI : 0;
            const newSVpct = newSA > 0 ? newSV / newSA : 0;

            tableHtml += `
                <tr class="hover:bg-gray-700/50 text-gray-400 italic">
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${nextStartNum}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">
                        <input type="checkbox" class="form-checkbox bg-gray-800 border-gray-600 rounded" disabled />
                        Use
                    </td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm font-medium">${scenario.name}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newW.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newGA.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newSV.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newSA.toFixed(0)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newSVpct.toFixed(3)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newGAA.toFixed(3)}</td>
                    <td class="px-3 py-2 whitespace-nowrap text-sm">${newSHO.toFixed(0)}</td>
                </tr>
            `;
        });
        // --- [END] NEW SCENARIO LOGIC ---

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
