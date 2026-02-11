const API_BASE =
  document.documentElement.dataset.apiBase || "http://localhost:8000";

const statusEl = document.getElementById("status");
const requestForm = document.getElementById("request-form");
const signupForm = document.getElementById("signup-form");
const loginForm = document.getElementById("login-form");
const appPanel = document.getElementById("app-panel");

const requestEmail = document.getElementById("request-email");
const requestReason = document.getElementById("request-reason");
const checkStatusBtn = document.getElementById("check-status");
const switchLoginBtn = document.getElementById("switch-login");

const signupEmail = document.getElementById("signup-email");
const signupPassword = document.getElementById("signup-password");
const signupConfirm = document.getElementById("signup-confirm");
const backRequestBtn = document.getElementById("back-request");

const loginEmail = document.getElementById("login-email");
const loginPassword = document.getElementById("login-password");
const loginBackBtn = document.getElementById("login-back");

const logoutBtn = document.getElementById("logout");
const refreshProfileBtn = document.getElementById("refresh-profile");
const appEmail = document.getElementById("app-email");

const preferencesForm = document.getElementById("preferences-form");
const preferencesNote = document.getElementById("preferences-note");
const preferencesSummary = document.getElementById("preferences-summary");
const minPriceInput = document.getElementById("min-price");
const maxPriceInput = document.getElementById("max-price");
const minAreaInput = document.getElementById("min-area");
const maxAreaInput = document.getElementById("max-area");
const preferredCitiesContainer = document.getElementById("preferred-cities");
const loadPreferencesBtn = document.getElementById("load-preferences");
const startRecommendationsBtn = document.getElementById("start-recommendations");
const editPreferencesBtn = document.getElementById("edit-preferences");
const preferencesSummaryResults = document.getElementById(
  "preferences-summary-results"
);
const appPanels = document.querySelectorAll("[data-app-panel]");

const qaEmpty = document.getElementById("qa-empty");
const qaContent = document.getElementById("qa-content");
const qaQuestion = document.getElementById("qa-question");
const qaAnswer = document.getElementById("qa-answer");
const propertiesList = document.getElementById("properties-list");
const propertiesCount = document.getElementById("properties-count");

const stepCards = document.querySelectorAll(".step");
const panels = document.querySelectorAll("[data-panel]");

const state = {
  email: "",
  token: localStorage.getItem("findmyhome_token") || "",
  step: "request",
  preferences: null,
  hasChats: false,
  threadId: "",
};

const PRICE_MIN = 55000;
const PRICE_MAX = 840000000;
const AREA_MIN = 70;
const AREA_MAX = 35000;
const ALLOWED_CITIES = new Set([
  "Thane",
  "Bangalore",
  "Mumbai",
  "New Delhi",
  "Kolkata",
  "Chennai",
  "Pune",
  "Hyderabad",
]);

function setStatus(type, message) {
  statusEl.className = `status status--${type}`;
  statusEl.textContent = message;
  statusEl.classList.remove("is-hidden");
}

function clearStatus() {
  statusEl.className = "status is-hidden";
  statusEl.textContent = "";
}

function setStep(step) {
  state.step = step;
  document.body.classList.toggle("app-mode", step === "app");
  panels.forEach((panel) => {
    panel.classList.toggle("is-hidden", panel.dataset.panel !== step);
  });
  stepCards.forEach((card) => {
    card.classList.toggle("step--active", card.dataset.step === step);
  });
}

function setAppPanel(panelName) {
  appPanels.forEach((panel) => {
    panel.classList.toggle("is-hidden", panel.dataset.appPanel !== panelName);
  });
}

function setEmail(email) {
  state.email = email;
  requestEmail.value = email;
  signupEmail.value = email;
  loginEmail.value = email;
}

function setLoading(form, isLoading) {
  const buttons = form.querySelectorAll("button");
  buttons.forEach((btn) => {
    btn.disabled = isLoading;
  });
}

function getAuthHeaders() {
  if (!state.token) {
    return {};
  }
  return { Authorization: `Bearer ${state.token}` };
}

