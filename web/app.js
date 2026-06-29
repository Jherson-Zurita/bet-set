/**
 * Value Bet Finder — Frontend Application
 * 
 * Handles data fetching, rendering, filtering, and interactions
 * for both the main page (index.html) and detail page (match.html).
 */

// ============================================================
// CONFIGURATION
// ============================================================

const CONFIG = {
  // API base URL — empty for same-origin (Vercel), or set for local dev
  API_BASE: '',
  REFRESH_INTERVAL: 5 * 60 * 1000, // 5 minutes
  MOCK_MODE: true, // Will be overridden if API is available
};

// Country flag emojis mapping — incluye los 48 equipos del Mundial 2026
const TEAM_FLAGS = {
  // Conmebol / Sudamérica
  'Argentina': '🇦🇷', 'Brasil': '🇧🇷', 'Uruguay': '🇺🇾',
  'Colombia': '🇨🇴', 'Chile': '🇨🇱', 'Perú': '🇵🇪',
  'Paraguay': '🇵🇾', 'Ecuador': '🇪🇨',
  // Concacaf
  'México': '🇲🇽', 'Estados Unidos': '🇺🇸', 'Canadá': '🇨🇦',
  'Costa Rica': '🇨🇷', 'Panamá': '🇵🇦', 'Curazao': '🇨🇼',
  // UEFA
  'Francia': '🇫🇷', 'Alemania': '🇩🇪', 'España': '🇪🇸',
  'Inglaterra': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'Portugal': '🇵🇹', 'Países Bajos': '🇳🇱',
  'Italia': '🇮🇹', 'Bélgica': '🇧🇪', 'Croacia': '🇭🇷',
  'Suiza': '🇨🇭', 'Dinamarca': '🇩🇰', 'Serbia': '🇷🇸',
  'Polonia': '🇵🇱', 'Gales': '🏴󠁧󠁢󠁷󠁬󠁳󠁿', 'Austria': '🇦🇹',
  'Ucrania': '🇺🇦', 'Suecia': '🇸🇪', 'Noruega': '🇳🇴',
  'Escocia': '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'Eslovaquia': '🇸🇰', 'Rumania': '🇷🇴',
  'Macedonia del Norte': '🇲🇰',
  // CAF / África
  'Marruecos': '🇲🇦', 'Senegal': '🇸🇳', 'Camerún': '🇨🇲',
  'Ghana': '🇬🇭', 'Egipto': '🇪🇬', 'Argelia': '🇩🇿',
  'Túnez': '🇹🇳', 'Costa de Marfil': '🇨🇮', 'Sudáfrica': '🇿🇦',
  'Cabo Verde': '🇨🇻',
  // AFC / Asia
  'Japón': '🇯🇵', 'Corea del Sur': '🇰🇷', 'Arabia Saudita': '🇸🇦',
  'Irán': '🇮🇷', 'Irak': '🇮🇶', 'Australia': '🇦🇺',
  'Qatar': '🇶🇦',
  // OFC / Oceanía
  'Nueva Zelanda': '🇳🇿',
  // Otros
  'Haití': '🇭🇹',
  // Placeholder para partidos TBD (octavos de final)
  'TBD': '🏳️',
};

// Market display names
const MARKET_NAMES = {
  'h2h': '⚽ Resultado Final (1X2)',
  'totals': '📊 Over / Under Goles',
  'btts': '🎯 Ambos Marcan (BTTS)',
};

// ============================================================
// STATE
// ============================================================

let state = {
  matches: [],
  currentFilter: 'all',
  refreshTimer: null,
  isDetailPage: false,
  matchDetail: null,
};

// ============================================================
// UTILITY FUNCTIONS
// ============================================================

function getFlag(teamName) {
  return TEAM_FLAGS[teamName] || '🏳️';
}

function formatTime(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  
  const time = date.toLocaleTimeString('es', { hour: '2-digit', minute: '2-digit' });
  
  if (isToday) {
    const diffMs = date - now;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins > 0 && diffMins < 60) {
      return `${time} · En ${diffMins} min`;
    } else if (diffMins >= 60) {
      const hours = Math.floor(diffMins / 60);
      return `${time} · En ${hours}h`;
    } else if (diffMins > -120 && diffMins <= 0) {
      return `${time} · En juego`;
    }
  }
  
  return `${time} · ${date.toLocaleDateString('es', { day: 'numeric', month: 'short' })}`;
}

