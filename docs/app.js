// ── Firebase Configuration ──────────────────────────────────────────────────
const firebaseConfig = {
    apiKey: "AIzaSyCTxVnPDZOdw50hxynaBPgTJi3Uxnh_nS4",
    authDomain: "safenet-e969a.firebaseapp.com",
    databaseURL: "https://safenet-e969a-default-rtdb.europe-west1.firebasedatabase.app",
    projectId: "safenet-e969a",
    storageBucket: "safenet-e969a.firebasestorage.app",
    messagingSenderId: "67444032834",
    appId: "1:67444032834:web:7c817e8db571551a6eb4db",
    measurementId: "G-VS8F0627M5"
};

firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const database = firebase.database();

// ── State ───────────────────────────────────────────────────────────────────
let currentUser = null;
let isConnected = false;
let currentFilter = 'all';
let statusCache = {};
let allEventsCache = [];
let commandInProgress = {};
let lastSyncTime = Date.now();
let syncTimerInterval = null;

// ── UI Elements ─────────────────────────────────────────────────────────────
const authContainer = document.getElementById('auth-container');
const appContainer = document.getElementById('app-container');
const loginForm = document.getElementById('login-form');
const registerForm = document.getElementById('register-form');
const emailInput = document.getElementById('email');
const passwordInput = document.getElementById('password');
const registerEmailInput = document.getElementById('register-email');
const registerPasswordInput = document.getElementById('register-password');
const registerPasswordConfirmInput = document.getElementById('register-password-confirm');
const loginBtn = document.getElementById('login-btn');
const registerBtn = document.getElementById('register-btn');
const logoutBtn = document.getElementById('logout-btn');
const userEmailSpan = document.getElementById('user-email-text');
const eventsList = document.getElementById('events-list');
const syncSecondsDisplay = document.getElementById('sync-seconds');

// ── Auth Handlers ───────────────────────────────────────────────────────────
function toggleAuth(event) {
    event.preventDefault();
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    loginForm.classList.toggle('hidden');
    registerForm.classList.toggle('hidden');
}

loginBtn.addEventListener('click', async () => {
    const email = emailInput.value.trim();
    const password = passwordInput.value;

    if (!email || !password) {
        showError('login-error', 'Email and password are required');
        return;
    }

    try {
        loginBtn.disabled = true;
        await auth.signInWithEmailAndPassword(email, password);
        authContainer.classList.add('hidden');
        appContainer.classList.remove('hidden');
    } catch (error) {
        let message = 'Login error';
        if (error.code === 'auth/user-not-found') message = 'User not found';
        if (error.code === 'auth/wrong-password') message = 'Incorrect password';
        if (error.code === 'auth/invalid-email') message = 'Invalid email address';
        showError('login-error', message);
    } finally {
        loginBtn.disabled = false;
    }
});

registerBtn.addEventListener('click', async () => {
    const email = registerEmailInput.value.trim();
    const password = registerPasswordInput.value;
    const passwordConfirm = registerPasswordConfirmInput.value;

    if (!email || !password || !passwordConfirm) {
        showError('register-error', 'All fields are required');
        return;
    }

    if (password !== passwordConfirm) {
        showError('register-error', 'Passwords do not match');
        return;
    }

    if (password.length < 6) {
        showError('register-error', 'Password must be at least 6 characters');
        return;
    }

    try {
        registerBtn.disabled = true;
        await auth.createUserWithEmailAndPassword(email, password);
        authContainer.classList.add('hidden');
        appContainer.classList.remove('hidden');
    } catch (error) {
        let message = 'Registration error';
        if (error.code === 'auth/email-already-in-use') message = 'Email already in use';
        if (error.code === 'auth/invalid-email') message = 'Invalid email address';
        if (error.code === 'auth/weak-password') message = 'Password is too weak';
        showError('register-error', message);
    } finally {
        registerBtn.disabled = false;
    }
});

logoutBtn.addEventListener('click', async () => {
    await auth.signOut();
});

auth.onAuthStateChanged((user) => {
    currentUser = user;
    if (user) {
        userEmailSpan.textContent = user.email;
        authContainer.classList.add('hidden');
        appContainer.classList.remove('hidden');
        initializeApp();
    } else {
        authContainer.classList.remove('hidden');
        appContainer.classList.add('hidden');
        loginForm.classList.remove('hidden');
        registerForm.classList.add('hidden');
        emailInput.value = '';
        passwordInput.value = '';
        registerEmailInput.value = '';
        registerPasswordInput.value = '';
        registerPasswordConfirmInput.value = '';
    }
});

function showError(elementId, message) {
    const errorEl = document.getElementById(elementId);
    errorEl.textContent = message;
    errorEl.classList.add('show');
    setTimeout(() => {
        errorEl.classList.remove('show');
    }, 5000);
}

