// Wildcard Weekend 2026 - Pure Display Layer
// All logic is in Python backend; JS only renders pre-computed data

const API_BASE = '';

// State
let displayData = null;
let autoRefreshInterval = null;
let demoInterval = null;
let demoRunning = false;
const AUTO_REFRESH_MS = 60000;
const DEMO_TICK_MS = 2000;

// DOM Elements
const simulateBtn = document.getElementById('simulate-btn');
const refreshBtn = document.getElementById('refresh-btn');
const demoBtn = document.getElementById('demo-btn');
const lastUpdateEl = document.getElementById('last-update');
const probabilityTable = document.getElementById('probability-table');
const teamsGrid = document.getElementById('teams-grid');
const gamesList = document.getElementById('games-list');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await runSimulation();
    simulateBtn.addEventListener('click', runSimulation);
    refreshBtn.addEventListener('click', refreshLiveData);
    demoBtn.addEventListener('click', toggleDemoMode);
    startAutoRefresh();
});

function startAutoRefresh() {
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    autoRefreshInterval = setInterval(refreshLiveData, AUTO_REFRESH_MS);
    updateRefreshStatus();
}

function updateRefreshStatus() {
    const demoStatus = demoRunning ? ' · DEMO' : '';
    lastUpdateEl.textContent = `Updated ${formatTime(new Date())} · Auto-refresh 60s${demoStatus}`;
}

function toggleDemoMode() {
    if (demoRunning) {
        stopDemoMode();
    } else {
        startDemoMode();
    }
}

async function startDemoMode() {
    demoRunning = true;
    demoBtn.innerHTML = '<span class="btn-icon">■</span> Stop Demo';
    demoBtn.classList.add('demo-active');
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    await resetGamesForDemo();
    demoInterval = setInterval(demoTick, DEMO_TICK_MS);
    updateRefreshStatus();
}

function stopDemoMode() {
    demoRunning = false;
    demoBtn.innerHTML = '<span class="btn-icon">▷</span> Demo Mode';
    demoBtn.classList.remove('demo-active');
    if (demoInterval) {
        clearInterval(demoInterval);
        demoInterval = null;
    }
    startAutoRefresh();
}

async function resetGamesForDemo() {
    // Reset all games to Q1 start
    if (!displayData?.games) return;
    for (const game of displayData.games) {
        await fetch(`${API_BASE}/api/update_game`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: game.matchup,
                away_score: 0,
                home_score: 0,
                quarter: 1,
                time_remaining: 3600
            })
        });
    }
    await runSimulation();
}

async function demoTick() {
    // Fetch current state once
    const resp = await fetch(`${API_BASE}/api/scoreboard`);
    const data = await resp.json();
    if (!data.games) return;

    // Update each game
    for (const [gameId, game] of Object.entries(data.games)) {
        if (game.is_final) continue;

        // Advance clock by 2-3 minutes
        let newTime = game.time_remaining - Math.floor(120 + Math.random() * 60);
        let newQuarter = game.quarter;

        if (newTime <= 0) {
            if (newQuarter >= 4) {
                // Game ends
                await fetch(`${API_BASE}/api/update_game`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ game_id: gameId, quarter: 5, time_remaining: 0 })
                });
                continue;
            } else {
                // Next quarter
                newQuarter++;
                newTime = 900;
            }
        }

        // Random scoring (~15% chance per tick)
        let awayScore = game.away_score;
        let homeScore = game.home_score;
        if (Math.random() < 0.15) {
            const points = [3, 3, 3, 6, 7, 7, 7][Math.floor(Math.random() * 7)];
            if (Math.random() < 0.5) {
                awayScore += points;
            } else {
                homeScore += points;
            }
        }

        await fetch(`${API_BASE}/api/update_game`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                game_id: gameId,
                away_score: awayScore,
                home_score: homeScore,
                quarter: newQuarter,
                time_remaining: newTime
            })
        });
    }

    await runSimulation();
}

async function runSimulation() {
    simulateBtn.disabled = true;
    simulateBtn.innerHTML = '<span class="btn-icon">⏳</span> Running...';
    probabilityTable.innerHTML = '<div class="loading-cell">Calculating probabilities...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/simulate`);
        displayData = await response.json();

        if (displayData.error) {
            throw new Error(displayData.error);
        }

        renderAll();
        updateRefreshStatus();
    } catch (error) {
        console.error('Error:', error);
        probabilityTable.innerHTML = `<div class="loading-cell">Error: ${error.message}</div>`;
    } finally {
        simulateBtn.disabled = false;
        simulateBtn.innerHTML = '<span class="btn-icon">▶</span> Run Simulation';
    }
}

async function refreshLiveData() {
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<span class="btn-icon">⏳</span> Refreshing...';

    try {
        await fetch(`${API_BASE}/api/refresh`, { method: 'POST' });
        await runSimulation();
    } catch (error) {
        console.error('Error:', error);
    } finally {
        refreshBtn.disabled = false;
        refreshBtn.innerHTML = '<span class="btn-icon">↻</span> Refresh Data';
    }
}

function renderAll() {
    renderProbabilities();
    renderTeamsTable();
    renderGamesTable();
}

