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
    // CHANGED: ID selector for week
    const weekSelect = document.getElementById('history-week-select');
    // REVERTED: ID selector for team
    const yourTeamSelect = document.getElementById('your-team-select');
    const historyContent = document.getElementById('history-content');
    const loadingSpinner = document.getElementById('loading-spinner');

    let pageData = null;

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
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
        // --- Team Dropdown ---
        // REMOVED: All population logic for 'yourTeamSelect'.
        // 'home.js' will handle populating it.

        // --- Week Dropdown (New Logic) ---

        // Filter for completed weeks
        const completedWeeks = pageData.weeks.filter(week => week.week_num < pageData.current_week);

        // Start with "All Season"
        let weekOptions = '<option value="all">All Season</option>';

        // Add the completed weeks
        weekOptions += completedWeeks.map(week =>
            `<option value="${week.week_num}">
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');

        weekSelect.innerHTML = weekOptions;

        // Default to "All Season"
        weekSelect.value = "all";
    }

    function setupEventListeners() {
        // Add listener for this page's unique week dropdown
        weekSelect.addEventListener('change', fetchAndRenderTable);

        // Add listener for the global team dropdown
        yourTeamSelect.addEventListener('change', fetchAndRenderTable);
    }

    async function fetchAndRenderTable() {
        // We can safely read the value from the global team select
        const selectedTeam = yourTeamSelect.value;
        const selectedWeek = weekSelect.value;

        console.log(`Fetching data for: ${selectedTeam}, Week: ${selectedWeek}`);

        loadingSpinner.classList.remove('hidden');
        historyContent.innerHTML = ''; // Clear previous content

        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay

        historyContent.innerHTML = `<p class="text-gray-400">Data for ${selectedTeam} (Week ${selectedWeek}) will be displayed here.</p>`;
        loadingSpinner.classList.add('hidden');
    }

    async function init() {
        loadingSpinner.classList.remove('hidden');
        const success = await fetchPageData();
        if (success) {
            populateDropdowns();
            setupEventListeners();
            // We need to wait for home.js to potentially populate the team dropdown,
            // but for now, we'll just load with whatever value is present.
            await fetchAndRenderTable(); // Load initial data
        }
    }

    init();

})();