// ── Sync Timer ──────────────────────────────────────────────────────────────
function updateSyncTime() {
    lastSyncTime = Date.now();
}

function startSyncTimer() {
    if (syncTimerInterval) clearInterval(syncTimerInterval);

    syncTimerInterval = setInterval(() => {
        const secondsAgo = Math.floor((Date.now() - lastSyncTime) / 1000);
        if (syncSecondsDisplay) {
            syncSecondsDisplay.textContent = secondsAgo;
        }
    }, 1000);
}

// ── Firebase Listeners ──────────────────────────────────────────────────────
function setupFirebaseListeners() {
    if (!currentUser) return;

    // Status listener: drives all toggle and label updates
    database.ref('status').on('value', (snapshot) => {
        const status = snapshot.val();
        if (status) {
            statusCache = status;
            updateStatusDisplay();
            updateLastUpdate();
            updateSyncTime();
            isConnected = true;
        }
    });

    // Events listener: drives stats and timeline (no limit — counts are authoritative)
    database.ref('events').on('value', (snapshot) => {
        const eventsObj = snapshot.val();
        if (eventsObj) {
            allEventsCache = Object.values(eventsObj).sort((a, b) =>
                new Date(b.datetime) - new Date(a.datetime)
            );
        } else {
            allEventsCache = [];
        }
        displayEvents(allEventsCache);
        updateStats();
        updateSyncTime();
    });
}

// ── Status Display ──────────────────────────────────────────────────────────
// Single source of truth: always reads from statusCache (populated by Firebase listener).
// Called on every status update — overrides any local optimistic state.
function updateStatusDisplay() {
    if (!statusCache) return;

    const armed = statusCache.armed;
    const keyword = statusCache.keyword_spotting;
    const anomaly = statusCache.anomaly_detection;

    // System toggle
    document.getElementById('status-armed').textContent = armed ? 'ARMED' : 'DISARMED';
    document.getElementById('status-armed').className = `status-value ${armed ? 'armed' : 'disarmed'}`;
    document.getElementById('toggle-armed').checked = armed;

    // Keyword spotting
    document.getElementById('status-keyword').textContent = keyword ? 'ENABLED' : 'DISABLED';
    document.getElementById('status-keyword').className = `status-value ${keyword ? 'enabled' : 'disabled'}`;
    document.getElementById('toggle-keyword').checked = keyword;
    document.getElementById('toggle-keyword').disabled = !armed;
    document.getElementById('danger-signals-card').style.opacity = armed ? '1' : '0.5';

    // Anomaly detection
    document.getElementById('status-anomaly').textContent = anomaly ? 'ENABLED' : 'DISABLED';
    document.getElementById('status-anomaly').className = `status-value ${anomaly ? 'enabled' : 'disabled'}`;
    document.getElementById('toggle-anomaly').checked = anomaly;
    document.getElementById('toggle-anomaly').disabled = !armed;
    document.getElementById('anomaly-detection-card').style.opacity = armed ? '1' : '0.5';
}

// ── Stats ───────────────────────────────────────────────────────────────────
// Counts derived from Firebase events — no CSV dependency.
function updateStats() {
    document.getElementById('stat-total').textContent = allEventsCache.length;
    document.getElementById('stat-entries').textContent = allEventsCache.filter(e => e.direction === 'entry').length;
    document.getElementById('stat-exits').textContent = allEventsCache.filter(e => e.direction === 'exit').length;
    document.getElementById('stat-alarms').textContent = allEventsCache.filter(e => e.direction === 'alarm').length;
}

// ── Events Display ──────────────────────────────────────────────────────────
function displayEvents(events = []) {
    const filtered = currentFilter === 'all'
        ? events
        : events.filter(e => e.direction === currentFilter);

    if (!filtered || filtered.length === 0) {
        eventsList.innerHTML = '<p class="loading"><i class="fas fa-inbox"></i> No events</p>';
        return;
    }

    eventsList.innerHTML = filtered.slice(0, 50).map(event => createEventElement(event)).join('');
}

function createEventElement(event) {
    const dt = new Date(event.datetime);
    const time = dt.toLocaleTimeString();
    const direction = event.direction.toUpperCase();

    let icon = '📍';

    if (event.direction === 'entry') {
        icon = '<i class="fas fa-arrow-right" style="color: #10b981;"></i>';
    } else if (event.direction === 'exit') {
        icon = '<i class="fas fa-arrow-left" style="color: #f59e0b;"></i>';
    } else if (event.direction === 'alarm') {
        icon = '<i class="fas fa-bell" style="color: #ef4444;"></i>';
    }

    const anomalyScore = parseFloat(event.anomaly_score || 0);
    const anomalyHtml = anomalyScore > 0.5
        ? `<div class="event-anomaly"><i class="fas fa-exclamation-triangle"></i> Anomaly: ${anomalyScore.toFixed(2)}</div>`
        : '';

    return `
        <div class="event-item">
            <div class="event-icon">${icon}</div>
            <div class="event-details">
                <div class="event-time">${time}</div>
                <div class="event-direction">${direction}</div>
                ${anomalyHtml}
            </div>
        </div>
    `;
}

