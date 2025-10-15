document.addEventListener('DOMContentLoaded', () => {
    // Get references to all necessary elements
    const loginView = document.getElementById('login-view');
    const appView = document.getElementById('app-view');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const rememberMeCheckbox = document.getElementById('remember-me');

    // App view elements
    const loadingState = document.getElementById('loading-state');
    const dataState = document.getElementById('data-state');
    const errorState = document.getElementById('error-state');
    const leaguesDropdown = document.getElementById('leagues-dropdown');


    // --- Function Definitions ---

    /**
     * Fetches the user's league data from the backend and populates the dropdown.
     */
    async function fetchAndDisplayLeagues() {
        // Show loading state, hide others
        loadingState.classList.remove('hidden');
        dataState.classList.add('hidden');
        errorState.classList.add('hidden');
        leaguesDropdown.innerHTML = ''; // Clear previous options

        try {
            const response = await fetch('/api/leagues');
            if (!response.ok) {
                throw new Error('Failed to fetch leagues');
            }
            const leagues = await response.json();

            if (leagues.length === 0) {
                loadingState.querySelector('p').textContent = 'No 2025 fantasy leagues found.';
                return; // Keep showing the modified loading message
            }

            // Populate dropdown
            leagues.forEach(league => {
                const option = document.createElement('option');
                option.value = league.league_id;
                option.textContent = league.name;
                leaguesDropdown.appendChild(option);
            });

            // Show data state
            dataState.classList.remove('hidden');
            loadingState.classList.add('hidden');

        } catch (error) {
            console.error("Error fetching leagues:", error);
            // Show error state
            errorState.classList.remove('hidden');
            loadingState.classList.add('hidden');
        }
    }


    /**
     * Switches the view to the main application and triggers data fetching.
     */
    function showAppView() {
        loginView.classList.add('hidden');
        appView.classList.remove('hidden');
        fetchAndDisplayLeagues();
    }

    /**
     * Switches the view to the login page.
     */
    function showLoginView() {
        appView.classList.add('hidden');
        loginView.classList.remove('hidden');
    }

    /**
     * Initiates the login process by redirecting to the backend.
     */
    function handleLogin() {
        // Use a relative path for the login route. This will work on any domain.
        window.location.href = '/login';
    }

    /**
     * Handles the logout process.
     */
    async function handleLogout() {
        // Use a relative path for the logout route.
        await fetch('/logout');

        localStorage.removeItem('isLoggedIn'); // Clear any old local storage flags

        // Show the login page.
        showLoginView();
    }

    /**
     * Checks the login state with the backend when the page loads.
     */
    async function checkInitialState() {
        try {
            // Use a relative path to check the user's login status.
            const response = await fetch('/api/user');
            const data = await response.json();

            if (data.loggedIn) {
                showAppView();
            } else {
                showLoginView();
            }
        } catch (error) {
            console.error("Error checking login state:", error);
            showLoginView(); // If the backend is not running, show login.
        }
    }

    // --- Event Listeners ---

    // Add click listener for the login button.
    loginButton.addEventListener('click', handleLogin);

    // Add click listener for the logout button.
    logoutButton.addEventListener('click', handleLogout);

    // --- Initial Execution ---

    // Check the login state as soon as the page is ready.
    checkInitialState();
});
