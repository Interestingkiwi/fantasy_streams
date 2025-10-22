(async function() {
    await new Promise(resolve => setTimeout(resolve, 0)); // Ensure DOM is ready

    const errorDiv = document.getElementById('db-error-message');
    const waiverContainer = document.getElementById('waiver-players-container');
    const freeAgentContainer = document.getElementById('free-agent-players-container');

    async function init() {
        waiverContainer.innerHTML = '<p class="text-gray-400">Loading waiver players...</p>';
        freeAgentContainer.innerHTML = '<p class="text-gray-400">Loading free agents...</p>';

        try {
            const response = await fetch('/api/free_agent_data');
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch free agent data.');
            }

            renderPlayerTable('Waiver Players', data.waiver_players, data.scoring_categories, waiverContainer);
            renderPlayerTable('Free Agents', data.free_agents, data.scoring_categories, freeAgentContainer);

        } catch (error) {
            console.error('Initialization error:', error);
            errorDiv.textContent = `Error: ${error.message}`;
            errorDiv.classList.remove('hidden');
            waiverContainer.innerHTML = '';
            freeAgentContainer.innerHTML = '';
        }
    }

    function renderPlayerTable(title, players, scoringCategories, container) {
        if (!players || players.length === 0) {
            container.innerHTML = `<h2 class="text-2xl font-bold text-white mb-3">${title}</h2><p class="text-gray-400">No players found.</p>`;
            return;
        }

        // Sort players by total_cat_rank, lowest (best) first
        players.sort((a, b) => a.total_cat_rank - b.total_cat_rank);

        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <h2 class="text-2xl font-bold text-white p-4 bg-gray-800 rounded-t-lg">${title}</h2>
                <table class="min-w-full divide-y divide-gray-700">
                    <thead class="bg-gray-700/50">
                        <tr>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Player Name</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Team</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Positions</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Total Cat Rank</th>
        `;

        scoringCategories.forEach(cat => {
            tableHtml += `<th class="px-2 py-2 text-center text-xs font-bold text-gray-300 uppercase tracking-wider">${cat}</th>`;
        });

        tableHtml += `
                        </tr>
                    </thead>
                    <tbody class="bg-gray-800 divide-y divide-gray-700">
        `;

        players.forEach(player => {
            tableHtml += `
                <tr class="hover:bg-gray-700/50">
                    <td class="px-2 py-2 whitespace-nowrap text-sm font-medium text-gray-300">${player.player_name}</td>
                    <td class="px-2 py-2 whitespace-nowrap text-sm text-gray-300">${player.player_team}</td>
                    <td class="px-2 py-2 whitespace-nowrap text-sm text-gray-300">${player.positions}</td>
                    <td class="px-2 py-2 whitespace-nowrap text-sm font-bold text-yellow-300">${player.total_cat_rank}</td>
            `;
            scoringCategories.forEach(cat => {
                const rankKey = `${cat}_cat_rank`;
                const rank = (player[rankKey] !== null && player[rankKey] !== undefined) ? player[rankKey].toFixed(2) : '-';
                tableHtml += `<td class="px-2 py-2 whitespace-nowrap text-sm text-center text-gray-300">${rank}</td>`;
            });
            tableHtml += `</tr>`;
        });

        tableHtml += `
                    </tbody>
                </table>
            </div>
        `;
        container.innerHTML = tableHtml;
    }

    init();
})();
