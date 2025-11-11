(async function() {
    // Wait for the DOM to be fully loaded before running
    await new Promise(resolve => {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", resolve);
        } else {
            resolve();
        }
    });

    // --- Element IDs (unchanged) ---
    const errorDiv = document.getElementById('schedule-error-message');
    const weekSelect = document.getElementById('schedule-week-select');
    const reportSelect = document.getElementById('schedule-report-select');
    const scheduleContent = document.getElementById('schedule-content');
    const loadingSpinner = document.getElementById('loading-spinner-schedules');

    let pageData = null;

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
        scheduleContent.innerHTML = '';
        loadingSpinner.classList.add('hidden');
    }

    async function fetchPageData() {
        try {
            const response = await fetch('/api/schedules_page_data');
            if (!response.ok) {
                throw new Error(`Failed to load page data. Server responded with ${response.status}`);
            }
            const data = await response.json();
            if (!data.db_exists) {
                showError(data.error || "Database not found. Please create one on the 'League Database' page.");
                return false;
            }
            pageData = data;
            return true;
        } catch (error) {
            console.error('Error fetching page data:', error);
            showError(`Error fetching page data: ${error.message}`);
            return false;
        }
    }

    function populateDropdowns() {
        // --- Week Dropdown (unchanged) ---
        const allWeeks = pageData.weeks;
        let weekOptions = '<option value="all">All Season</option>';
        weekOptions += allWeeks.map(week =>
            `<option value="${week.week_num}">
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');
        weekSelect.innerHTML = weekOptions;
        weekSelect.value = "all";

        // --- Report Dropdown ---
        // --- MODIFIED: Added "Off Days" ---
        let reportOptions = '';
        reportOptions += '<option value="please_select">--Please Select--</option>';
        reportOptions += '<option value="off_days">Off Days</option>'; // NEW
        reportOptions += '<option value="tbd">TBD</option>';
        reportSelect.innerHTML = reportOptions;
        // --- END MODIFIED ---
    }

    function setupEventListeners() {
        weekSelect.addEventListener('change', fetchAndRenderReport);
        reportSelect.addEventListener('change', fetchAndRenderReport);
        // --- NEW: Add sort listener ---
        scheduleContent.addEventListener('click', handleTableSort);
    }

    // --- [START] NEW: Table Sorting Logic (from season-history.js) ---
    function handleTableSort(event) {
        const header = event.target.closest('.sortable-header');
        if (!header) return;

        const table = header.closest('table');
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));
        const sortKey = header.dataset.sortKey;

        let currentDir = header.dataset.sortDir || 'none';
        let nextDir = (currentDir === 'asc') ? 'desc' : 'asc';

        table.querySelectorAll('.sortable-header').forEach(th => {
            th.dataset.sortDir = 'none';
            const arrow = th.querySelector('.sort-arrow');
            if (arrow) arrow.remove();
        });

        header.dataset.sortDir = nextDir;
        const arrowSpan = document.createElement('span');
        arrowSpan.className = 'sort-arrow ml-1';
        arrowSpan.textContent = (nextDir === 'asc') ? '▲' : '▼';
        header.appendChild(arrowSpan);

        const headers = Array.from(header.parentElement.children);
        const colIndex = headers.indexOf(header);

        rows.sort((rowA, rowB) => {
            const cellA = rowA.children[colIndex];
            const cellB = rowB.children[colIndex];
            let valA, valB;

            if (sortKey === 'team') {
                valA = cellA.textContent.toLowerCase();
                valB = cellB.textContent.toLowerCase();
            } else {
                valA = parseFloat(cellA.textContent) || 0;
                valB = parseFloat(cellB.textContent) || 0;
            }

            let sortVal = 0;
            if (typeof valA === 'string') {
                sortVal = valA.localeCompare(valB);
            } else {
                sortVal = valA - valB;
            }

            if (nextDir === 'desc') {
                sortVal *= -1;
            }
            return sortVal;
        });

        rows.forEach(row => tbody.appendChild(row));
    }
    // --- [END] NEW: Table Sorting Logic ---


    // --- [START] NEW: Table Creation Helpers ---

    /**
     * Creates the HTML table for the single week "Off Days" report.
     */
    function createSingleWeekOffDaysTable(rows) {
        let html = `<div class="bg-gray-800 rounded-lg shadow-lg p-4">
                        <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-700">
                                <thead>
                                    <tr>
                                        <th class="table-header !text-left sortable-header cursor-pointer" data-sort-key="team">Team</th>
                                        <th class="table-header sortable-header cursor-pointer" data-sort-key="off_days">Off Days This Week</th>
                                        <th class="table-header sortable-header cursor-pointer" data-sort-key="total_games">Total Games</th>
                                    </tr>
                                </thead>
                                <tbody class="bg-gray-900 divide-y divide-gray-700">`;

        for (const row of rows) {
            html += `<tr>
                        <td class="table-cell !text-left">${row.team}</td>
                        <td class="table-cell text-center">${row.off_days}</td>
                        <td class="table-cell text-center">${row.total_games}</td>
                    </tr>`;
        }

        html += `           </tbody>
                        </table>
                    </div>
                </div>`;
        return html;
    }

    /**
     * Creates the HTML table for the "All Season" (Past or ROS) "Off Days" report.
     */
    function createMultiWeekOffDaysTable(title, data) {
        const { headers, rows } = data;

        let html = `<div class="bg-gray-800 rounded-lg shadow-lg p-4">
                        <h3 class="text-lg font-semibold text-white mb-3">${title}</h3>
                        <div class="overflow-x-auto">
                            <table class="min-w-full divide-y divide-gray-700">
                                <thead>
                                    <tr>
                                        <th class="table-header !text-left sortable-header cursor-pointer" data-sort-key="team">Team</th>`;

        for (const header of headers) {
            // Use week number (e.g., "Week 6") as the sort key
            html += `<th class="table-header sortable-header cursor-pointer" data-sort-key="${header}">${header}</th>`;
        }

        html += `           </tr>
                        </thead>
                        <tbody class="bg-gray-900 divide-y divide-gray-700">`;

        for (const row of rows) {
            html += `<tr>
                        <td class="table-cell !text-left">${row.team}</td>`;
            for (const header of headers) {
                html += `<td class="table-cell text-center">${row[header] || 0}</td>`;
            }
            html += `</tr>`;
        }

        html += `           </tbody>
                        </table>
                    </div>
                </div>`;
        return html;
    }

    // --- [END] NEW: Table Creation Helpers ---


    // --- [START] NEW: Off Days Fetch Function ---
    /**
     * Fetches data for the "Off Days" report from the backend.
     */
    async function fetchOffDaysReport(week) {
        loadingSpinner.classList.remove('hidden');
        scheduleContent.innerHTML = '';
        errorDiv.classList.add('hidden');

        try {
            const response = await fetch('/api/schedules/off_days', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ week: week })
            });

            if (!response.ok) throw new Error(`Server error: ${response.status}`);
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            if (data.report_type === 'single_week') {
                scheduleContent.innerHTML = createSingleWeekOffDaysTable(data.table_data);
            } else if (data.report_type === 'all_season') {
                const rosTable = createMultiWeekOffDaysTable("Off Days For ROS", data.ros_data);
                const pastTable = createMultiWeekOffDaysTable("Off Days From Past Weeks", data.past_data);
                scheduleContent.innerHTML = `
                    <div class="space-y-6">
                        ${rosTable}
                        ${pastTable}
                    </div>
                `;
            }

        } catch (error) {
            console.error('Error fetching off days report:', error);
            showError(error.message);
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    }
    // --- [END] NEW: Off Days Fetch Function ---


    async function fetchAndRenderReport() {
        const selectedWeek = weekSelect.value;
        const selectedReport = reportSelect.value;

        console.log(`Fetching data for: Week ${selectedWeek}, Report ${selectedReport}`);

        loadingSpinner.classList.remove('hidden');

        // --- MODIFIED: Added "off_days" case ---
        switch (selectedReport) {
            case 'off_days': // NEW
                await fetchOffDaysReport(selectedWeek);
                break;

            case 'tbd':
                scheduleContent.innerHTML = `<p class="text-gray-400">The "TBD" report is not yet implemented.</p>`;
                loadingSpinner.classList.add('hidden');
                break;

            case 'please_select':
            default:
                scheduleContent.innerHTML = `<p class="text-gray-400">Please select a report to view.</p>`;
                loadingSpinner.classList.add('hidden');
                break;
        }
        // --- END MODIFIED ---
    }

    async function init() {
        loadingSpinner.classList.remove('hidden');
        const success = await fetchPageData();
        if (success) {
            populateDropdowns();
            setupEventListeners();
            await fetchAndRenderReport();
        }
    }

    init();

})();
