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
let absenceCache = null;
let commandInProgress = {};
let lastSyncTime = Date.now();
let syncTimerInterval = null;
let clockInterval = null;
const sliderWriteTimers = {};

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
const timelineEl = document.getElementById('timeline');
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

    // Events listener: drives stats and timeline
    database.ref('events').on('value', (snapshot) => {
        const eventsObj = snapshot.val();
        if (eventsObj) {
            allEventsCache = Object.values(eventsObj).sort((a, b) =>
                new Date(a.datetime) - new Date(b.datetime)
            );
        } else {
            allEventsCache = [];
        }
        displayEvents(allEventsCache);
        updateStats();
        updateSyncTime();
    });

    // Absence listener: drives the live clock card
    database.ref('monitoring/absence').on('value', (snapshot) => {
        absenceCache = snapshot.val();
        renderAbsence();
        updateSyncTime();
    });

    // Model status listener
    database.ref('model/status').on('value', (snapshot) => {
        updateModelStatus(snapshot.val());
    });

    // Config listener: keeps sliders in sync (authoritative from Firebase)
    database.ref('config/anomaly').on('value', (snapshot) => {
        updateSlidersFromConfig(snapshot.val());
    });
}

// ── Status Display ──────────────────────────────────────────────────────────
// Single source of truth: always reads from statusCache (Firebase listener).
function updateStatusDisplay() {
    if (!statusCache) return;

    const armed = statusCache.armed;
    const keyword = statusCache.keyword_spotting;
    const anomaly = statusCache.anomaly_detection;

    document.getElementById('status-armed').textContent = armed ? 'ARMED' : 'DISARMED';
    document.getElementById('status-armed').className = `status-value ${armed ? 'armed' : 'disarmed'}`;
    document.getElementById('toggle-armed').checked = armed;

    document.getElementById('status-keyword').textContent = keyword ? 'ENABLED' : 'DISABLED';
    document.getElementById('status-keyword').className = `status-value ${keyword ? 'enabled' : 'disabled'}`;
    document.getElementById('toggle-keyword').checked = keyword;
    document.getElementById('toggle-keyword').disabled = !armed;
    document.getElementById('danger-signals-card').style.opacity = armed ? '1' : '0.5';

    document.getElementById('status-anomaly').textContent = anomaly ? 'ENABLED' : 'DISABLED';
    document.getElementById('status-anomaly').className = `status-value ${anomaly ? 'enabled' : 'disabled'}`;
    document.getElementById('toggle-anomaly').checked = anomaly;
    document.getElementById('toggle-anomaly').disabled = !armed;
    document.getElementById('anomaly-detection-card').style.opacity = armed ? '1' : '0.5';
}

// ── Stats ───────────────────────────────────────────────────────────────────
function updateStats() {
    document.getElementById('stat-total').textContent = allEventsCache.length;
    document.getElementById('stat-entries').textContent = allEventsCache.filter(e => e.direction === 'entry').length;
    document.getElementById('stat-exits').textContent = allEventsCache.filter(e => e.direction === 'exit').length;
    document.getElementById('stat-alarms').textContent =
        allEventsCache.filter(e => e.direction === 'alarm' || e.direction === 'anomaly').length;
}

// ── Horizontal Event Timeline ───────────────────────────────────────────────
function displayEvents(events = []) {
    const filtered = currentFilter === 'all'
        ? events
        : events.filter(e => e.direction === currentFilter);

    if (!filtered || filtered.length === 0) {
        timelineEl.innerHTML = '<p class="loading"><i class="fas fa-inbox"></i> No events</p>';
        return;
    }

    // Keep the most recent 50, rendered oldest -> newest (left -> right).
    const recent = filtered.slice(-50);
    timelineEl.innerHTML = recent.map(createTimelineNode).join('');

    // Auto-scroll to the newest event on the right.
    timelineEl.scrollLeft = timelineEl.scrollWidth;
}

