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
                                <th class="table-header">Player</th>`;

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
                        <td class="table-cell">${row['Date']}</td>
                        <td class="table-cell">${row['Player']}</td>`;
            for (const header of headersWithData) {
                html += `<td class="table-cell">${row[header] || 0}</td>`;
            }
            html += `</tr>`;
        }

        html += `       </tbody>
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

            // Render the two tables
            const skaterTable = createTable('Skaters', data.skater_headers, data.skater_data);
            const goalieTable = createTable('Goalies', data.goalie_headers, data.goalie_data);

            historyContent.innerHTML = `<div class="space-y-6">${skaterTable}${goalieTable}</div>`;

        } catch (error) {
            console.error('Error fetching bench points:', error);
            showError(error.message);
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    }

    // --- MODIFIED: This function is now a router ---
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