function formatNumber(value) {
  if (!Number.isFinite(value)) {
    return "N/A";
  }
  return value.toLocaleString("en-US");
}

function formatPrice(value) {
  if (!Number.isFinite(value)) {
    return "N/A";
  }
  return `Rs. ${formatNumber(value)}`;
}

function formatArea(value) {
  if (!Number.isFinite(value)) {
    return "N/A";
  }
  return `${formatNumber(value)} sq ft`;
}

function updateStartButtonState() {
  startRecommendationsBtn.disabled = !state.preferences;
}

function clearRecommendations() {
  qaContent.classList.add("is-hidden");
  qaEmpty.classList.remove("is-hidden");
  qaQuestion.textContent = "";
  qaAnswer.textContent = "";
  propertiesList.innerHTML = "";
  propertiesCount.textContent = "No homes yet";
  const empty = document.createElement("p");
  empty.className = "empty-state";
  empty.textContent = "No recommendations yet.";
  propertiesList.appendChild(empty);
}

function renderPreferencesSummary(preferences) {
  const targets = [preferencesSummary, preferencesSummaryResults];
  targets.forEach((target) => {
    if (!target) {
      return;
    }
    target.classList.remove("is-hidden");
    target.innerHTML = "";

    if (!preferences) {
      target.textContent = "No preferences saved yet.";
      return;
    }

    const list = document.createElement("ul");
    const priceItem = document.createElement("li");
    priceItem.textContent = `Price range: ${formatPrice(
      preferences.min_price
    )} to ${formatPrice(preferences.max_price)}`;
    list.appendChild(priceItem);

    const areaItem = document.createElement("li");
    areaItem.textContent = `Area range: ${formatArea(
      preferences.min_area
    )} to ${formatArea(preferences.max_area)}`;
    list.appendChild(areaItem);

    const citiesItem = document.createElement("li");
    const cities = Array.isArray(preferences.preferred_cities)
      ? preferences.preferred_cities.join(", ")
      : "None selected";
    citiesItem.textContent = `Preferred cities: ${cities}`;
    list.appendChild(citiesItem);

    target.appendChild(list);
  });
}

