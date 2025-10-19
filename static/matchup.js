document.addEventListener('DOMContentLoaded', function() {
    // This function runs when the page is loaded and kicks off the process
    // of populating the week dropdown.
    fetchWeeks();
});

function fetchWeeks() {
    // Fetches the available weeks from your API.
    fetch('/api/weeks')
        .then(response => response.json())
        .then(weeks => {
            const weekSelector = document.getElementById('week');
            weekSelector.innerHTML = ''; // Clear any existing options

            // Create a new <option> for each week and add it to the dropdown.
            weeks.forEach(week => {
                const option = document.createElement('option');
                option.value = week;
                option.textContent = `Week ${week}`;
                weekSelector.appendChild(option);
            });

            // If we successfully loaded weeks, automatically load the teams for the first week.
            if (weeks.length > 0) {
                getMatchups();
            }
        })
        .catch(error => console.error('Error fetching weeks:', error));
}

function getMatchups() {
    // This function is called when the selected week changes.
    const week = document.getElementById('week').value;
    if (!week) return;

    // Fetches the list of teams for the selected week.
    fetch(`/api/teams?week=${week}`)
        .then(response => response.json())
        .then(teams => {
            const team1Selector = document.getElementById('team1');
            const team2Selector = document.getElementById('team2');
            team1Selector.innerHTML = ''; // Clear previous team options
            team2Selector.innerHTML = '';

            // Populate both team dropdowns with the new list of teams.
            teams.forEach(team => {
                const option1 = document.createElement('option');
                option1.value = team.team_id;
                option1.textContent = team.name;
                team1Selector.appendChild(option1);

                const option2 = document.createElement('option');
                option2.value = team.team_id;
                option2.textContent = team.name;
                team2Selector.appendChild(option2);
            });
        })
        .catch(error => console.error('Error fetching teams:', error));
}

function getComparison() {
    // This function runs when you click the "Get Comparison" button.
    const week = document.getElementById('week').value;
    const team1 = document.getElementById('team1').value;
    const team2 = document.getElementById('team2').value;

    if (!week || !team1 || !team2) {
        // Use a more user-friendly modal instead of alert
        showModal('Please select a week and two teams.');
        return;
    }

    if (team1 === team2) {
        showModal('Please select two different teams.');
        return;
    }

    // Fetches the matchup comparison data from your API.
    fetch(`/api/comparison?week=${week}&team1=${team1}&team2=${team2}`)
        .then(response => response.json())
        .then(data => {
            const comparisonDiv = document.getElementById('comparison');
            comparisonDiv.innerHTML = ''; // Clear previous comparison

            // Create a table to display the stats.
            const table = document.createElement('table');
            table.className = 'data-table';
            const thead = document.createElement('thead');
            const tbody = document.createElement('tbody');

            // Table Header
            let headerRow = `<tr><th>Category</th><th>${data.team1_name || 'Team 1'}</th><th>${data.team2_name || 'Team 2'}</th></tr>`;
            thead.innerHTML = headerRow;

            // Table Body - one row for each stat category.
            const categories = Object.keys(data.team1_stats);
            categories.forEach(category => {
                const row = document.createElement('tr');
                let t1_stat = data.team1_stats[category];
                let t2_stat = data.team2_stats[category];

                // Highlight the winning stat in each category.
                let t1_class = '';
                let t2_class = '';
                if (parseFloat(t1_stat) > parseFloat(t2_stat)) {
                    t1_class = 'winner';
                } else if (parseFloat(t2_stat) > parseFloat(t1_stat)) {
                    t2_class = 'winner';
                }

                row.innerHTML = `<td>${category}</td><td class="${t1_class}">${t1_stat}</td><td class="${t2_class}">${t2_stat}</td>`;
                tbody.appendChild(row);
            });

            table.appendChild(thead);
            table.appendChild(tbody);
            comparisonDiv.appendChild(table);
        })
        .catch(error => {
            console.error('Error fetching comparison:', error);
            const comparisonDiv = document.getElementById('comparison');
            comparisonDiv.innerHTML = '<p class="error-message">Error loading comparison data. Please try again.</p>';
        });
}

// A simple modal function to avoid using alert()
function showModal(message) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    const closeButton = document.createElement('span');
    closeButton.className = 'close-button';
    closeButton.innerHTML = '&times;';
    closeButton.onclick = () => modal.style.display = 'none';
    const messageP = document.createElement('p');
    messageP.textContent = message;

    modalContent.appendChild(closeButton);
    modalContent.appendChild(messageP);
    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    modal.style.display = 'block';

    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }
}