function formatEdge(edge) {
  if (edge > 0) return `+${edge.toFixed(1)}%`;
  return `${edge.toFixed(1)}%`;
}

function showToast(message, duration = 3000) {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('visible');
  setTimeout(() => toast.classList.remove('visible'), duration);
}

function getMatchUrl(matchId) {
  return `match.html?id=${encodeURIComponent(matchId)}`;
}

function getMatchIdFromUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('id');
}

// ============================================================
// API CALLS (with mock fallback)
// ============================================================

async function fetchMatches() {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/matches`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    // Determinar modo demo según el backend
    if (data.is_mock && typeof data.is_mock === 'object') {
      CONFIG.MOCK_MODE = data.is_mock.world_cup || data.is_mock.odds || false;
    } else {
      CONFIG.MOCK_MODE = !!data.is_mock;
    }
    return data.matches || [];
  } catch (err) {
    console.error('[API] Fetch failed:', err.message);
    throw err; // Propagamos el error para mostrar mensaje claro
  }
}

async function fetchMatchDetail(matchId) {
  try {
    const response = await fetch(`${CONFIG.API_BASE}/api/match?id=${encodeURIComponent(matchId)}`);
    if (!response.ok) {
      const errBody = await response.text();
      throw new Error(`HTTP ${response.status} — ${errBody}`);
    }
    return await response.json();
  } catch (err) {
    console.error('[API] Match detail fetch failed:', err.message);
    throw err;
  }
}

// ============================================================
// RENDER: MAIN PAGE
// ============================================================

function renderMatchCard(match) {
  const bestBet = match.best_bet;
  const h2hMarket = match.markets?.h2h;
  const isPending = match.odds_pending || !h2hMarket;
  const edgeLevel = bestBet ? bestBet.classification.level : (isPending ? 'pending' : 'no-value');

  // Get h2h outcomes for display
  const outcomes = h2hMarket?.outcomes || [];
  const homeOutcome = outcomes.find(o => o.name === 'Home');
  const drawOutcome = outcomes.find(o => o.name === 'Draw');
  const awayOutcome = outcomes.find(o => o.name === 'Away');

  const card = document.createElement('div');
  card.className = `match-card animate-in value-${edgeLevel}`;
  card.dataset.matchId = match.match_id;
  card.dataset.valueLevel = edgeLevel;
  card.dataset.hasValue = match.has_value ? 'true' : 'false';
  card.onclick = () => window.location.href = getMatchUrl(match.match_id);

  // Etiquetas de grupo/fase si están disponibles
  const groupLabel = match.group ? `<span class="group-tag">Grupo ${match.group}</span>` : '';
  const stageLabel = match.stage && match.stage !== 'Group'
    ? `<span class="stage-tag">${match.stage === 'Round of 16' ? 'Octavos' : (match.stage === 'Round of 32' ? 'Dieciseisavos' : match.stage)}</span>`
    : '';

  card.innerHTML = `
    <div class="match-card-header">
      <div class="match-time">
        <span class="clock-icon">🕐</span>
        ${formatTime(match.commence_time)}
      </div>
      ${isPending ? `
        <div class="edge-badge pending">⏳ Sin cuotas</div>
      ` : bestBet ? `
        <div class="edge-badge ${edgeLevel}">
          ${bestBet.classification.emoji} ${formatEdge(bestBet.edge)}
        </div>
      ` : `
        <div class="edge-badge no-value">⚪ Sin valor</div>
      `}
    </div>

    ${(groupLabel || stageLabel) ? `
      <div class="match-labels">
        ${groupLabel}
        ${stageLabel}
      </div>
    ` : ''}

    <div class="match-teams">
      <div class="team">
        <div class="team-flag">${getFlag(match.home_team)}</div>
        <div class="team-name">${match.home_team}</div>
      </div>
      <div class="vs-divider">VS</div>
      <div class="team">
        <div class="team-flag">${getFlag(match.away_team)}</div>
        <div class="team-name">${match.away_team}</div>
      </div>
    </div>

    <div class="odds-comparison">
      <div class="odds-item ${homeOutcome && homeOutcome.edge >= 3 ? 'has-value' : ''}">
        <div class="odds-label">Local</div>
        <div class="odds-value">${homeOutcome ? homeOutcome.bet365_odds.toFixed(2) : '—'}</div>
        <div class="odds-edge ${homeOutcome && homeOutcome.edge > 0 ? 'positive' : 'negative'}">
          ${homeOutcome ? formatEdge(homeOutcome.edge) : '—'}
        </div>
      </div>
      <div class="odds-item ${drawOutcome && drawOutcome.edge >= 3 ? 'has-value' : ''}">
        <div class="odds-label">Empate</div>
        <div class="odds-value">${drawOutcome ? drawOutcome.bet365_odds.toFixed(2) : '—'}</div>
        <div class="odds-edge ${drawOutcome && drawOutcome.edge > 0 ? 'positive' : 'negative'}">
          ${drawOutcome ? formatEdge(drawOutcome.edge) : '—'}
        </div>
      </div>
      <div class="odds-item ${awayOutcome && awayOutcome.edge >= 3 ? 'has-value' : ''}">
        <div class="odds-label">Visit.</div>
        <div class="odds-value">${awayOutcome ? awayOutcome.bet365_odds.toFixed(2) : '—'}</div>
        <div class="odds-edge ${awayOutcome && awayOutcome.edge > 0 ? 'positive' : 'negative'}">
          ${awayOutcome ? formatEdge(awayOutcome.edge) : '—'}
        </div>
      </div>
    </div>

    <div class="match-card-footer">
      ${isPending ? `
        <div class="best-bet-tag" style="color: var(--text-muted);">
          ⏳ Cuotas no disponibles aún
        </div>
      ` : bestBet ? `
        <div class="best-bet-tag">
          <span class="icon">🎯</span>
          Mejor: ${bestBet.outcome} @ ${bestBet.odds.toFixed(2)}
        </div>
      ` : `
        <div class="best-bet-tag" style="color: var(--text-muted);">
          Sin apuesta de valor
        </div>
      `}
      <div class="view-detail">
        Ver detalle →
      </div>
    </div>
  `;

  return card;
}

function renderMatches(matches) {
  const grid = document.getElementById('matches-grid');
  if (!grid) return;

  grid.innerHTML = '';

  if (matches.length === 0) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚽</div>
        <h3 class="empty-title">No hay partidos del Mundial en los próximos 7 días</h3>
        <p class="empty-text">El Mundial 2026 se disputa del 11 de junio al 19 de julio. Vuelve en una jornada activa para ver partidos aquí.</p>
      </div>
    `;
    return;
  }

  matches.forEach(match => {
    grid.appendChild(renderMatchCard(match));
  });
}

