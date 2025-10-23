(async function() {
    await new Promise(resolve => setTimeout(resolve, 0)); // Ensure DOM is ready

    const errorDiv = document.getElementById('db-error-message');
    const waiverContainer = document.getElementById('waiver-players-container');
    const freeAgentContainer = document.getElementById('free-agent-players-container');
    const playerSearchInput = document.getElementById('player-search');
    const checkboxesContainer = document.getElementById('category-checkboxes-container');
    const recalculateButton = document.getElementById('recalculate-button');

    // --- Global State ---
    let allWaiverPlayers = [];
    let allFreeAgents = [];
    let allScoringCategories = []; // Full list for creating checkboxes
    let rankedCategories = []; // List used for the current ranking
    let sortConfig = {
        waivers: { key: 'total_cat_rank', direction: 'ascending' },
        freeAgents: { key: 'total_cat_rank', direction: 'ascending' }
    };

    async function fetchData(selectedCategories = null) {
        waiverContainer.innerHTML = '<p class="text-gray-400">Loading waiver players...</p>';
        freeAgentContainer.innerHTML = '<p class="text-gray-400">Loading free agents...</p>';

        try {
            const body = selectedCategories ? JSON.stringify({ categories: selectedCategories }) : null;
            const response = await fetch('/api/free_agent_data', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: body
            });
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch free agent data.');
            }

            allWaiverPlayers = data.waiver_players;
            allFreeAgents = data.free_agents;
            rankedCategories = data.ranked_categories;

            // Only populate all categories on the initial load
            if (allScoringCategories.length === 0) {
                allScoringCategories = data.scoring_categories;
                renderCategoryCheckboxes();
            }

            filterAndSortPlayers();

        } catch (error) {
            console.error('Fetch error:', error);
            errorDiv.textContent = `Error: ${error.message}`;
            errorDiv.classList.remove('hidden');
            waiverContainer.innerHTML = '';
            freeAgentContainer.innerHTML = '';
        }
    }

    function renderCategoryCheckboxes() {
        let checkboxHtml = '<label class="block text-sm font-medium text-gray-300 mb-2">Recalculate Rank Based On:</label><div class="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">';
        allScoringCategories.forEach(cat => {
            const isChecked = rankedCategories.includes(cat);
            checkboxHtml += `
                <div class="flex items-center">
                    <input id="cat-${cat}" name="category" type="checkbox" value="${cat}" ${isChecked ? 'checked' : ''} class="h-4 w-4 bg-gray-700 border-gray-600 text-indigo-600 focus:ring-indigo-500 rounded">
                    <label for="cat-${cat}" class="ml-2 block text-sm text-gray-300">${cat}</label>
                </div>
            `;
        });
        checkboxHtml += '</div>';
        checkboxesContainer.innerHTML = checkboxHtml;
    }

    function filterAndSortPlayers() {
        const searchTerm = playerSearchInput.value.toLowerCase();

        // --- Process Waivers ---
        let filteredWaivers = searchTerm
            ? allWaiverPlayers.filter(p => p.player_name.toLowerCase().includes(searchTerm))
            : [...allWaiverPlayers];

        sortPlayers(filteredWaivers, sortConfig.waivers);
        renderPlayerTable('Waiver Players', filteredWaivers, waiverContainer, 'waivers');

        // --- Process Free Agents ---
        let filteredFreeAgents = searchTerm
            ? allFreeAgents.filter(p => p.player_name.toLowerCase().includes(searchTerm))
            : [...allFreeAgents];

        sortPlayers(filteredFreeAgents, sortConfig.freeAgents);
        renderPlayerTable('Free Agents', filteredFreeAgents, freeAgentContainer, 'freeAgents', true);
    }

    function sortPlayers(players, config) {
        players.sort((a, b) => {
            let valA = a[config.key] === 0 ? Infinity : a[config.key];
            let valB = b[config.key] === 0 ? Infinity : b[config.key];

            if (config.key === 'player_name') {
                valA = String(a.player_name).toLowerCase();
                valB = String(b.player_name).toLowerCase();
            }

            if (valA < valB) {
                return config.direction === 'ascending' ? -1 : 1;
            }
            if (valA > valB) {
                return config.direction === 'ascending' ? 1 : -1;
            }
            return 0;
        });
    }

    function renderPlayerTable(title, players, container, tableType, shouldCap = false) {
        if (!players) {
            container.innerHTML = `<h2 class="text-2xl font-bold text-white mb-3">${title}</h2><p class="text-gray-400">No players found.</p>`;
            return;
        }

        const playersToDisplay = shouldCap ? players.slice(0, 100) : players;

        let tableHtml = `
            <div class="bg-gray-900 rounded-lg shadow">
                <h2 class="text-2xl font-bold text-white p-4 bg-gray-800 rounded-t-lg">${title}</h2>
                <table class="min-w-full divide-y divide-gray-700">
                    <thead class="bg-gray-700/50">
                        <tr>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider sortable" data-sort-key="player_name" data-table-type="${tableType}">Player Name</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Team</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Positions</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">This Week</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider">Next Week</th>
                            <th class="px-2 py-2 text-left text-xs font-bold text-gray-300 uppercase tracking-wider sortable" data-sort-key="total_cat_rank" data-table-type="${tableType}">Total Cat Rank</th>
        `;

        rankedCategories.forEach(cat => {
            tableHtml += `<th class="px-2 py-2 text-center text-xs font-bold text-gray-300 uppercase tracking-wider sortable" data-sort-key="${cat}_cat_rank" data-table-type="${tableType}">${cat}</th>`;
        });

        tableHtml += `
                        </tr>
                        <tr><td colspan="${6 + rankedCategories.length}" class="text-center text-xs text-gray-500 py-1">Click headers to sort</td></tr>
                    </thead>
                    <tbody class="bg-gray-800 divide-y divide-gray-700">
        `;

        if (playersToDisplay.length === 0) {
            tableHtml += `<tr><td colspan="${6 + rankedCategories.length}" class="text-center py-4">No players match the current filter.</td></tr>`;
        } else {
            playersToDisplay.forEach(player => {
                tableHtml += `
                    <tr class="hover:bg-gray-700/50">
                        <td class="px-2 py-2 whitespace-nowrap text-sm font-medium text-gray-300">${player.player_name}</td>
                        <td class="px-2 py-2 whitespace-nowrap text-sm text-gray-300">${player.player_team}</td>
                        <td class="px-2 py-2 whitespace-nowrap text-sm text-gray-300">${player.positions}</td>
                        <td class="px-2 py-2 whitespace-nowrap text-sm text-gray-300">${(player.games_this_week || []).join(', ')}</td>
                        <td class="px-2 py-2 whitespace-nowrap text-sm text-gray-300">${(player.games_next_week || []).join(', ')}</td>
                        <td class="px-2 py-2 whitespace-nowrap text-sm font-bold text-yellow-300">${player.total_cat_rank}</td>
                `;
                rankedCategories.forEach(cat => {
                    const rankKey = `${cat}_cat_rank`;
                    const rank = (player[rankKey] !== null && player[rankKey] !== undefined) ? player[rankKey].toFixed(2) : '-';
                    tableHtml += `<td class="px-2 py-2 whitespace-nowrap text-sm text-center text-gray-300">${rank}</td>`;
                });
                tableHtml += `</tr>`;
            });
        }

        tableHtml += `
                    </tbody>
                </table>
            </div>
        `;
        container.innerHTML = tableHtml;

        document.querySelectorAll(`[data-table-type="${tableType}"].sortable`).forEach(header => {
            header.classList.remove('sort-asc', 'sort-desc');
            if (header.dataset.sortKey === sortConfig[tableType].key) {
                header.classList.add(sortConfig[tableType].direction === 'ascending' ? 'sort-asc' : 'sort-desc');
            }
            header.removeEventListener('click', handleSortClick);
            header.addEventListener('click', handleSortClick);
        });
    }

    function handleSortClick(e) {
        const key = e.target.dataset.sortKey;
        const tableType = e.target.dataset.tableType;

        if (sortConfig[tableType].key === key) {
            sortConfig[tableType].direction = sortConfig[tableType].direction === 'ascending' ? 'descending' : 'ascending';
        } else {
            sortConfig[tableType].key = key;
            sortConfig[tableType].direction = 'ascending';
        }
        filterAndSortPlayers();
    }

    function handleRecalculateClick() {
        const selectedCategories = Array.from(document.querySelectorAll('#category-checkboxes-container input:checked')).map(cb => cb.value);
        fetchData(selectedCategories);
    }

    function setupEventListeners() {
        playerSearchInput.addEventListener('input', filterAndSortPlayers);
        recalculateButton.addEventListener('click', handleRecalculateClick);
    }

    fetchData(); // Initial data load
})();
