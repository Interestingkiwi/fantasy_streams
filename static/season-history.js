(async function() {
    await new Promise(resolve => setTimeout(resolve, 0));

    const errorDiv = document.getElementById('db-error-message');
    const weekSelect = document.getElementById('week-select');
    const yourTeamSelect = document.getElementById('your-team-select');


    function populateDropdowns() {
        weekSelect.innerHTML = pageData.weeks.map(week =>
            `<option value="${week.week_num}">
                Week ${week.week_num} (${week.start_date} to ${week.end_date})
            </option>`
        ).join('');

        const teamOptions = pageData.teams.map(team =>
            `<option value="${team.name}">${team.name}</option>`
        ).join('');
        yourTeamSelect.innerHTML = teamOptions;

        const savedTeam = localStorage.getItem('selectedTeam');
        if (savedTeam) {
            yourTeamSelect.value = savedTeam;
        }

        if (!sessionStorage.getItem('fantasySessionStarted')) {
            const currentWeek = pageData.current_week;
            weekSelect.value = currentWeek;
            localStorage.setItem('selectedWeek', currentWeek);
            sessionStorage.setItem('fantasySessionStarted', 'true');
        } else {
            const savedWeek = localStorage.getItem('selectedWeek');
            if (savedWeek) {
                weekSelect.value = savedWeek;
            } else {
                weekSelect.value = pageData.current_week;
            }
        }
    }


    function setupEventListeners() {
        weekSelect.addEventListener('change', fetchAndRenderTable);
        yourTeamSelect.addEventListener('change', fetchAndRenderTable);
    }

    init();
