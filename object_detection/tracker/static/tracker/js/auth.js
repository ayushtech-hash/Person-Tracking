/**
 * Shared client-side logic for login.html / register.html.
 * Tokens live in httpOnly cookies set by the server (see
 * tracker/services/auth/tokens.py) - this file never reads or stores
 * the JWT itself, it only POSTs credentials and reacts to the result.
 */

const AUTH_API_BASE = '/api/auth';

function qs(sel, root = document) {
  return root.querySelector(sel);
}

function setFieldError(fieldName, message) {
  const el = document.querySelector(`[data-error-for="${fieldName}"]`);
  if (el) el.textContent = message || '';
}

function clearFieldErrors(form) {
  form.querySelectorAll('[data-error-for]').forEach((el) => (el.textContent = ''));
}

function showBanner(form, message) {
  const banner = qs('[data-auth-banner]', form);
  if (!banner) return;
  if (message) {
    banner.textContent = message;
    banner.classList.add('is-visible');
  } else {
    banner.textContent = '';
    banner.classList.remove('is-visible');
  }
}

function setLoading(form, isLoading) {
  const btn = qs('[data-submit]', form);
  if (!btn) return;
  btn.disabled = isLoading;
  btn.textContent = isLoading ? btn.dataset.loadingLabel || 'Working…' : btn.dataset.idleLabel;
}

async function postJSON(path, body) {
  const res = await fetch(`${AUTH_API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include', // send/receive the httpOnly cookies
    body: JSON.stringify(body),
  });
  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    /* no body */
  }
  return { ok: res.ok, status: res.status, data };
}

function nextUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get('next') || '/';
}

function initLoginForm() {
  const form = qs('#login-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFieldErrors(form);
    showBanner(form, '');
    setLoading(form, true);

    const payload = {
      username: form.username.value.trim(),
      password: form.password.value,
    };

    const { ok, data } = await postJSON('/login/', payload);

    if (ok) {
      window.location.href = nextUrl();
      return;
    }

    showBanner(form, data.detail || 'Login failed. Check your credentials and try again.');
    setLoading(form, false);
  });
}

function initRegisterForm() {
  const form = qs('#register-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearFieldErrors(form);
    showBanner(form, '');
    setLoading(form, true);

    const payload = {
      username: form.username.value.trim(),
      email: form.email.value.trim(),
      password: form.password.value,
      password_confirm: form.password_confirm.value,
    };

    const { ok, data } = await postJSON('/register/', payload);

    if (ok) {
      window.location.href = '/';
      return;
    }

    if (data.field) {
      setFieldError(data.field, data.detail);
    } else if (data.username) {
      setFieldError('username', Array.isArray(data.username) ? data.username[0] : data.username);
    } else {
      showBanner(form, data.detail || 'Registration failed. Please check the form and try again.');
    }
    setLoading(form, false);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  initLoginForm();
  initRegisterForm();
});
