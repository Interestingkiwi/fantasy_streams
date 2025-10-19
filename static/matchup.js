document.addEventListener('DOMContentLoaded', function() {
    const weekSelector = document.getElementById('week-selector');
    const today = new Date();
    const currentDay = today.getDay(); // 0 for Sunday, 1 for Monday, etc.
    const monday = new Date(today);
    monday.setDate(today.getDate() - currentDay + (currentDay === 0 ? -6 : 1)); // Adjust to the most recent Monday

    // Populate week selector
    for (let i = 0; i < 26; i++) { // Assuming a 26-week season
        const weekStart = new Date(monday);
        weekStart.setDate(monday.getDate() - (i * 7));
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);

        const option = document.createElement('option');
        option.value = weekStart.toISOString().split('T')[0];
        option.textContent = `Week of ${weekStart.toLocaleDateString()} - ${weekEnd.toLocaleDateString()}`;
        if (i === 0) {
            option.selected = true;
        }
        weekSelector.appendChild(option);
    }

    // Set default value for opponent selector if it exists
    const opponentSelector = document.getElementById('opponent-selector');
    if (opponentSelector && opponentSelector.options.length > 0) {
        const leagueId = document.getElementById('league-id').value;
        const defaultOpponent = localStorage.getItem(`defaultOpponent_${leagueId}`);
        if (defaultOpponent) {
            opponentSelector.value = defaultOpponent;
        }
    }


    weekSelector.addEventListener('change', getMatchupData);
    if (opponentSelector) {
        opponentSelector.addEventListener('change', function() {
            const leagueId = document.getElementById('league-id').value;
            localStorage.setItem(`defaultOpponent_${leagueId}`, this.value);
            getMatchupData();
        });
    }

    getMatchupData(); // Initial data load
});