function updateStats(matches) {
  const totalMatches = matches.length;
  const valueBets = matches.filter(m => m.has_value).length;
  const bestEdge = matches.reduce((max, m) => {
    const edge = m.best_bet?.edge || 0;
    return edge > max ? edge : max;
  }, 0);
  
  const statMatches = document.getElementById('stat-matches');
  const statValueBets = document.getElementById('stat-valuebets');
  const statBestEdge = document.getElementById('stat-bestedge');
  
  if (statMatches) statMatches.textContent = totalMatches;
  if (statValueBets) statValueBets.textContent = valueBets;
  if (statBestEdge) statBestEdge.textContent = bestEdge > 0 ? `+${bestEdge.toFixed(1)}%` : '—';
  
  const countEl = document.getElementById('matches-count');
  if (countEl) countEl.textContent = totalMatches;
}

function updateStatusBadge() {
  const badge = document.getElementById('status-badge');
  const text = document.getElementById('status-text');
  if (!badge || !text) return;

  if (CONFIG.MOCK_MODE) {
    badge.classList.add('mock');
    text.textContent = 'Modo Demo';
  } else {
    badge.classList.remove('mock');
    text.textContent = 'En vivo';
  }
}

// ============================================================
// FILTERING
// ============================================================

function filterMatches(filter) {
  state.currentFilter = filter;
  
  // Update active tab
  document.querySelectorAll('.filter-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.filter === filter);
  });
  
  let filtered = [...state.matches];
  
  switch (filter) {
    case 'value':
      filtered = filtered.filter(m => m.has_value);
      break;
    case 'excellent':
      filtered = filtered.filter(m => m.best_bet?.classification?.level === 'excellent');
      break;
    case 'good':
      filtered = filtered.filter(m => m.best_bet?.classification?.level === 'good');
      break;
    case 'acceptable':
      filtered = filtered.filter(m => m.best_bet?.classification?.level === 'acceptable');
      break;
    default:
      // 'all' — no filter
      break;
  }
  
  renderMatches(filtered);
  
  const countEl = document.getElementById('matches-count');
  if (countEl) countEl.textContent = filtered.length;
}