function fillPreferencesForm(preferences) {
  if (!preferences) {
    return;
  }
  minPriceInput.value = preferences.min_price ?? "";
  maxPriceInput.value = preferences.max_price ?? "";
  minAreaInput.value = preferences.min_area ?? "";
  maxAreaInput.value = preferences.max_area ?? "";

  const selected = new Set(preferences.preferred_cities || []);
  Array.from(
    preferredCitiesContainer.querySelectorAll('input[type="checkbox"]')
  ).forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function readPreferencesForm() {
  const preferred_cities = Array.from(
    preferredCitiesContainer.querySelectorAll('input[type="checkbox"]:checked')
  ).map((input) => input.value);

  return {
    min_price: Number(minPriceInput.value),
    max_price: Number(maxPriceInput.value),
    min_area: Number(minAreaInput.value),
    max_area: Number(maxAreaInput.value),
    preferred_cities,
  };
}

function validatePreferences(preferences) {
  if (!Number.isFinite(preferences.min_price)) {
    return "Min price is required.";
  }
  if (!Number.isFinite(preferences.max_price)) {
    return "Max price is required.";
  }
  if (!Number.isFinite(preferences.min_area)) {
    return "Min area is required.";
  }
  if (!Number.isFinite(preferences.max_area)) {
    return "Max area is required.";
  }
  if (preferences.min_price < PRICE_MIN || preferences.min_price > PRICE_MAX) {
    return `Min price must be between ${PRICE_MIN} and ${PRICE_MAX}.`;
  }
  if (preferences.max_price < PRICE_MIN || preferences.max_price > PRICE_MAX) {
    return `Max price must be between ${PRICE_MIN} and ${PRICE_MAX}.`;
  }
  if (preferences.min_price > preferences.max_price) {
    return "Min price cannot be higher than max price.";
  }
  if (preferences.min_area < AREA_MIN || preferences.min_area > AREA_MAX) {
    return `Min area must be between ${AREA_MIN} and ${AREA_MAX} sq ft.`;
  }
  if (preferences.max_area < AREA_MIN || preferences.max_area > AREA_MAX) {
    return `Max area must be between ${AREA_MIN} and ${AREA_MAX} sq ft.`;
  }
  if (preferences.min_area > preferences.max_area) {
    return "Min area cannot be higher than max area.";
  }
  if (!preferences.preferred_cities.length) {
    return "Select at least one preferred city.";
  }
  for (const city of preferences.preferred_cities) {
    if (!ALLOWED_CITIES.has(city)) {
      return "One or more selected cities are not supported.";
    }
  }
  return "";
}

function makeStat(label, value) {
  const stat = document.createElement("div");
  stat.className = "property-stat";
  const statLabel = document.createElement("span");
  statLabel.textContent = label;
  const statValue = document.createElement("strong");
  statValue.textContent = value;
  stat.appendChild(statLabel);
  stat.appendChild(statValue);
  return stat;
}

function createPropertyCard(property) {
  const card = document.createElement("article");
  card.className = "property-card";

  const title = document.createElement("h6");
  title.className = "property-title";
  title.textContent = property.name || "Unnamed property";
  card.appendChild(title);

  const metaParts = [
    property.cityName,
    property.property_type,
    property.room_type,
  ].filter(Boolean);
  if (metaParts.length) {
    const meta = document.createElement("p");
    meta.className = "property-meta";
    meta.textContent = metaParts.join(" | ");
    card.appendChild(meta);
  }

  const stats = document.createElement("div");
  stats.className = "property-stats";
  stats.appendChild(makeStat("Price", formatPrice(property.price)));
  stats.appendChild(makeStat("Area", formatArea(property.totalArea)));
  stats.appendChild(makeStat("Beds", property.beds ?? "N/A"));
  stats.appendChild(makeStat("Baths", property.baths ?? "N/A"));
  stats.appendChild(
    makeStat("Price/sq ft", formatPrice(property.pricePerSqft))
  );
  card.appendChild(stats);

  const tags = document.createElement("div");
  tags.className = "property-tags";
  if (property.hasBalcony === true) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "Balcony";
    tags.appendChild(tag);
  }
  if (property.hasBalcony === false) {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = "No balcony";
    tags.appendChild(tag);
  }
  if (tags.children.length) {
    card.appendChild(tags);
  }

  if (property.description) {
    const desc = document.createElement("p");
    desc.className = "property-desc";
    desc.textContent = property.description;
    card.appendChild(desc);
  }

  return card;
}

function renderPropertyList(properties) {
  propertiesList.innerHTML = "";
  if (!Array.isArray(properties) || properties.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No recommendations yet.";
    propertiesList.appendChild(empty);
    propertiesCount.textContent = "No homes yet";
    return;
  }

  propertiesCount.textContent = `${properties.length} homes`;
  properties.forEach((property) => {
    if (property && typeof property === "object") {
      propertiesList.appendChild(createPropertyCard(property));
    }
  });
}

function renderRecommendationsFromState(stateData) {
  const turnLog = Array.isArray(stateData?.turn_log) ? stateData.turn_log : [];
  const lastTurn = turnLog[turnLog.length - 1];
  if (!lastTurn) {
    clearRecommendations();
    return;
  }

  qaQuestion.textContent = lastTurn.question || lastTurn.query_used || "";
  qaAnswer.textContent =
    lastTurn.answer || stateData.augmentation_summary || "";
  qaEmpty.classList.add("is-hidden");
  qaContent.classList.remove("is-hidden");
  renderPropertyList(lastTurn.recommended_properties || []);
}

async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  let data = {};
  try {
    data = await response.json();
  } catch (error) {
    data = {};
  }

  if (!response.ok) {
    const detail = data.detail || data.message || response.statusText;
    const err = new Error(detail);
    err.status = response.status;
    err.data = data;
    throw err;
  }

  return data;
}

async function loadChatOverview() {
  try {
    const chats = await apiFetch("/my-chats", {
      headers: getAuthHeaders(),
    });
    state.hasChats = Array.isArray(chats) && chats.length > 0;
    preferencesNote.textContent = state.hasChats
      ? "We found previous chats. You can update preferences or start new recommendations."
      : "No chats yet. Save your preferences to start recommendations.";
  } catch (error) {
    preferencesNote.textContent =
      "Unable to load chat history. You can still set preferences.";
  }
}

