(async function() {
    // Wait for the DOM to be fully loaded before running
    await new Promise(resolve => {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", resolve);
        } else {
            resolve();
        }
    });

    const errorDiv = document.getElementById('db-error-message');
    const weekSelect = document.getElementById('history-week-select');
    const yourTeamSelect = document.getElementById('your-team-select');
    const reportSelect = document.getElementById('history-report-select');
    const historyContent = document.getElementById('history-content');
    const loadingSpinner = document.getElementById('loading-spinner');

    let pageData = null;

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
        historyContent.innerHTML = ''; // Clear content on error
        loadingSpinner.classList.add('hidden');
    }

    async function fetchPageData() {
        try {
            const response = await fetch('/api/season_history_page_data');
            if (!response.ok) {
                throw new Error(`Failed to load page data. Server responded with ${response.status}`);
            }
            const data = await response.json();
            if (!data.db_exists) {
                showError(data.error || "Database not found. Please create one on the 'League Database' page.");
                return false;
            }
            pageData = data; // Store data globally for this module
            return true;
        } catch (error) {
            console.error('Error fetching page data:', error);
            showError(`Error fetching page data: ${error.message}`);
            return false;
        }
    }

    function populateDropdowns() {
        // --- Team Dropdown --- (Handled by home.js)

        // --- Week Dropdown ---
        const completedWeeks = pageData.weeks.filter(week => week.week_num < pageData.current_week);
        let weekOptions = '<option value="all">All Season</option>';
        weekOptions += completedWeeks.map(week =>
            `<option value="${week.week_num}">
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');
        weekSelect.innerHTML = weekOptions;
        weekSelect.value = "all"; // Default to "All Season"

        // --- Report Dropdown ---
        let reportOptions = '';
        reportOptions += '<option value="please_select">--Please Select--</option>'; // Your default
        reportOptions += '<option value="bench_points">Bench Points</option>';
        reportOptions += '<option value="tbd">TBD</option>';

        reportSelect.innerHTML = reportOptions;
    }

    function setupEventListeners() {
        weekSelect.addEventListener('change', fetchAndRenderTable);
        yourTeamSelect.addEventListener('change', fetchAndRenderTable);
        reportSelect.addEventListener('change', fetchAndRenderTable);
    }

    // --- NEW: Helper function to create a table ---
    function createTable(title, headers, rows) {
        let html = `<div class="bg-gray-800 rounded-lg shadow-lg p-4">
                        <h3 class="text-lg font-semibold text-white mb-3">${title}</h3>`;

        if (rows.length === 0) {
            html += '<p class="text-gray-400">No data found for this period.</p></div>';
            return html;
        }

        html += `<div class="overflow-x-auto">
                    <table class="min-w-full divide-y divide-gray-700">
                        <thead>
                            <tr>
                                <th class="table-header">Date</th>
                                <th class="table-header">Player</th>
                                <th class="table-header">Positions</th>
                                `;

        // Filter headers to only include those with data
        const headersWithData = headers.filter(header =>
            rows.some(row => row[header] && row[header] != 0)
        );

        for (const header of headersWithData) {
            html += `<th class="table-header">${header}</th>`;
        }

        html += `           </tr>
                        </thead>
                        <tbody class="bg-gray-900 divide-y divide-gray-700">`;

        for (const row of rows) {
            html += `<tr>
                        <td class="table-cell text-center">${row['Date']}</td>
                        <td class="table-cell text-center">${row['Player']}</td>
                        <td class="table-cell text-center">${row['Positions'] || ''}</td>
                        `;
            for (const header of headersWithData) {
                html += `<td class="table-cell text-center">${row[header] || 0}</td>`;
            }
            html += `</tr>`;
        }

        html += `       </tbody>
                    </table>
                </div>
            </div>`;
        return html;
    }


    function createMatchupStatsTable(matchup_data) {
            const { your_team_stats, opponent_team_stats, opponent_name, scoring_categories } = matchup_data;

            // --- START NEW LOGIC ---
            // 1. Define goalie sub-category relationships
            const goalieCats = {
                'SVpct': ['SV', 'SA'],
                'GAA': ['GA', 'TOI/G']
            };
            const scoringCategoriesSet = new Set(scoring_categories);

            // 2. Create a set of categories to skip in the main loop
            const catsToSkip = new Set();
            if (scoringCategoriesSet.has('SVpct')) {
                goalieCats['SVpct'].forEach(cat => catsToSkip.add(cat));
            }
            if (scoringCategoriesSet.has('GAA')) {
                goalieCats['GAA'].forEach(cat => catsToSkip.add(cat));
            }
            // --- END NEW LOGIC ---

            let html = `<div class="bg-gray-800 rounded-lg shadow-lg p-4">
                            <h3 class="text-lg font-semibold text-white mb-3">Matchup Result</h3>
                            <h4 class="text-sm text-gray-400 mb-3 -mt-2">vs. ${opponent_name}</h4>
                            <div class="overflow-x-auto">
                                <table class="min-w-full">
                                    <thead>
                                        <tr>
                                            <th class="table-header !text-left">Category</th>
                                            <th class="table-header">You</th>
                                            <th class="table-header">Opp</th>
                                        </tr>
                                    </thead>
                                    <tbody class="bg-gray-900 divide-y divide-gray-700">`;

            for (const category of scoring_categories) {

                // --- START MODIFIED LOGIC ---
                // 3. Skip rendering this category if it's a sub-category of one that exists
                if (catsToSkip.has(category)) {
                    continue;
                }
                // --- END MODIFIED LOGIC ---

                const your_val = your_team_stats[category] || 0;
                const opp_val = opponent_team_stats[category] || 0;

                // Add styling for wins/losses
                let your_class = 'text-gray-400';
                let opp_class = 'text-gray-400';

                // Handle reverse-scoring categories (GAA, GA)
                if (['GAA', 'GA'].includes(category)) {
                    if (your_val < opp_val) {
                        your_class = 'text-green-400 font-bold';
                    } else if (opp_val < your_val) {
                        opp_class = 'text-green-400 font-bold';
                    }
                } else { // Handle normal scoring
                    if (your_val > opp_val) {
                        your_class = 'text-green-400 font-bold';
                    } else if (opp_val > your_val) {
                        opp_class = 'text-green-400 font-bold';
                    }
                }

                // 4. Render the main category row (with a style fix to make winning cats bold)
                html += `<tr>
                            <td class="table-cell !text-left ${your_class.includes('font-bold') ? 'font-semibold' : ''}">${category}</td>
                            <td class="table-cell text-center ${your_class}">${your_val}</td>
                            <td class="table-cell text-center ${opp_class}">${opp_val}</td>
                         </tr>`;

                // --- START NEW LOGIC ---
                // 5. Check for and render sub-categories
                if (goalieCats.hasOwnProperty(category)) {
                    for (const subCat of goalieCats[category]) {
                        // Get sub-cat values (no win/loss styling)
                        const your_sub_val = your_team_stats[subCat] || 0;
                        const opp_sub_val = opponent_team_stats[subCat] || 0;

                        html += `<tr class="hover:bg-gray-700/50">
                                    <td class="table-cell !text-left pl-8 text-sm text-gray-400">${subCat}</td>
                                    <td class="table-cell text-center text-sm text-gray-400">${your_sub_val}</td>
                                    <td class="table-cell text-center text-sm text-gray-400">${opp_sub_val}</td>
                                </tr>`;
                    }
                }
                // --- END NEW LOGIC ---
            }

            html += `           </tbody>
                            </table>
                        </div>
                    </div>`;
            return html;
        }

    // --- NEW: Function to fetch and render bench points ---
    async function fetchBenchPoints(teamName, week) {
        loadingSpinner.classList.remove('hidden');
        historyContent.innerHTML = '';
        errorDiv.classList.add('hidden'); // Hide old errors

        try {
            const response = await fetch('/api/history/bench_points', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ team_name: teamName, week: week })
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            if (data.error) {
                throw new Error(data.error);
            }

            // Render the two bench tables
            const skaterTable = createTable('Skaters', data.skater_headers, data.skater_data);
            const goalieTable = createTable('Goalies', data.goalie_headers, data.goalie_data);

            // --- START MODIFIED LAYOUT ---
            let matchupHtml = '';
            if (data.matchup_data) {
                // If matchup data exists, render the table
                matchupHtml = createMatchupStatsTable(data.matchup_data);
            } else {
                // Otherwise, show the "All Season" message
                matchupHtml = `<div class="bg-gray-800 rounded-lg shadow-lg p-4">
                                <h3 class="text-lg font-semibold text-white mb-3">Matchup Result</h3>
                                <p class="text-gray-400">Matchup outcome unavailable when "All Season" is selected.</p>
                               </div>`;
            }

            historyContent.innerHTML = `
                <div class="flex flex-col lg:flex-row gap-6">
                    <div class="flex-grow space-y-6">
                        ${skaterTable}
                        ${goalieTable}
                    </div>
                    <div class="w-full lg:w-1/3 xl:w-1/4 flex-shrink-0">
                        ${matchupHtml}
                    </div>
                </div>
            `;
            // --- END MODIFIED LAYOUT ---

        } catch (error) {
            console.error('Error fetching bench points:', error);
            showError(error.message);
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    }


    async function fetchAndRenderTable() {
            const selectedTeam = yourTeamSelect.value;
            const selectedWeek = weekSelect.value;
            const selectedReport = reportSelect.value;

            console.log(`Fetching data for: Team ${selectedTeam}, Week ${selectedWeek}, Report ${selectedReport}`);

            // Route based on the selected report
            switch (selectedReport) {
                case 'bench_points':
                    await fetchBenchPoints(selectedTeam, selectedWeek);
                    break;

                case 'tbd':
                    loadingSpinner.classList.remove('hidden');
                    historyContent.innerHTML = `<p class="text-gray-400">The "TBD" report is not yet implemented.</p>`;
                    loadingSpinner.classList.add('hidden');
                    break;

                case 'please_select':
                default:
                    loadingSpinner.classList.add('hidden');
                    historyContent.innerHTML = `<p class="text-gray-400">Please select a report to view.</p>`;
                    break;
            }
        }


    async function init() {
        loadingSpinner.classList.remove('hidden');
        const success = await fetchPageData();
        if (success) {
            populateDropdowns();
            setupEventListeners();
            await fetchAndRenderTable(); // Load initial data (will show "Please select")
        }
    }

    init();

})();