// ============================================================
// RENDER: DETAIL PAGE
// ============================================================

function renderMatchDetail(data) {
  const match = data.match;
  const stats = data.stats;
  const ai = data.ai_analysis;
  const isPending = data.odds_pending || !match.markets || Object.keys(match.markets || {}).length === 0;

  if (!match) return;

  // Mostrar aviso si no hay cuotas
  if (isPending) {
    const notice = document.getElementById('pending-notice');
    if (notice) notice.style.display = 'flex';
  }
  
  // Header
  document.getElementById('home-flag').textContent = getFlag(match.home_team);
  document.getElementById('home-name').textContent = match.home_team;
  document.getElementById('away-flag').textContent = getFlag(match.away_team);
  document.getElementById('away-name').textContent = match.away_team;
  document.getElementById('detail-time').textContent = formatTime(match.commence_time);
  
  const comp = document.getElementById('detail-competition');
  if (comp) comp.textContent = match.sport === 'soccer_fifa_world_cup' ? 'FIFA World Cup 2026' : match.sport;

  // Etapa del partido (Grupo A, Octavos, etc.)
  const stageEl = document.getElementById('detail-stage');
  if (stageEl) {
    let stageText = '';
    if (match.group) stageText = `Grupo ${match.group}`;
    else if (match.stage === 'Round of 32') stageText = 'Dieciseisavos de Final';
    else if (match.stage === 'Round of 16') stageText = 'Octavos de Final';
    else if (match.stage === 'Quarter-finals') stageText = 'Cuartos de Final';
    else if (match.stage === 'Semi-finals') stageText = 'Semifinal';
    else if (match.stage === 'Final') stageText = 'Final';
    else if (match.stage) stageText = match.stage;

    if (match.venue) stageText += ` · ${match.venue}`;
    stageEl.textContent = stageText;
  }
  
  // Recommendation box
  const recContainer = document.getElementById('recommendation-container');
  if (match.has_value && match.best_bet && recContainer) {
    recContainer.style.display = 'block';
    
    const marketNames = { 'h2h': '1X2', 'totals': 'Over/Under', 'btts': 'BTTS' };
    document.getElementById('rec-market').textContent = marketNames[match.best_bet.market] || match.best_bet.market;
    document.getElementById('rec-selection').textContent = match.best_bet.outcome;
    document.getElementById('rec-odds').textContent = match.best_bet.odds.toFixed(2);
    document.getElementById('rec-edge').textContent = formatEdge(match.best_bet.edge);
    
    // Copy button
    const copyBtn = document.getElementById('copy-bet-btn');
    if (copyBtn) {
      copyBtn.onclick = () => {
        const text = `🎯 VALUE BET — ${match.home_team} vs ${match.away_team}\n` +
                     `📊 Mercado: ${marketNames[match.best_bet.market] || match.best_bet.market}\n` +
                     `✅ Selección: ${match.best_bet.outcome}\n` +
                     `💰 Cuota bet365: ${match.best_bet.odds.toFixed(2)}\n` +
                     `📈 Edge: ${formatEdge(match.best_bet.edge)}\n` +
                     `⏰ ${formatTime(match.commence_time)}`;
        
        navigator.clipboard.writeText(text).then(() => {
          copyBtn.textContent = '✅ Copiado!';
          copyBtn.classList.add('copied');
          showToast('Apuesta copiada al portapapeles');
          setTimeout(() => {
            copyBtn.textContent = '📋 Copiar Apuesta';
            copyBtn.classList.remove('copied');
          }, 2000);
        }).catch(() => {
          showToast('Error al copiar');
        });
      };
    }
  }
  
  // Markets
  const marketsContainer = document.getElementById('markets-container');
  if (marketsContainer && match.markets) {
    marketsContainer.innerHTML = '';
    
    for (const [marketKey, marketData] of Object.entries(match.markets)) {
      const marketCard = document.createElement('div');
      marketCard.className = 'market-card';
      
      let outcomesHtml = '';
      const outcomes = marketData.outcomes || [];
      
      outcomes.forEach(outcome => {
        const edgeWidth = Math.min(Math.abs(outcome.edge) * 5, 100);
        const isPositive = outcome.edge > 0;
        const hasValue = outcome.edge >= 3;
        
        outcomesHtml += `
          <div class="outcome-row ${hasValue ? 'has-value' : ''}">
            <div class="outcome-name">${outcome.name}</div>
            <div>
              <div class="outcome-odds-label">bet365</div>
              <div class="outcome-odds">${outcome.bet365_odds.toFixed(2)}</div>
            </div>
            <div>
              <div class="outcome-odds-label">Pinnacle</div>
              <div class="outcome-odds" style="color: var(--text-secondary)">${outcome.pinnacle_odds.toFixed(2)}</div>
            </div>
            <div class="outcome-edge-value ${isPositive ? 'positive' : 'negative'}">
              ${formatEdge(outcome.edge)}
            </div>
          </div>
        `;
      });
      
      marketCard.innerHTML = `
        <div class="market-title">${MARKET_NAMES[marketKey] || marketKey}</div>
        <div class="market-outcomes">${outcomesHtml}</div>
      `;
      
      marketsContainer.appendChild(marketCard);
    }
  }
  
  // AI Analysis
  if (ai) {
    const aiText = document.getElementById('ai-text');
    if (aiText) aiText.innerHTML = ai.analysis || 'No hay análisis disponible.';
    
    const aiFactors = document.getElementById('ai-factors');
    if (aiFactors && ai.key_factors) {
      aiFactors.innerHTML = ai.key_factors.map(f => 
        `<div class="ai-factor"><span class="bullet">▸</span>${f}</div>`
      ).join('');
    }
    
    // Toggle
    const toggleHeader = document.getElementById('ai-toggle-header');
    const aiBody = document.getElementById('ai-body');
    const toggleIcon = document.getElementById('ai-toggle-icon');
    
    if (toggleHeader && aiBody && toggleIcon) {
      // Start expanded
      aiBody.classList.add('visible');
      toggleIcon.classList.add('expanded');
      
      toggleHeader.onclick = () => {
        aiBody.classList.toggle('visible');
        toggleIcon.classList.toggle('expanded');
      };
    }
  }
  
  // Stats
  if (stats) {
    const statsGrid = document.getElementById('stats-grid');
    if (statsGrid) {
      statsGrid.innerHTML = '';
      
      const teams = [
        { name: match.home_team, data: stats.home },
        { name: match.away_team, data: stats.away }
      ];
      
      teams.forEach(team => {
        if (!team.data) return;
        
        const form = team.data.form || '';
        const formDots = form.split('').map(c => 
          `<div class="form-dot ${c}">${c}</div>`
        ).join('');
        
        const card = document.createElement('div');
        card.className = 'team-stats-card';
        card.innerHTML = `
          <div class="team-stats-header">
            <span>${getFlag(team.name)}</span>
            <span class="team-stats-name">${team.name}</span>
          </div>
          <div class="form-display">${formDots}</div>
          <div class="team-stat-row">
            <span class="team-stat-label">Goles/partido</span>
            <span class="team-stat-value">${team.data.goals_scored_avg}</span>
          </div>
          <div class="team-stat-row">
            <span class="team-stat-label">Goles en contra</span>
            <span class="team-stat-value">${team.data.goals_conceded_avg}</span>
          </div>
          <div class="team-stat-row">
            <span class="team-stat-label">Posesión</span>
            <span class="team-stat-value">${team.data.possession_avg}%</span>
          </div>
          <div class="team-stat-row">
            <span class="team-stat-label">Corners/partido</span>
            <span class="team-stat-value">${team.data.corners_avg}</span>
          </div>
          <div class="team-stat-row">
            <span class="team-stat-label">Tiros/partido</span>
            <span class="team-stat-value">${team.data.shots_avg}</span>
          </div>
          <div class="team-stat-row">
            <span class="team-stat-label">Portería a cero</span>
            <span class="team-stat-value">${team.data.clean_sheets_pct}%</span>
          </div>
          <div class="team-stat-row">
            <span class="team-stat-label">BTTS %</span>
            <span class="team-stat-value">${team.data.btts_pct}%</span>
          </div>
        `;
        statsGrid.appendChild(card);
      });
    }
    
    // Insights
    const insightsList = document.getElementById('insights-list');
    if (insightsList && stats.insights) {
      insightsList.innerHTML = stats.insights.map(insight => 
        `<div class="insight-item">${insight}</div>`
      ).join('');
    }
  }
  
  // Show content, hide loading
  document.getElementById('detail-loading').style.display = 'none';
  document.getElementById('detail-content').style.display = 'block';
}