async function loadPreferences(showStatus = false) {
  try {
    const data = await apiFetch("/my-preferences", {
      headers: getAuthHeaders(),
    });
    const preferences = data.preferences || null;
    state.preferences = preferences;
    renderPreferencesSummary(preferences);
    fillPreferencesForm(preferences);
    updateStartButtonState();
    if (showStatus) {
      setStatus(
        "success",
        preferences ? "Preferences loaded." : "No preferences saved yet."
      );
    }
    return preferences;
  } catch (error) {
    if (showStatus) {
      setStatus("error", error.message || "Failed to load preferences.");
    }
    state.preferences = null;
    renderPreferencesSummary(null);
    updateStartButtonState();
    return null;
  }
}

async function handleSavePreferences(event) {
  event.preventDefault();
  clearStatus();

  const preferences = readPreferencesForm();
  const error = validatePreferences(preferences);
  if (error) {
    setStatus("error", error);
    return;
  }

  setLoading(preferencesForm, true);
  startRecommendationsBtn.disabled = true;

  try {
    await apiFetch("/save-preferences", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(preferences),
    });
    state.preferences = preferences;
    renderPreferencesSummary(preferences);
    updateStartButtonState();
    setStatus("success", "Preferences saved.");
  } catch (err) {
    setStatus("error", err.message || "Failed to save preferences.");
  } finally {
    setLoading(preferencesForm, false);
  }
}

async function handleLoadPreferences() {
  clearStatus();
  loadPreferencesBtn.disabled = true;
  await loadPreferences(true);
  loadPreferencesBtn.disabled = false;
}

async function handleStartRecommendations() {
  clearStatus();
  if (!state.preferences) {
    setStatus("error", "Save your preferences before starting.");
    return;
  }

  startRecommendationsBtn.disabled = true;
  try {
    const data = await apiFetch("/initial-preferences", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({}),
    });
    state.threadId = data.thread_id || "";
    renderRecommendationsFromState(data.state || {});
    setAppPanel("results");
    setStatus("success", "Recommendations are ready.");
  } catch (error) {
    setStatus("error", error.message || "Failed to start recommendations.");
  } finally {
    updateStartButtonState();
  }
}

async function initializeApp() {
  if (!state.token) {
    return;
  }
  clearRecommendations();
  setAppPanel("preferences");
  await loadChatOverview();
  await loadPreferences();
  updateStartButtonState();
}

function handleApprovalError(detail) {
  const text = detail.toLowerCase();

  if (text.includes("approved")) {
    setStatus("success", "You are approved. Create a password to continue.");
    setStep("signup");
    return;
  }

  if (text.includes("log in")) {
    setStatus("success", "You already have access. Log in to continue.");
    setStep("login");
    return;
  }

  if (text.includes("submitted for approval")) {
    setStatus("info", "Your request is still under review. Check again later.");
    checkStatusBtn.classList.remove("is-hidden");
    return;
  }

  if (text.includes("rejected")) {
    setStatus("warning", "Your request was not approved. Contact the admin.");
    return;
  }

  setStatus("error", detail);
}