function getMatchupData() {
    const leagueId = document.getElementById('league-id').value;
    const weekStartDate = document.getElementById('week-selector').value;
    const opponentSelector = document.getElementById('opponent-selector');
    let opponentTeamId = null;
    if (opponentSelector){
        opponentTeamId = opponentSelector.value;
    }


    if (!opponentTeamId) {
        console.log("No opponent selected");
        // Clear tables if no opponent is selected
        document.querySelector('#my-team-table tbody').innerHTML = '<tr><td colspan="2">Select an opponent</td></tr>';
        document.querySelector('#opponent-team-table tbody').innerHTML = '<tr><td colspan="2">Select an opponent</td></tr>';
        document.querySelector('#projected-matchup-table tbody').innerHTML = '<tr><td colspan="3">Select an opponent to see projections</td></tr>';
        document.getElementById('my-team-score').textContent = '0';
        document.getElementById('opponent-team-score').textContent = '0';
        document.getElementById('projected-score').textContent = '0 - 0 - 0';
        return;
    }

    showLoading();

    fetch(`/get_matchup_data?league_id=${leagueId}&week_start_date=${weekStartDate}&opponent_team_id=${opponentTeamId}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error fetching matchup data:', data.error);
                hideLoading();
                return;
            }
            document.getElementById('my-team-name').textContent = data.my_team.name;
            document.getElementById('opponent-team-name').textContent = data.opponent_team.name;

            createMatchupTable(data.my_team, 'my-team-table', false);
            createMatchupTable(data.opponent_team, 'opponent-team-table', true);

            createProjectedTable(data.my_team, data.opponent_team, data.my_team_projections, data.opponent_team_projections);

            updateScores(data.my_team, data.opponent_team);

            hideLoading();
        })
        .catch(error => {
            console.error('Error fetching matchup data:', error);
            hideLoading();
        });
}

function createMatchupTable(teamData, tableId, isOpponent) {
    const tableBody = document.querySelector(`#${tableId} tbody`);
    tableBody.innerHTML = ''; // Clear existing rows

    const goalieStats = [
        'W', 'L', 'GAA', 'SV%', 'SO', 'SV', 'GA',
        'Wins', 'Losses', 'Goals Against Average', 'Save Percentage', 'Shutouts', 'Saves', 'Goals Against'
    ];

    const sortedStats = [...teamData.stats].sort((a, b) => {
        const aIsGoalie = goalieStats.includes(a.stat_name);
        const bIsGoalie = goalieStats.includes(b.stat_name);

        if (aIsGoalie && !bIsGoalie) {
            return 1; // a (goalie) comes after b (skater)
        }
        if (!aIsGoalie && bIsGoalie) {
            return -1; // a (skater) comes before b (goalie)
        }
        return 0; // maintain original relative order
    });


    for (const row of sortedStats) {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${row.stat_name}</td>
            <td class="stat-value">${formatStat(row.stat_name, row.stat_value)}</td>
        `;
        tableBody.appendChild(tr);
    }
    updateTeamScore(tableId, teamData.win_count || 0);
}

function updateTeamScore(tableId, score) {
    const scoreElementId = tableId.replace('-table', '-score');
    const scoreElement = document.getElementById(scoreElementId);
    if (scoreElement) {
        scoreElement.textContent = score;
    }
}

function createProjectedTable(myTeamData, opponentData, myTeamProjections, opponentProjections) {
    const tableBody = document.querySelector('#projected-matchup-table tbody');
    tableBody.innerHTML = '';

    const goalieStats = [
        'W', 'L', 'GAA', 'SV%', 'SO', 'SV', 'GA',
        'Wins', 'Losses', 'Goals Against Average', 'Save Percentage', 'Shutouts', 'Saves', 'Goals Against'
    ];

    const allStatNames = Array.from(new Set([
        ...myTeamData.stats.map(s => s.stat_name),
        ...opponentData.stats.map(s => s.stat_name)
    ]));

    allStatNames.sort((a, b) => {
        const aIsGoalie = goalieStats.includes(a);
        const bIsGoalie = goalieStats.includes(b);

        if (aIsGoalie && !bIsGoalie) {
            return 1;
        }
        if (!aIsGoalie && bIsGoalie) {
            return -1;
        }
        // If they are of the same type, maintain a consistent order based on the myTeamData stat order
        const myTeamStatNames = myTeamData.stats.map(s => s.stat_name);
        return myTeamStatNames.indexOf(a) - myTeamStatNames.indexOf(b);
    });


    let myProjectedWins = 0;
    let opponentProjectedWins = 0;
    let ties = 0;

    for (const statName of allStatNames) {
        const myStat = myTeamData.stats.find(s => s.stat_name === statName);
        const opponentStat = opponentData.stats.find(s => s.stat_name === statName);

        const myCurrentValue = myStat ? parseFloat(myStat.stat_value) : 0;
        const opponentCurrentValue = opponentStat ? parseFloat(opponentStat.stat_value) : 0;

        const myProjectedValue = myTeamProjections[statName] || 0;
        const opponentProjectedValue = opponentProjections[statName] || 0;

        const myCombinedValue = myCurrentValue + myProjectedValue;
        const opponentCombinedValue = opponentCurrentValue + opponentProjectedValue;

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${formatStat(statName, myCombinedValue)}</td>
            <td class="stat-name-proj"><strong>${statName}</strong></td>
            <td>${formatStat(statName, opponentCombinedValue)}</td>
        `;

        const myTotalCell = tr.children[0];
        const opponentTotalCell = tr.children[2];

        // Inverse categories where lower is better
        const isInverseStat = ['GAA', 'L', 'GA', 'Losses', 'Goals Against Average', 'Goals Against', 'PIM', 'Penalty Minutes'].includes(statName);

        if (isInverseStat) {
            if (myCombinedValue < opponentCombinedValue) {
                myTotalCell.classList.add('winning');
                myProjectedWins++;
            } else if (opponentCombinedValue < myCombinedValue) {
                opponentTotalCell.classList.add('winning');
                opponentProjectedWins++;
            } else if (myCombinedValue === opponentCombinedValue && myCombinedValue !== 0){
                ties++;
            }
        } else {
            if (myCombinedValue > opponentCombinedValue) {
                myTotalCell.classList.add('winning');
                myProjectedWins++;
            } else if (opponentCombinedValue > myCombinedValue) {
                opponentTotalCell.classList.add('winning');
                opponentProjectedWins++;
            } else if (myCombinedValue === opponentCombinedValue && myCombinedValue !== 0){
                ties++;
            }
        }

        tableBody.appendChild(tr);
    }

    const scoreElement = document.getElementById('projected-score');
    scoreElement.textContent = `${myProjectedWins} - ${opponentProjectedWins} - ${ties}`;
}


function updateScores(myTeamData, opponentData) {
    let myWinCount = 0;
    let opponentWinCount = 0;
    let tieCount = 0;

    myTeamData.stats.forEach(myStat => {
        const opponentStat = opponentData.stats.find(s => s.stat_name === myStat.stat_name);
        if (opponentStat) {
            const myValue = parseFloat(myStat.stat_value);
            const opponentValue = parseFloat(opponentStat.stat_value);

            // Inverse categories where lower is better
            const isInverseStat = ['GAA', 'L', 'GA', 'Losses', 'Goals Against Average', 'Goals Against', 'PIM', 'Penalty Minutes'].includes(myStat.stat_name);

            if (isInverseStat) {
                if (myValue < opponentValue) {
                    myWinCount++;
                } else if (opponentValue < myValue) {
                    opponentWinCount++;
                } else if (myValue === opponentValue && myValue !== 0) {
                    tieCount++;
                }
            } else {
                 if (myValue > opponentValue) {
                    myWinCount++;
                } else if (opponentValue > myValue) {
                    opponentWinCount++;
                } else if (myValue === opponentValue && myValue !== 0) {
                    tieCount++;
                }
            }
        }
    });

    document.getElementById('my-team-score').textContent = myWinCount;
    document.getElementById('opponent-team-score').textContent = opponentWinCount;
    document.getElementById('tie-count').textContent = tieCount;

}


function formatStat(statName, value) {
    const floatStats = ['SV%', 'GAA', 'Save Percentage', 'Goals Against Average', 'Shooting Percentage'];
    if (floatStats.includes(statName)) {
        // For GAA, ensure 2 decimal places. For SV%, 3.
        const decimalPlaces = (statName === 'GAA' || statName === 'Goals Against Average') ? 2 : 3;
        // Check if value is a number before calling toFixed
        if (typeof value === 'number') {
            return value.toFixed(decimalPlaces);
        }
    }
    // if value is a float, but not in floatStats, round to 2 decimal places
    if (typeof value === 'number' && value % 1 !== 0) {
        return value.toFixed(2);
    }

    return value;
}

function showLoading() {
    document.getElementById('loading-overlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loading-overlay').style.display = 'none';
}
