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

const stepCards = document.querySelectorAll(".step");
const panels = document.querySelectorAll("[data-panel]");

const state = {
  email: "",
  token: localStorage.getItem("findmyhome_token") || "",
  step: "request",
};

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
  panels.forEach((panel) => {
    panel.classList.toggle("is-hidden", panel.dataset.panel !== step);
  });
  stepCards.forEach((card) => {
    card.classList.toggle("step--active", card.dataset.step === step);
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

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
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
      headers: {
        Authorization: `Bearer ${state.token}`,
      },
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
  setStatus("info", "You have been logged out.");
  setStep("login");
});

refreshProfileBtn.addEventListener("click", loadProfile);

if (state.token) {
  setStep("app");
  loadProfile();
} else {
  setStep("request");
}
