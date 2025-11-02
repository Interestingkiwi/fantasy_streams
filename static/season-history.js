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
    const weekSelect = document.getElementById('week-select');
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
        // 1. Populate "Your Team" dropdown (same as before)
        const teamOptions = pageData.teams.map(team =>
            `<option value="${team.name}">${team.name}</option>`
        ).join('');
        yourTeamSelect.innerHTML = teamOptions;

        // Set saved team
        const savedTeam = localStorage.getItem('selectedTeam');
        if (savedTeam && pageData.teams.some(t => t.name === savedTeam)) {
            yourTeamSelect.value = savedTeam;
        } else if (pageData.teams.length > 0) {
            // Default to first team if no selection saved
            yourTeamSelect.value = pageData.teams[0].name;
            localStorage.setItem('selectedTeam', pageData.teams[0].name);
        }

        // 2. Populate "Week" dropdown (New Logic)

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
        weekSelect.addEventListener('change', fetchAndRenderTable);

        yourTeamSelect.addEventListener('change', () => {
            localStorage.setItem('selectedTeam', yourTeamSelect.value);
            fetchAndRenderTable();
        });
    }

    async function fetchAndRenderTable() {
        // This is the placeholder for your next step.
        // We will build this out to fetch and display the historical data.
        console.log(`Fetching data for: ${yourTeamSelect.value}, Week: ${weekSelect.value}`);

        // Show spinner (and hide it after a delay, for now)
        loadingSpinner.classList.remove('hidden');
        historyContent.innerHTML = ''; // Clear previous content

        // --- SIMULATE API CALL ---
        // In the future, this is where you'll fetch data from the backend
        // based on the selected team and week.
        await new Promise(resolve => setTimeout(resolve, 500)); // Simulate network delay

        historyContent.innerHTML = `<p class="text-gray-400">Data for ${yourTeamSelect.value} (Week ${weekSelect.value}) will be displayed here.</p>`;
        loadingSpinner.classList.add('hidden');
    }

    async function init() {
        loadingSpinner.classList.remove('hidden');
        const success = await fetchPageData();
        if (success) {
            populateDropdowns();
            setupEventListeners();
            await fetchAndRenderTable(); // Load initial data
        }
    }

    init();

})();