function createTimelineNode(event) {
    const dt = new Date(event.datetime);
    const time = dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const day = dt.toLocaleDateString([], { day: '2-digit', month: '2-digit' });

    let icon = '<i class="fas fa-location-dot"></i>';
    let typeClass = '';
    let label = event.direction.toUpperCase();

    if (event.direction === 'entry') {
        icon = '<i class="fas fa-arrow-right-to-bracket"></i>';
        typeClass = 'entry';
        label = 'ENTRY';
    } else if (event.direction === 'exit') {
        icon = '<i class="fas fa-arrow-right-from-bracket"></i>';
        typeClass = 'exit';
        label = 'EXIT';
    } else if (event.direction === 'alarm') {
        icon = '<i class="fas fa-bell"></i>';
        typeClass = 'alarm';
        label = 'ALARM';
    } else if (event.direction === 'anomaly') {
        icon = '<i class="fas fa-brain"></i>';
        typeClass = 'anomaly';
        label = event.anomaly_type === 'ABSENCE_OVERDUE' ? 'OVERDUE' : 'UNUSUAL';
    }

    return `
        <div class="tl-node ${typeClass}">
            <div class="tl-dot">${icon}</div>
            <div class="tl-time">${time}</div>
            <div class="tl-label">${label}</div>
            <div class="tl-day">${day}</div>
        </div>
    `;
}

// ── Active Absence Card + Live Clock ────────────────────────────────────────
function renderAbsence() {
    const section = document.getElementById('absence-section');

    if (!absenceCache || !absenceCache.active) {
        section.classList.add('hidden');
        return;
    }

    section.classList.remove('hidden');

    const exitDt = new Date(absenceCache.exit_time);
    document.getElementById('absence-exit-time').textContent =
        exitDt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const ws = new Date(absenceCache.window_start);
    const we = new Date(absenceCache.window_end);
    const fmt = (d) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById('absence-expected-window').textContent = `${fmt(ws)} - ${fmt(we)}`;

    const deadline = new Date(absenceCache.late_deadline_at);
    document.getElementById('absence-deadline').textContent = fmt(deadline);

    const confidenceEl = document.getElementById('absence-confidence');
    confidenceEl.classList.toggle('hidden', absenceCache.confidence !== 'low');

    const badge = document.getElementById('absence-status-badge');
    const status = absenceCache.status || 'out';
    badge.textContent = status.toUpperCase();
    badge.className = `absence-status-badge ${status}`;

    const dismissBtn = document.getElementById('absence-dismiss-btn');
    dismissBtn.classList.toggle('hidden', status === 'dismissed');

    tickClock();
}

function tickClock() {
    if (!absenceCache || !absenceCache.active) return;

    const exitDt = new Date(absenceCache.exit_time);
    const deadline = new Date(absenceCache.late_deadline_at);
    const expected = new Date(absenceCache.expected_return_at);
    const now = new Date();

    // Elapsed time since exit (counts up).
    const elapsedMs = Math.max(0, now - exitDt);
    document.getElementById('absence-clock').textContent = formatDuration(elapsedMs);

    // Progress from exit (0%) to deadline (100%).
    const totalMs = deadline - exitDt;
    const pct = totalMs > 0 ? Math.min(100, Math.max(0, ((now - exitDt) / totalMs) * 100)) : 100;
    const bar = document.getElementById('absence-progress-bar');
    bar.style.width = `${pct}%`;

    // Expected-return marker position.
    const expPct = totalMs > 0 ? Math.min(100, Math.max(0, ((expected - exitDt) / totalMs) * 100)) : 100;
    document.getElementById('absence-progress-expected').style.left = `${expPct}%`;

    // Color the card by urgency, unless dismissed.
    const card = document.getElementById('absence-card');
    if (absenceCache.status === 'dismissed') {
        card.className = 'absence-card dismissed';
    } else if (now >= deadline) {
        card.className = 'absence-card overdue';
    } else if (pct >= 80) {
        card.className = 'absence-card approaching';
    } else {
        card.className = 'absence-card out';
    }
}