function renderProbabilities() {
    if (!displayData?.owners) return;

    const headerRow = `
        <div class="prob-row prob-header">
            <span class="prob-owner"></span>
            <div class="prob-bar-wrap" style="background: transparent; border: none;"></div>
            <span class="prob-percent">WIN%</span>
            <span class="prob-cur">CUR</span>
            <span class="prob-prj">PRJ</span>
            <span class="prob-mins">LEFT</span>
        </div>
    `;

    const rows = displayData.owners.map(owner => {
        const percent = (owner.win_probability * 100).toFixed(0);
        const width = owner.win_probability * 100;

        return `
            <div class="prob-row" onclick="scrollToTeam('${owner.name}')" style="cursor: pointer;">
                <span class="prob-owner">${owner.name}</span>
                <div class="prob-bar-wrap">
                    <div class="prob-bar" style="width: ${width}%; background: ${owner.color}"></div>
                </div>
                <span class="prob-percent">${percent}%</span>
                <span class="prob-cur">${owner.current_pts > 0 ? owner.current_pts.toFixed(1) : '-'}</span>
                <span class="prob-prj">${owner.projected_pts.toFixed(1)}</span>
                <span class="prob-mins">${owner.minutes_remaining}m</span>
            </div>
        `;
    }).join('');

    probabilityTable.innerHTML = headerRow + rows;
}

function renderTeamsTable() {
    if (!displayData?.owners) return;

    const html = displayData.owners.map(owner => {
        // Player rows
        const playerRows = owner.players.map(player => {
            if (!player.name) return '';

            const helmetImg = player.team
                ? `<img class="team-helmet" src="https://a.espncdn.com/i/teamlogos/nfl/500/${player.team.toLowerCase()}.png" alt="${player.team}">`
                : '';

            return `
                <div class="roster-row">
                    <span class="slot-label">${player.slot}</span>
                    ${helmetImg}
                    <span class="player-name">${formatPlayerName(player.name)}</span>
                    <span class="pts cur">${player.current_pts > 0 ? player.current_pts.toFixed(1) : '-'}</span>
                    <span class="pts prj">${player.projected_pts.toFixed(1)}</span>
                </div>
            `;
        }).join('');

        // Bet rows
        const betRows = owner.bets.map(bet => {
            const probColor = getProbColor(bet.probability);
            const statusClass = bet.status === 'winning' || bet.status === 'won' ? 'winning' :
                               bet.status === 'losing' || bet.status === 'lost' ? 'losing' : 'pending';

            return `
                <div class="bet-row ${statusClass}">
                    <span class="bet-info">${bet.description}</span>
                    <span class="bet-prob" style="color: ${probColor}">${(bet.probability * 100).toFixed(0)}%</span>
                    <span class="pts cur">${bet.current_pts > 0 ? bet.current_pts.toFixed(1) : '-'}</span>
                    <span class="pts prj">${bet.projected_pts.toFixed(1)}</span>
                </div>
            `;
        }).join('');

        return `
            <div class="team-card" id="team-${owner.name.toLowerCase()}">
                <div class="card-header" style="background: ${owner.color}">${owner.name}</div>
                <div class="card-body">
                    <div class="col-headers">
                        <span class="col-spacer"></span>
                        <span class="col-label">CUR</span>
                        <span class="col-label">PRJ</span>
                    </div>
                    <div class="roster-section">
                        ${playerRows}
                        <div class="roster-subtotal">
                            <span>Players</span>
                            <span class="pts cur">${owner.player_current_total > 0 ? owner.player_current_total.toFixed(1) : '-'}</span>
                            <span class="pts prj">${owner.player_projected_total.toFixed(1)}</span>
                        </div>
                    </div>
                    <div class="bets-section">
                        ${betRows}
                    </div>
                    <div class="card-total">
                        <span>TOTAL</span>
                        <span class="pts cur">${owner.current_pts > 0 ? owner.current_pts.toFixed(1) : '-'}</span>
                        <span class="pts prj">${owner.projected_pts.toFixed(1)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    teamsGrid.innerHTML = html;
}

function renderGamesTable() {
    if (!displayData?.games) {
        gamesList.innerHTML = '<div class="loading-cell">No games found</div>';
        return;
    }

    gamesList.innerHTML = displayData.games.map(game => {
        const [away, home] = game.matchup.split(' @ ');
        const awayHelmet = `<img class="game-helmet" src="https://a.espncdn.com/i/teamlogos/nfl/500/${away.toLowerCase()}.png" alt="${away}">`;
        const homeHelmet = `<img class="game-helmet" src="https://a.espncdn.com/i/teamlogos/nfl/500/${home.toLowerCase()}.png" alt="${home}">`;
        return `
            <div class="game-row">
                <div class="game-teams">
                    <span class="game-team">${awayHelmet}<span class="game-team-score">${game.away_score}</span></span>
                    <span class="game-at">@</span>
                    <span class="game-team"><span class="game-team-score">${game.home_score}</span>${homeHelmet}</span>
                </div>
                <div class="game-details">
                    <span class="status-badge ${game.status_class}">${game.status}</span>
                    <span class="game-line">o${game.over_under} | ${game.spread}</span>
                </div>
            </div>
        `;
    }).join('');
}

function scrollToTeam(ownerName) {
    const teamCard = document.getElementById(`team-${ownerName.toLowerCase()}`);
    if (teamCard) {
        teamCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        teamCard.classList.add('highlight');
        setTimeout(() => teamCard.classList.remove('highlight'), 1500);
    }
}

// Display helpers (no logic, just formatting)
function formatPlayerName(name) {
    if (!name) return '';
    if (name.length > 18) {
        const parts = name.split(' ');
        if (parts.length >= 2) {
            return `${parts[0][0]}. ${parts.slice(1).join(' ')}`;
        }
    }
    return name;
}

function formatTime(date) {
    return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit'
    });
}

function getProbColor(prob) {
    // Display styling: red=0%, yellow=50%, green=100%
    if (prob < 0.5) {
        const t = prob * 2;
        const r = 200;
        const g = Math.floor(180 * t);
        return `rgb(${r}, ${g}, 0)`;
    } else {
        const t = (prob - 0.5) * 2;
        const r = Math.floor(200 * (1 - t));
        const g = Math.floor(140 + 40 * t);
        return `rgb(${r}, ${g}, 0)`;
    }
}
