(async function() {
    // Wait for the DOM to be fully loaded before running
    await new Promise(resolve => {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", resolve);
        } else {
            resolve();
        }
    });

    // --- MODIFIED: Using new element IDs ---
    const errorDiv = document.getElementById('schedule-error-message');
    const weekSelect = document.getElementById('schedule-week-select');
    const reportSelect = document.getElementById('schedule-report-select');
    const scheduleContent = document.getElementById('schedule-content');
    const loadingSpinner = document.getElementById('loading-spinner-schedules');
    // --- END MODIFIED ---

    let pageData = null;

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
        scheduleContent.innerHTML = ''; // Clear content on error
        loadingSpinner.classList.add('hidden');
    }

    async function fetchPageData() {
        try {
            // --- MODIFIED: New API endpoint ---
            const response = await fetch('/api/schedules_page_data');
            // --- END MODIFIED ---

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
        // --- Week Dropdown ---
        // --- MODIFIED: Use all weeks, not just completed ones ---
        const allWeeks = pageData.weeks; // No filter
        let weekOptions = '<option value="all">All Season</option>';
        weekOptions += allWeeks.map(week =>
            `<option value="${week.week_num}">
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');
        weekSelect.innerHTML = weekOptions;
        weekSelect.value = "all"; // Default to "All Season"
        // --- END MODIFIED ---

        // --- Report Dropdown ---
        // --- MODIFIED: Populate with requested schedule reports ---
        let reportOptions = '';
        reportOptions += '<option value="please_select">--Please Select--</option>';
        reportOptions += '<option value="tbd">TBD</option>'; // Placeholder as requested

        reportSelect.innerHTML = reportOptions;
        // --- END MODIFIED ---
    }

    function setupEventListeners() {
        weekSelect.addEventListener('change', fetchAndRenderReport);
        reportSelect.addEventListener('change', fetchAndRenderReport);
    }

    // --- MODIFIED: Renamed from fetchAndRenderTable ---
    async function fetchAndRenderReport() {
            const selectedWeek = weekSelect.value;
            const selectedReport = reportSelect.value;

            console.log(`Fetching data for: Week ${selectedWeek}, Report ${selectedReport}`);

            loadingSpinner.classList.remove('hidden');

            // Route based on the selected report
            switch (selectedReport) {
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
        }
    // --- END MODIFIED ---

    async function init() {
        loadingSpinner.classList.remove('hidden');
        const success = await fetchPageData();
        if (success) {
            populateDropdowns();
            setupEventListeners();
            await fetchAndRenderReport(); // Load initial data (will show "Please select")
        }
    }

    init();

})();