// ============================================================
// INITIALIZATION
// ============================================================

async function initMainPage() {
  const grid = document.getElementById('matches-grid');
  if (!grid) return; // Not the main page

  // Mostrar skeletons mientras carga
  grid.innerHTML = `
    <div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div>
    <div class="skeleton skeleton-card"></div>
  `;

  try {
    state.matches = await fetchMatches();

    // Sort by commence time
    state.matches.sort((a, b) => new Date(a.commence_time) - new Date(b.commence_time));

    updateStats(state.matches);
    updateStatusBadge();
    renderMatches(state.matches);

    // Setup filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
      tab.addEventListener('click', () => filterMatches(tab.dataset.filter));
    });

    // Auto-refresh
    if (state.refreshTimer) clearInterval(state.refreshTimer);
    state.refreshTimer = setInterval(async () => {
      try {
        state.matches = await fetchMatches();
        state.matches.sort((a, b) => new Date(a.commence_time) - new Date(b.commence_time));
        updateStats(state.matches);
        filterMatches(state.currentFilter);
      } catch (err) {
        console.warn('[Refresh] Failed:', err.message);
      }
    }, CONFIG.REFRESH_INTERVAL);

  } catch (err) {
    console.error('[Init] Error:', err);
    grid.innerHTML = `
      <div class="error-state">
        <div class="error-icon">❌</div>
        <h3 class="error-title">No se pudo conectar con el servidor</h3>
        <p class="error-text">Error: ${err.message}</p>
        <p class="error-hint">Verifica tu conexión o inténtalo de nuevo en unos segundos.</p>
        <button class="retry-btn" onclick="initMainPage()">Reintentar</button>
      </div>
    `;
    // Mostrar como modo demo hasta que se reconecte
    CONFIG.MOCK_MODE = true;
    updateStatusBadge();
  }
}