async function handleRequestApproval() {
  clearStatus();
  const email = requestEmail.value.trim();
  const reason = requestReason.value.trim();

  if (!email) {
    setStatus("error", "Please enter your email.");
    return;
  }

  setEmail(email);
  setLoading(requestForm, true);

  try {
    const payload = { email };
    if (reason) {
      payload.reason = reason;
    }

    const data = await apiFetch("/request-approval", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setStatus(
      "success",
      `${data.message}. We will notify you after approval.`
    );
    checkStatusBtn.classList.remove("is-hidden");
  } catch (error) {
    handleApprovalError(error.message || "Request failed.");
  } finally {
    setLoading(requestForm, false);
  }
}

async function handleSignup(event) {
  event.preventDefault();
  clearStatus();

  const email = signupEmail.value.trim() || state.email;
  const password = signupPassword.value;
  const confirm = signupConfirm.value;

  if (!email) {
    setStatus("error", "Missing email for signup.");
    return;
  }

  if (password.length < 8) {
    setStatus("error", "Password must be at least 8 characters.");
    return;
  }

  if (password !== confirm) {
    setStatus("error", "Passwords do not match.");
    return;
  }

  setLoading(signupForm, true);

  try {
    const data = await apiFetch("/signup", {
      method: "POST",
      body: JSON.stringify({
        email,
        password,
      }),
    });

    setEmail(email);
    setStatus("success", `${data.message}. Please log in to continue.`);
    signupPassword.value = "";
    signupConfirm.value = "";
    setStep("login");
  } catch (error) {
    setStatus("error", error.message || "Signup failed.");
  } finally {
    setLoading(signupForm, false);
  }
}

async function handleLogin(event) {
  event.preventDefault();
  clearStatus();

  const email = loginEmail.value.trim();
  const password = loginPassword.value;
  if (!email) {
    setStatus("error", "Please enter your email.");
    return;
  }

  if (!password) {
    setStatus("error", "Please enter your password.");
    return;
  }

  setEmail(email);
  setLoading(loginForm, true);

  try {
    const data = await apiFetch("/login", {
      method: "POST",
      body: JSON.stringify({
        email: state.email,
        password,
      }),
    });

    state.token = data.access_token;
    localStorage.setItem("findmyhome_token", data.access_token);
    loginPassword.value = "";
    setStep("app");
    await loadProfile();
    if (state.token) {
      await initializeApp();
    }
  } catch (error) {
    setStatus("error", error.message || "Login failed.");
  } finally {
    setLoading(loginForm, false);
  }
}

async function loadProfile() {
  if (!state.token) {
    return;
  }

  try {
    const data = await apiFetch("/profile", {
      headers: getAuthHeaders(),
    });
    appEmail.textContent = `Signed in as ${data.email}`;
  } catch (error) {
    localStorage.removeItem("findmyhome_token");
    state.token = "";
    setStatus("error", "Session expired. Please log in again.");
    setStep("login");
  }
}

requestForm.addEventListener("submit", (event) => {
  event.preventDefault();
  handleRequestApproval();
});

checkStatusBtn.addEventListener("click", handleRequestApproval);

signupForm.addEventListener("submit", handleSignup);

loginForm.addEventListener("submit", handleLogin);

preferencesForm.addEventListener("submit", handleSavePreferences);

loadPreferencesBtn.addEventListener("click", handleLoadPreferences);

startRecommendationsBtn.addEventListener("click", handleStartRecommendations);

editPreferencesBtn.addEventListener("click", () => {
  setAppPanel("preferences");
});

switchLoginBtn.addEventListener("click", () => {
  clearStatus();
  if (requestEmail.value.trim()) {
    setEmail(requestEmail.value.trim());
  }
  setStep("login");
});

backRequestBtn.addEventListener("click", () => {
  clearStatus();
  setStep("request");
});

loginBackBtn.addEventListener("click", () => {
  clearStatus();
  if (loginEmail.value.trim()) {
    setEmail(loginEmail.value.trim());
  }
  setStep("request");
});

logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("findmyhome_token");
  state.token = "";
  state.preferences = null;
  state.hasChats = false;
  state.threadId = "";
  preferencesForm.reset();
  Array.from(
    preferredCitiesContainer.querySelectorAll('input[type="checkbox"]')
  ).forEach((input) => {
    input.checked = false;
  });
  preferencesNote.textContent =
    "No chats yet. Save your preferences to start recommendations.";
  renderPreferencesSummary(null);
  clearRecommendations();
  updateStartButtonState();
  setStatus("info", "You have been logged out.");
  setStep("login");
});

refreshProfileBtn.addEventListener("click", () => {
  loadProfile().then(() => {
    if (state.token) {
      initializeApp();
    }
  });
});

if (state.token) {
  setStep("app");
  loadProfile().then(() => {
    if (state.token) {
      initializeApp();
    }
  });
} else {
  setStep("request");
}