// ── Controls ────────────────────────────────────────────────────────────────
function sendCommand(toggleId, commandType, value) {
    const cmdId = Date.now().toString();
    const toggleElement = document.getElementById(toggleId);

    if (commandInProgress[commandType]) {
        console.log(`Command ${commandType} already in progress`);
        if (toggleElement) toggleElement.checked = !value;
        return;
    }

    commandInProgress[commandType] = true;
    if (toggleElement) toggleElement.disabled = true;

    database.ref(`commands/${cmdId}`).set({
        type: commandType,
        value: value,
        source: "dashboard",
        timestamp: new Date().toISOString(),
        status: "pending"
    });

    // Poll for Arduino acknowledgement; Firebase status listener will have
    // already updated the UI by the time this fires in most cases.
    let checkCount = 0;
    const checkInterval = setInterval(() => {
        checkCount++;
        database.ref(`commands/${cmdId}`).once('value', (snapshot) => {
            const cmd = snapshot.val();
            if (cmd && cmd.status !== "pending") {
                clearInterval(checkInterval);
                commandInProgress[commandType] = false;
                if (toggleElement) toggleElement.disabled = false;

                if (cmd.status === "failed") {
                    console.error(`Command failed: ${cmd.error}`);
                    if (toggleElement) toggleElement.checked = !value;
                }

                // Re-apply authoritative state from Firebase
                updateStatusDisplay();
            }
        });

        if (checkCount > 25) {
            clearInterval(checkInterval);
            commandInProgress[commandType] = false;
            if (toggleElement) toggleElement.disabled = false;
            console.warn(`Command ${commandType} timeout`);
            if (toggleElement) toggleElement.checked = !value;
        }
    }, 200);
}

function toggleArmed() {
    const armed = document.getElementById('toggle-armed').checked;
    sendCommand('toggle-armed', 'set_armed', armed);
    // Immediate optimistic visual feedback while waiting for Arduino round-trip
    applyArmedVisuals(armed);
}

// Applies immediate visual state for armed/disarmed without waiting for Firebase.
// updateStatusDisplay() will correct this with authoritative state on next sync.
function applyArmedVisuals(armed) {
    const keywordToggle = document.getElementById('toggle-keyword');
    const anomalyToggle = document.getElementById('toggle-anomaly');

    document.getElementById('status-armed').textContent = armed ? 'ARMED' : 'DISARMED';
    document.getElementById('status-armed').className = `status-value ${armed ? 'armed' : 'disarmed'}`;

    keywordToggle.disabled = !armed;
    anomalyToggle.disabled = !armed;
    document.getElementById('danger-signals-card').style.opacity = armed ? '1' : '0.5';
    document.getElementById('anomaly-detection-card').style.opacity = armed ? '1' : '0.5';

    if (armed) {
        // Optimistic: system ON re-enables both features (Arduino will confirm)
        keywordToggle.checked = true;
        anomalyToggle.checked = true;
        document.getElementById('status-keyword').textContent = 'ENABLED';
        document.getElementById('status-keyword').className = 'status-value enabled';
        document.getElementById('status-anomaly').textContent = 'ENABLED';
        document.getElementById('status-anomaly').className = 'status-value enabled';
    } else {
        keywordToggle.checked = false;
        anomalyToggle.checked = false;
        document.getElementById('status-keyword').textContent = 'DISABLED';
        document.getElementById('status-keyword').className = 'status-value disabled';
        document.getElementById('status-anomaly').textContent = 'DISABLED';
        document.getElementById('status-anomaly').className = 'status-value disabled';
    }
}

function toggleKeywordSpotting() {
    const enabled = document.getElementById('toggle-keyword').checked;
    sendCommand('toggle-keyword', 'set_keyword_spotting', enabled);
}

function toggleAnomalyDetection() {
    const enabled = document.getElementById('toggle-anomaly').checked;
    sendCommand('toggle-anomaly', 'set_anomaly_detection', enabled);
}

function filterEvents(type) {
    currentFilter = type;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    displayEvents(allEventsCache);
}

function updateLastUpdate() {
    if (statusCache && statusCache.last_update) {
        const date = new Date(statusCache.last_update);
        document.getElementById('last-update').textContent = date.toLocaleTimeString();
    }
}

// ── Initialize App ──────────────────────────────────────────────────────────
function initializeApp() {
    if (!currentUser) return;
    setupFirebaseListeners();
    startSyncTimer();
}

// ── On Load ─────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
    if (currentUser) {
        initializeApp();
    }
});