function formatDuration(ms) {
    const totalSec = Math.floor(ms / 1000);
    const h = String(Math.floor(totalSec / 3600)).padStart(2, '0');
    const m = String(Math.floor((totalSec % 3600) / 60)).padStart(2, '0');
    const s = String(totalSec % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
}

// ── Anomaly Config Sliders ──────────────────────────────────────────────────
function onSliderInput(which) {
    const id = which === 'unusual' ? 'slider-unusual-time' : 'slider-return-late';
    const valueId = which === 'unusual' ? 'slider-unusual-time-value' : 'slider-return-late-value';
    const key = which === 'unusual' ? 'unusual_time_sensitivity' : 'return_late_sensitivity';

    const value = parseInt(document.getElementById(id).value, 10);
    document.getElementById(valueId).textContent = value;

    // Debounce writes so dragging the slider does not spam Firebase.
    if (sliderWriteTimers[key]) clearTimeout(sliderWriteTimers[key]);
    sliderWriteTimers[key] = setTimeout(() => {
        database.ref('config/anomaly').update({ [key]: value });
    }, 400);
}

function updateSlidersFromConfig(config) {
    if (!config) return;

    const unusual = document.getElementById('slider-unusual-time');
    const ret = document.getElementById('slider-return-late');

    // Do not fight the user while they are actively dragging a slider.
    if (config.unusual_time_sensitivity != null && document.activeElement !== unusual) {
        unusual.value = config.unusual_time_sensitivity;
        document.getElementById('slider-unusual-time-value').textContent = config.unusual_time_sensitivity;
    }
    if (config.return_late_sensitivity != null && document.activeElement !== ret) {
        ret.value = config.return_late_sensitivity;
        document.getElementById('slider-return-late-value').textContent = config.return_late_sensitivity;
    }
}

// ── Model Status ────────────────────────────────────────────────────────────
function updateModelStatus(status) {
    const el = document.getElementById('model-status-text');
    if (!status) {
        el.innerHTML = '<i class="fas fa-circle-nodes"></i> Model status unavailable';
        return;
    }

    const trained = status.last_trained_at
        ? new Date(status.last_trained_at).toLocaleString([], { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
        : 'never';

    el.innerHTML = `<i class="fas fa-circle-nodes"></i> Last trained: <strong>${trained}</strong> ` +
        `&middot; ${status.training_samples || 0} samples ` +
        `(real ${status.real_events_in_window || 0}, synthetic ${status.synthetic_in_window || 0}) ` +
        `&middot; window ${status.training_window_days || 0}d`;
}

// ── Command Helpers ─────────────────────────────────────────────────────────
function sendCommandAwait(commandType, value, timeoutMs = 30000) {
    return new Promise((resolve) => {
        const cmdId = Date.now().toString();
        database.ref(`commands/${cmdId}`).set({
            type: commandType,
            value: value,
            source: "dashboard",
            timestamp: new Date().toISOString(),
            status: "pending"
        });

        const start = Date.now();
        const interval = setInterval(() => {
            database.ref(`commands/${cmdId}`).once('value', (snapshot) => {
                const cmd = snapshot.val();
                if (cmd && cmd.status !== "pending" && cmd.status !== "executing") {
                    clearInterval(interval);
                    resolve(cmd);
                }
            });
            if (Date.now() - start > timeoutMs) {
                clearInterval(interval);
                resolve({ status: "timeout", response: "No response from device" });
            }
        }, 300);
    });
}

async function retrainModel() {
    const btn = document.getElementById('retrain-btn');
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-rotate fa-spin"></i> Retraining...';

    const cmd = await sendCommandAwait('retrain_model', true);

    if (cmd.status === 'completed') {
        btn.innerHTML = '<i class="fas fa-check"></i> Done';
    } else {
        btn.innerHTML = '<i class="fas fa-triangle-exclamation"></i> Failed';
        console.error('Retrain:', cmd.response);
    }
    setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = original;
    }, 2500);
}

async function dismissAbsence() {
    const btn = document.getElementById('absence-dismiss-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-hourglass-half"></i> Dismissing...';

    await sendCommandAwait('dismiss_absence', true);

    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-bell-slash"></i> Dismiss alert';
}

// ── System Controls (existing) ──────────────────────────────────────────────
function sendCommand(toggleId, commandType, value) {
    const cmdId = Date.now().toString();
    const toggleElement = document.getElementById(toggleId);

    if (commandInProgress[commandType]) {
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
                updateStatusDisplay();
            }
        });

        if (checkCount > 25) {
            clearInterval(checkInterval);
            commandInProgress[commandType] = false;
            if (toggleElement) toggleElement.disabled = false;
            if (toggleElement) toggleElement.checked = !value;
        }
    }, 200);
}

function toggleArmed() {
    const armed = document.getElementById('toggle-armed').checked;
    sendCommand('toggle-armed', 'set_armed', armed);
    applyArmedVisuals(armed);
}

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

    // Live clock tick (independent of Firebase pushes).
    if (clockInterval) clearInterval(clockInterval);
    clockInterval = setInterval(tickClock, 1000);
}

// ── On Load ─────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
    if (currentUser) {
        initializeApp();
    }
});
