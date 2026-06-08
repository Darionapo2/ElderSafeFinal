// Firebase Configuration
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

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let currentUser = null;
let isConnected = false;
let currentFilter = 'all';
let statusCache = {};
let commandInProgress = {};

// Timer state
let timerInterval = null;
let timerSeconds = 0;
let lastExitTime = null;
let lastEntryTime = null;
let isAwayFromHome = false;
const ALERT_THRESHOLD_MS = 2 * 60 * 60 * 1000; // 2 hours

// ============================================================================
// UI ELEMENTS
// ============================================================================

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
const userEmailSpan = document.getElementById('user-email');
const eventsList = document.getElementById('events-list');
const connectionStatus = document.getElementById('connection-status');

// ============================================================================
// AUTHENTICATION HANDLERS
// ============================================================================

function toggleAuth(event) {
    event.preventDefault();
    loginForm.classList.toggle('active');
    registerForm.classList.toggle('active');
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
        if (error.code === 'auth/wrong-password') message = 'Wrong password';
        if (error.code === 'auth/invalid-email') message = 'Invalid email';
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
        if (error.code === 'auth/email-already-in-use') message = 'Email already registered';
        if (error.code === 'auth/invalid-email') message = 'Invalid email';
        if (error.code === 'auth/weak-password') message = 'Password too weak';
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
        loginForm.classList.add('active');
        registerForm.classList.remove('active');
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

// ============================================================================
// TIMER FUNCTIONS
// ============================================================================

function formatTime(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function updateTimerDisplay() {
    document.getElementById('timer-display').textContent = formatTime(timerSeconds);

    // Update timer status
    const statusEl = document.getElementById('timer-status');
    const alertEl = document.getElementById('timer-alert');

    if (isAwayFromHome) {
        statusEl.textContent = 'Away from Home';
        statusEl.classList.add('away');

        // Check alert threshold (2 hours)
        if (timerSeconds > ALERT_THRESHOLD_MS / 1000) {
            alertEl.classList.add('show');
        } else {
            alertEl.classList.remove('show');
        }
    } else {
        statusEl.textContent = 'At Home';
        statusEl.classList.remove('away');
        alertEl.classList.remove('show');
    }
}

function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerSeconds = 0;
    lastExitTime = new Date().toLocaleTimeString();
    isAwayFromHome = true;

    timerInterval = setInterval(() => {
        timerSeconds++;
        updateTimerDisplay();
    }, 1000);

    updateTimerDisplay();
}

function stopTimer() {
    if (timerInterval) clearInterval(timerInterval);
    lastEntryTime = new Date().toLocaleTimeString();
    isAwayFromHome = false;
    timerSeconds = 0;
    updateTimerDisplay();
}

function updateTimerInfo() {
    const exitEl = document.getElementById('last-exit-time');
    const entryEl = document.getElementById('last-entry-time');

    if (lastExitTime) exitEl.textContent = lastExitTime;
    if (lastEntryTime) entryEl.textContent = lastEntryTime;
}

// ============================================================================
// FIREBASE LISTENERS
// ============================================================================

function setupFirebaseListeners() {
    if (!currentUser) return;

    // Update connection status
    database.ref('.info/connected').on('value', (snapshot) => {
        isConnected = snapshot.val() === true;
        updateConnectionStatus();
    });

    // Listen to status updates
    database.ref('status').on('value', (snapshot) => {
        const status = snapshot.val();
        if (status) {
            statusCache = status;
            updateStatusDisplay();
            updateStats();
            updateLastUpdate();
            updateTogglesFromStatus();
            isConnected = true;
            updateConnectionStatus();
        }
    });

    // Listen to events updates
    database.ref('events').limitToLast(100).on('value', (snapshot) => {
        const eventsObj = snapshot.val();
        if (eventsObj) {
            const events = Object.values(eventsObj).sort((a, b) =>
                new Date(b.timestamp) - new Date(a.timestamp)
            );

            // Handle timer based on last event
            const lastEvent = events[0];
            if (lastEvent) {
                if (lastEvent.direction === 'exit') {
                    startTimer();
                } else if (lastEvent.direction === 'entry') {
                    stopTimer();
                }
            }

            displayEvents(events);
        }
    });
}

function updateConnectionStatus() {
    const statusEl = document.querySelector('.connection-status span');
    const statusDot = document.querySelector('.status-dot');

    if (isConnected) {
        statusEl.textContent = 'Connected';
        statusDot.classList.add('connected');
    } else {
        statusEl.textContent = 'Disconnected';
        statusDot.classList.remove('connected');
    }
}

function updateTogglesFromStatus() {
    if (!statusCache) return;
    if (Object.keys(commandInProgress).length === 0) {
        document.getElementById('toggle-armed').checked = statusCache.armed;
        document.getElementById('toggle-keyword').checked = statusCache.keyword_spotting;
        document.getElementById('toggle-sound').checked = statusCache.sound_classification;
        document.getElementById('toggle-anomaly').checked = statusCache.anomaly_detection;
    }
}

function updateStatusDisplay() {
    const armed = statusCache.armed ? 'Armed' : 'Disarmed';
    const armedClass = statusCache.armed ? 'armed' : 'disarmed';
    document.getElementById('status-armed').textContent = armed;
    document.getElementById('status-armed').className = `status-value ${armedClass}`;

    const statuses = {
        'status-keyword': statusCache.keyword_spotting,
        'status-sound': statusCache.sound_classification,
        'status-anomaly': statusCache.anomaly_detection,
    };

    for (const [id, enabled] of Object.entries(statuses)) {
        const text = enabled ? 'Enabled' : 'Disabled';
        const className = enabled ? 'enabled' : 'disabled';
        document.getElementById(id).textContent = text;
        document.getElementById(id).className = `status-value ${className}`;
    }
}

function updateStats() {
    document.getElementById('stat-total').textContent = statusCache.total_events || 0;
    document.getElementById('stat-entries').textContent = statusCache.entries || 0;
    document.getElementById('stat-exits').textContent = statusCache.exits || 0;
    document.getElementById('stat-alarms').textContent = statusCache.alarms || 0;
}

function displayEvents(events = []) {
    const filtered = currentFilter === 'all'
        ? events
        : events.filter(e => e.direction === currentFilter);

    if (!filtered || filtered.length === 0) {
        eventsList.innerHTML = '<p class="loading"><i class="fas fa-inbox"></i> No events</p>';
        return;
    }

    eventsList.innerHTML = filtered.map(event => createEventElement(event)).join('');
}

function createEventElement(event) {
    const dt = new Date(event.timestamp);
    const time = dt.toLocaleTimeString();
    const direction = event.direction.charAt(0).toUpperCase() + event.direction.slice(1);

    let icon = '📍';
    let bgClass = '';

    if (event.direction === 'entry') {
        icon = '<i class="fas fa-arrow-right" style="color: #10b981;"></i>';
        bgClass = 'entry';
    } else if (event.direction === 'exit') {
        icon = '<i class="fas fa-arrow-left" style="color: #f59e0b;"></i>';
        bgClass = 'exit';
    } else if (event.direction === 'alarm') {
        icon = '<i class="fas fa-bell" style="color: #ef4444;"></i>';
        bgClass = 'alarm';
    }

    const anomalyScore = parseFloat(event.anomaly_score || 0);
    const anomalyHtml = anomalyScore > 0.5
        ? `<div class="event-anomaly"><i class="fas fa-exclamation-triangle"></i> Anomaly: ${anomalyScore.toFixed(2)}</div>`
        : '';

    return `
        <div class="event-item ${bgClass}">
            <div class="event-icon">${icon}</div>
            <div class="event-details">
                <div class="event-time">${time}</div>
                <div class="event-direction">${direction}</div>
                ${anomalyHtml}
            </div>
        </div>
    `;
}

// ============================================================================
// CONTROL FUNCTIONS
// ============================================================================

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
                    if (toggleElement) toggleElement.checked = !value;
                }

                updateTogglesFromStatus();
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
}

