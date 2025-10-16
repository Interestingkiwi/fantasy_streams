document.addEventListener('DOMContentLoaded', () => {
    const mainContent = document.getElementById('main-content');
    const entryView = document.getElementById('entry-view');
    const initializingDbState = document.getElementById('initializing-db-state');
    const errorState = document.getElementById('error-state');
    const errorMessage = document.getElementById('error-message');

    const useLeagueButton = document.getElementById('use-league-button');
    const leagueIdInput = document.getElementById('league-id-input');
    const logoutButton = document.getElementById('logout-button');
    const tryAgainButton = document.getElementById('try-again-button');

    let statusInterval;

    function showView(viewToShow) {
        [entryView, initializingDbState, errorState].forEach(el => el.classList.add('hidden'));
        viewToShow.classList.remove('hidden');
    }

    function showError(message = 'Please try again.') {
        errorMessage.textContent = message;
        showView(errorState);
    }

    async function handleUseLeague() {
        const leagueId = leagueIdInput.value.trim();
        if (!leagueId || !/^\d+$/.test(leagueId)) {
            alert('Please enter a valid numeric League ID.');
            return;
        }

        // Store leagueId in sessionStorage to survive the redirect
        sessionStorage.setItem('leagueIdForAuth', leagueId);

        // Check if we are already logged in
        const userResponse = await fetch('/api/user');
        const userData = await userResponse.json();

        if (userData.loggedIn) {
            // If already logged in, proceed to initialize directly
            initializeLeague(leagueId);
        } else {
            // If not logged in, redirect to the server's login route to start OAuth
            window.location.href = '/login';
        }
    }

    async function initializeLeague(leagueId) {
        showView(initializingDbState);
        try {
            const response = await fetch('/api/initialize_league', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ league_id: leagueId }),
            });
            const data = await response.json();

            if (data.status === 'exists') {
                window.location.href = '/home';
            } else if (data.status === 'initializing') {
                statusInterval = setInterval(() => checkLeagueStatus(leagueId), 5000);
            } else {
                throw new Error(data.message || 'Failed to start initialization.');
            }
        } catch (error) {
            console.error('Error initializing league:', error);
            showError('Could not initialize the league. Please check the League ID and try again.');
        }
    }

    async function checkLeagueStatus(leagueId) {
        try {
            const response = await fetch(`/api/league_status/${leagueId}`);
            if (!response.ok) {
                 throw new Error(`Server responded with status: ${response.status}`);
            }
            const data = await response.json();

            if (data.status === 'complete') {
                clearInterval(statusInterval);
                window.location.href = '/home';
            } else if (data.status === 'error') {
                clearInterval(statusInterval);
                console.error('Database initialization failed:', data.message);
                showError(data.message || 'Database initialization failed.');
            }
        } catch (error) {
            clearInterval(statusInterval);
            console.error('Error checking league status:', error);
            showError('Lost connection while checking league status.');
        }
    }

    async function handleLogout() {
        await fetch('/logout');
        sessionStorage.removeItem('leagueIdForAuth');
        window.location.href = '/';
    }

    async function checkInitialState() {
        const urlParams = new URLSearchParams(window.location.search);
        const authCode = urlParams.get('code');
        const leagueId = sessionStorage.getItem('leagueIdForAuth');

        if (authCode && leagueId) {
            // We've just returned from Yahoo auth
            // Clean the URL
            window.history.replaceState({}, document.title, "/");
            // The backend is now creating the token file. Let's start initialization.
            initializeLeague(leagueId);
            sessionStorage.removeItem('leagueIdForAuth');
        } else {
             // Standard page load
             const userResponse = await fetch('/api/user');
             const userData = await userResponse.json();
             if (userData.loggedIn) {
                 logoutButton.classList.remove('hidden');
             }
             showView(entryView);
        }
    }

    useLeagueButton.addEventListener('click', handleUseLeague);
    logoutButton.addEventListener('click', handleLogout);
    tryAgainButton.addEventListener('click', () => window.location.href = '/');

    checkInitialState();
});