async function loadMatchDetail() {
  const matchId = getMatchIdFromUrl();
  if (!matchId) {
    window.location.href = '/';
    return;
  }
  
  const loadingEl = document.getElementById('detail-loading');
  const contentEl = document.getElementById('detail-content');
  const errorEl = document.getElementById('detail-error');
  
  if (loadingEl) loadingEl.style.display = 'block';
  if (contentEl) contentEl.style.display = 'none';
  if (errorEl) errorEl.style.display = 'none';
  
  try {
    const data = await fetchMatchDetail(matchId);
    
    if (!data.success && !data.match) {
      throw new Error(data.error || 'Match not found');
    }
    
    state.matchDetail = data;
    renderMatchDetail(data);
    
    // Update page title
    const match = data.match;
    if (match) {
      document.title = `${match.home_team} vs ${match.away_team} — Value Bet Finder`;
    }
    
  } catch (err) {
    console.error('[Detail] Error:', err);
    if (loadingEl) loadingEl.style.display = 'none';
    if (errorEl) {
      errorEl.style.display = 'block';
      const errorMsg = document.getElementById('error-message');
      if (errorMsg) errorMsg.textContent = `Error: ${err.message}`;
    }
  }
}

async function initDetailPage() {
  const detailApp = document.getElementById('detail-app');
  if (!detailApp) return;
  
  await loadMatchDetail();
}

// ============================================================
// APP START
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  // Detect which page we're on
  const isDetail = !!document.getElementById('detail-app');
  const isMain = !!document.getElementById('matches-grid');
  
  if (isDetail) {
    state.isDetailPage = true;
    initDetailPage();
  } else if (isMain) {
    initMainPage();
  }
});