function toggleKeywordSpotting() {
    const enabled = document.getElementById('toggle-keyword').checked;
    sendCommand('toggle-keyword', 'set_keyword_spotting', enabled);
}

function toggleSoundClassification() {
    const enabled = document.getElementById('toggle-sound').checked;
    sendCommand('toggle-sound', 'set_sound_classification', enabled);
}

function toggleAnomalyDetection() {
    const enabled = document.getElementById('toggle-anomaly').checked;
    sendCommand('toggle-anomaly', 'set_anomaly_detection', enabled);
}

function filterEvents(type) {
    currentFilter = type;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    database.ref('events').limitToLast(100).once('value', (snapshot) => {
        const eventsObj = snapshot.val();
        if (eventsObj) {
            const events = Object.values(eventsObj).sort((a, b) =>
                new Date(b.timestamp) - new Date(a.timestamp)
            );
            displayEvents(events);
        }
    });
}

function updateLastUpdate() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString();
}

// ============================================================================
// INITIALIZATION
// ============================================================================

function initializeApp() {
    if (!currentUser) return;
    setupFirebaseListeners();
    setTimeout(() => {
        updateTogglesFromStatus();
        updateTimerInfo();
    }, 1000);
}

window.addEventListener('load', () => {
    if (currentUser) {
        initializeApp();
    }
});
