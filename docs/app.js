// ── Firebase Configuration ──────────────────────────────────────────────────
// TODO: Replace with your Firebase config from Firebase Console
const firebaseConfig = {
    apiKey: "YOUR_API_KEY",
    authDomain: "your-project.firebaseapp.com",
    databaseURL: "https://your-project.firebaseio.com",
    projectId: "your-project-id",
    storageBucket: "your-project.appspot.com",
    messagingSenderId: "your-messaging-sender-id",
    appId: "your-app-id"
};

firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();
const database = firebase.database();

// ── State ───────────────────────────────────────────────────────────────────
let currentUser = null;
let arduinoIp = localStorage.getItem('arduinoIp') || 'localhost';
let arduinoPort = localStorage.getItem('arduinoPort') || '8000';
let isConnected = false;
let currentFilter = 'all';
let statusCache = {};

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
const arduinoIpInput = document.getElementById('arduino-ip');
const arduinoPortInput = document.getElementById('arduino-port');
const connectionStatus = document.getElementById('connection-status');
const eventsList = document.getElementById('events-list');

// ── Auth Handlers ───────────────────────────────────────────────────────────
function toggleAuth(event) {
    event.preventDefault();
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

// ── Arduino Connection ──────────────────────────────────────────────────────
function getArduinoUrl() {
    return `http://${arduinoIp}:${arduinoPort}`;
}

async function testConnection() {
    const ip = arduinoIpInput.value.trim();
    const port = arduinoPortInput.value.trim();

    if (!ip || !port) {
        showError('connection-status', 'IP e porta sono obbligatori');
        return;
    }

    arduinoIp = ip;
    arduinoPort = port;
    localStorage.setItem('arduinoIp', ip);
    localStorage.setItem('arduinoPort', port);

    try {
        const response = await fetch(`${getArduinoUrl()}/api/health`, { mode: 'cors' });
        if (response.ok) {
            connectionStatus.className = 'connection-status connected';
            connectionStatus.textContent = '✓ Connesso';
            isConnected = true;
            loadStatus();
            loadEvents();
        }
    } catch (error) {
        connectionStatus.className = 'connection-status disconnected';
        connectionStatus.textContent = '✗ Disconnesso';
        isConnected = false;
    }
}

// ── API Calls ───────────────────────────────────────────────────────────────
async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = {
            method,
            mode: 'cors',
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (body) {
            options.body = JSON.stringify(body);
        }

        const response = await fetch(`${getArduinoUrl()}${endpoint}`, options);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);
        isConnected = false;
        updateConnectionStatus();
        return null;
    }
}

async function loadStatus() {
    const status = await apiCall('/api/status');
    if (!status) return;

    statusCache = status;
    document.getElementById('toggle-armed').checked = status.armed;
    document.getElementById('toggle-keyword').checked = status.keyword_spotting;
    document.getElementById('toggle-sound').checked = status.sound_classification;
    document.getElementById('toggle-anomaly').checked = status.anomaly_detection;

    updateStatusDisplay();
    updateStats();
    updateLastUpdate();
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

async function loadEvents(type = currentFilter) {
    currentFilter = type;
    const query = type !== 'all' ? `?type=${type}&limit=100` : '?limit=100';
    const data = await apiCall(`/api/events${query}`);

    if (!data || !data.rows) {
        eventsList.innerHTML = '<p class="loading">Nessun evento</p>';
        return;
    }

    eventsList.innerHTML = data.rows.map(event => createEventElement(event)).join('');
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
async function toggleArmed() {
    const armed = document.getElementById('toggle-armed').checked;
    await apiCall('/api/control', 'POST', { armed });
    await loadStatus();
}

async function toggleKeywordSpotting() {
    const enabled = document.getElementById('toggle-keyword').checked;
    await apiCall('/api/control', 'POST', { keyword_spotting: enabled });
    await loadStatus();
}

async function toggleSoundClassification() {
    const enabled = document.getElementById('toggle-sound').checked;
    await apiCall('/api/control', 'POST', { sound_classification: enabled });
    await loadStatus();
}

async function toggleAnomalyDetection() {
    const enabled = document.getElementById('toggle-anomaly').checked;
    await apiCall('/api/control', 'POST', { anomaly_detection: enabled });
    await loadStatus();
}

function filterEvents(type) {
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    loadEvents(type);
}

function updateConnectionStatus() {
    if (isConnected) {
        connectionStatus.className = 'connection-status connected';
        connectionStatus.textContent = '✓ Connesso';
    } else {
        connectionStatus.className = 'connection-status disconnected';
        connectionStatus.textContent = '✗ Disconnesso';
    }
}

function updateLastUpdate() {
    const now = new Date();
    document.getElementById('last-update').textContent = now.toLocaleTimeString('it-IT');
}

// ── Initialize App ──────────────────────────────────────────────────────────
function initializeApp() {
    arduinoIpInput.value = arduinoIp;
    arduinoPortInput.value = arduinoPort;

    // Initial connection test
    testConnection();

    // Refresh every 10 seconds
    setInterval(() => {
        if (isConnected) {
            loadStatus();
            loadEvents(currentFilter);
        }
    }, 10000);

    // Listen to Firebase events for real-time updates
    if (currentUser) {
        const eventsRef = database.ref(`elderly/${currentUser.uid}/events`);
        eventsRef.limitToLast(100).on('value', (snapshot) => {
            if (snapshot.exists()) {
                updateLastUpdate();
            }
        });
    }
}

// ── On Load ─────────────────────────────────────────────────────────────────
window.addEventListener('load', () => {
    // Check if user is already logged in
    if (currentUser) {
        initializeApp();
    }
});
