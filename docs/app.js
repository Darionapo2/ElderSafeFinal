// ── Firebase Configuration ──────────────────────────────────────────────────
// TODO: Replace with your Firebase config from Firebase Console
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
let commandInProgress = {};

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
const userEmailSpan = document.getElementById('user-email');
const eventsList = document.getElementById('events-list');

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
        showError('login-error', 'Email e password sono obbligatori');
        return;
    }

    try {
        loginBtn.disabled = true;
        await auth.signInWithEmailAndPassword(email, password);
        authContainer.classList.add('hidden');
        appContainer.classList.remove('hidden');
    } catch (error) {
        let message = 'Errore di login';
        if (error.code === 'auth/user-not-found') message = 'Utente non trovato';
        if (error.code === 'auth/wrong-password') message = 'Password errata';
        if (error.code === 'auth/invalid-email') message = 'Email non valida';
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
        showError('register-error', 'Tutti i campi sono obbligatori');
        return;
    }

    if (password !== passwordConfirm) {
        showError('register-error', 'Le password non coincidono');
        return;
    }

    if (password.length < 6) {
        showError('register-error', 'La password deve avere almeno 6 caratteri');
        return;
    }

    try {
        registerBtn.disabled = true;
        await auth.createUserWithEmailAndPassword(email, password);
        authContainer.classList.add('hidden');
        appContainer.classList.remove('hidden');
    } catch (error) {
        let message = 'Errore di registrazione';
        if (error.code === 'auth/email-already-in-use') message = 'Email già registrata';
        if (error.code === 'auth/invalid-email') message = 'Email non valida';
        if (error.code === 'auth/weak-password') message = 'Password troppo debole';
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

// ── Firebase Listeners ──────────────────────────────────────────────────────
function setupFirebaseListeners() {
    // Listen to Firebase for real-time updates
    if (!currentUser) return;

    // Listen to status updates
    database.ref('status').on('value', (snapshot) => {
        const status = snapshot.val();
        if (status) {
            statusCache = status;
            updateStatusDisplay();
            updateStats();
            updateLastUpdate();
            updateTogglesFromStatus();  // Sync toggles without sending new commands
            isConnected = true;
        }
    });

    // Listen to events updates
    database.ref('events').limitToLast(100).on('value', (snapshot) => {
        const eventsObj = snapshot.val();
        if (eventsObj) {
            const events = Object.values(eventsObj).sort((a, b) =>
                new Date(b.datetime) - new Date(a.datetime)
            );
            displayEvents(events);
        }
    });
}

function updateTogglesFromStatus() {
    // Update toggle UI from statusCache
    // But DO NOT resync while a command is in progress
    if (!statusCache) return;

    // Only sync if no command is in progress
    if (Object.keys(commandInProgress).length === 0) {
        document.getElementById('toggle-armed').checked = statusCache.armed;
        document.getElementById('toggle-keyword').checked = statusCache.keyword_spotting;
        document.getElementById('toggle-anomaly').checked = statusCache.anomaly_detection;
    }
}

function updateStatusDisplay() {
    const armed = statusCache.armed ? 'ATTIVO' : 'DISATTIVATO';
    const armedClass = statusCache.armed ? 'armed' : 'disarmed';
    document.getElementById('status-armed').textContent = armed;
    document.getElementById('status-armed').className = `status-value ${armedClass}`;

    const statuses = {
        'status-keyword': statusCache.keyword_spotting,
        'status-sound': statusCache.sound_classification,
        'status-anomaly': statusCache.anomaly_detection,
    };

    for (const [id, enabled] of Object.entries(statuses)) {
        const text = enabled ? 'ABILITATO' : 'DISABILITATO';
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
    // Display filtered events in UI
    const filtered = currentFilter === 'all'
        ? events
        : events.filter(e => e.direction === currentFilter);

    if (!filtered || filtered.length === 0) {
        eventsList.innerHTML = '<p class="loading">Nessun evento</p>';
        return;
    }

    eventsList.innerHTML = filtered.map(event => createEventElement(event)).join('');
}

function createEventElement(event) {
    const dt = new Date(event.datetime);
    const time = dt.toLocaleTimeString('it-IT');
    const direction = event.direction.toUpperCase();

    let icon = '📍';
    let bgClass = '';

    if (event.direction === 'entry') {
        icon = '📥';
        bgClass = 'entry';
    } else if (event.direction === 'exit') {
        icon = '📤';
        bgClass = 'exit';
    } else if (event.direction === 'alarm') {
        icon = '🚨';
        bgClass = 'alarm';
    }

    const anomalyScore = parseFloat(event.anomaly_score || 0);
    const anomalyHtml = anomalyScore > 0.5 ? `<div class="event-anomaly">⚠️ Anomalia: ${anomalyScore.toFixed(2)}</div>` : '';

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
    // Send command to Arduino via Firebase
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

    // Wait for response (max 5 seconds)
    let checkCount = 0;
    const checkInterval = setInterval(() => {
        checkCount++;
        database.ref(`commands/${cmdId}`).once('value', (snapshot) => {
            const cmd = snapshot.val();
            if (cmd && cmd.status !== "pending") {
                clearInterval(checkInterval);
                commandInProgress[commandType] = false;
                if (toggleElement) toggleElement.disabled = false;

                if (cmd.status === "completed") {
                    console.log(`✓ ${cmd.response}`);
                } else if (cmd.status === "failed") {
                    console.error(`✗ ${cmd.error}`);
                    if (toggleElement) toggleElement.checked = !value;
                }

                // Re-sync status from Firebase
                updateTogglesFromStatus();
            }
        });

        if (checkCount > 25) {  // 5 seconds timeout (25 * 200ms)
            clearInterval(checkInterval);
            commandInProgress[commandType] = false;
            if (toggleElement) toggleElement.disabled = false;
            console.warn(`⏱️ Command ${commandType} timeout`);
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

function toggleAnomalyDetection() {
    const enabled = document.getElementById('toggle-anomaly').checked;
    sendCommand('toggle-anomaly', 'set_anomaly_detection', enabled);
}

function filterEvents(type) {
    currentFilter = type;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    // Get current events from Firebase and filter
    database.ref('events').limitToLast(100).once('value', (snapshot) => {
        const eventsObj = snapshot.val();
        if (eventsObj) {
            const events = Object.values(eventsObj).sort((a, b) =>
                new Date(b.datetime) - new Date(a.datetime)
            );
            displayEvents(events);
        }
    });
}

function updateLastUpdate() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString('it-IT');
}

// ── Initialize App ──────────────────────────────────────────────────────────
function initializeApp() {
    if (!currentUser) return;

    // Setup real-time Firebase listeners
    setupFirebaseListeners();

    // Update toggles from current status
    setTimeout(() => {
        updateTogglesFromStatus();
    }, 1000);
}

// ── On Load ─────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
    // Check if user is already logged in
    if (currentUser) {
        initializeApp();
    }
});
