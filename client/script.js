document.addEventListener('DOMContentLoaded', () => {
    const loginView = document.getElementById('login-view');
    const appView = document.getElementById('app-view');
    const loginButton = document.getElementById('login-button');
    const logoutButton = document.getElementById('logout-button');
    const useLeagueButton = document.getElementById('use-league-button');

    const loadingLeaguesState = document.getElementById('loading-leagues-state');
    const initializingDbState = document.getElementById('initializing-db-state');
    const dataState = document.getElementById('data-state');
    const errorState = document.getElementById('error-state');
    const leaguesDropdown = document.getElementById('leagues-dropdown');

    let statusInterval;

    async function fetchAndDisplayLeagues() {
        showView(appView);
        showWithinApp(loadingLeaguesState);

        try {
            const response = await fetch('/api/leagues');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const leagues = await response.json();

            if (leagues.error) {
                 throw new Error(leagues.error);
            }

            if (leagues.length === 0) {
                loadingLeaguesState.querySelector('p').textContent = 'No 2025 fantasy leagues found.';
                return;
            }

            leaguesDropdown.innerHTML = '';
            leagues.forEach(league => {
                const option = document.createElement('option');
                option.value = league.league_id;
                option.textContent = league.name;
                leaguesDropdown.appendChild(option);
            });

            showWithinApp(dataState);

        } catch (error) {
            console.error("Error fetching leagues:", error);
            showWithinApp(errorState);
        }
    }

    function showWithinApp(elementToShow) {
        [loadingLeaguesState, initializingDbState, dataState, errorState].forEach(el => {
            el.classList.add('hidden');
        });
        elementToShow.classList.remove('hidden');
    }

    function showView(viewToShow) {
        [loginView, appView].forEach(view => view.classList.add('hidden'));
        viewToShow.classList.remove('hidden');

        if(viewToShow === appView) {
            logoutButton.classList.remove('hidden');
        } else {
            logoutButton.classList.add('hidden');
        }
    }

    function handleLogin() {
        window.location.href = '/login';
    }

    async function handleLogout() {
        await fetch('/logout');
        showView(loginView);
        if (statusInterval) {
            clearInterval(statusInterval);
        }
    }

    async function handleUseLeague() {
        const selectedLeagueId = leaguesDropdown.value;
        showWithinApp(initializingDbState);

        try {
            const response = await fetch('/api/initialize_league', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ league_id: selectedLeagueId }),
            });
            const data = await response.json();

            if (data.status === 'exists') {
                 window.location.href = '/home';
            } else if (data.status === 'initializing') {
                // Start polling for status
                statusInterval = setInterval(() => checkLeagueStatus(selectedLeagueId), 3000);
            } else {
                throw new Error(data.message || 'Failed to start initialization.');
            }

        } catch (error) {
            console.error('Error initializing league:', error);
            errorState.querySelector('p').textContent = 'Error initializing league.';
            showWithinApp(errorState);
        }
    }

    async function checkLeagueStatus(leagueId) {
        try {
            const response = await fetch(`/api/league_status/${leagueId}`);
            const data = await response.json();

            if (data.status === 'complete') {
                clearInterval(statusInterval);
                window.location.href = '/home';
            } else if (data.status === 'error') {
                 clearInterval(statusInterval);
                 console.error('Database initialization failed:', data.message);
                 errorState.querySelector('p').textContent = 'Database initialization failed.';
                 showWithinApp(errorState);
            }
            // If status is 'initializing', do nothing and let the interval continue.
        } catch (error) {
             clearInterval(statusInterval);
             console.error('Error checking league status:', error);
             errorState.querySelector('p').textContent = 'Error checking league status.';
             showWithinApp(errorState);
        }
    }


    async function checkInitialState() {
        try {
            const response = await fetch('/api/user');
            const data = await response.json();

            if (data.loggedIn) {
                fetchAndDisplayLeagues();
            } else {
                showView(loginView);
            }
        } catch (error) {
            console.error("Error checking login state:", error);
            showView(loginView);
        }
    }

    loginButton.addEventListener('click', handleLogin);
    logoutButton.addEventListener('click', handleLogout);
    useLeagueButton.addEventListener('click', handleUseLeague);

    checkInitialState();
});
