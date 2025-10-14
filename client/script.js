document.addEventListener('DOMContentLoaded', () => {
    // Get references to all necessary elements
    const loginView = document.getElementById('login-view');
    const appView = document.getElementById('app-view');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const rememberMeCheckbox = document.getElementById('remember-me');

    // --- Function Definitions ---

    /**
     * Switches the view to the main application.
     */
    function showAppView() {
        loginView.classList.add('hidden');
        appView.classList.remove('hidden');
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
