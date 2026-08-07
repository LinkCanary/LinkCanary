/**
 * Better Auth client — handles signup, login, logout, session management.
 * Talks to the Better Auth service via the Caddy proxy at /auth/*
 */

const AUTH_BASE = '/auth';

async function authFetch(path, options = {}) {
  const res = await fetch(`${AUTH_BASE}${path}`, {
    credentials: 'include', // send cookies
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.message || data.error || `Auth error: ${res.status}`);
  }
  return data;
}

export async function signUpEmail(email, password, name) {
  return authFetch('/sign-up/email', {
    method: 'POST',
    body: JSON.stringify({ email, password, name }),
  });
}

export async function signInEmail(email, password) {
  return authFetch('/sign-in/email', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function signInSocial(provider) {
  // Redirects to the provider's OAuth page
  const res = await fetch(`${AUTH_BASE}/social/${provider}?callbackURL=${encodeURIComponent('/dashboard')}`, {
    credentials: 'include',
    redirect: 'follow',
  });
  // The browser follows the redirect to Google/GitHub
  if (res.redirected) {
    window.location.href = res.url;
  }
}

export async function signOut() {
  return authFetch('/sign-out', { method: 'POST' });
}

export async function getSession() {
  try {
    const data = await authFetch('/get-session');
    return data?.session ? data : null;
  } catch {
    return null;
  }
}

export async function forgotPassword(email) {
  return authFetch('/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email, redirectTo: '/reset-password' }),
  });
}

export async function resetPassword(newPassword, token) {
  return authFetch('/reset-password', {
    method: 'POST',
    body: JSON.stringify({ newPassword, token }),
  });
}

export async function verifyEmail(token) {
  return authFetch(`/verify-email?token=${encodeURIComponent(token)}`, {
    method: 'GET',
  });
}

export async function sendVerificationEmail(email) {
  return authFetch('/send-verification-email', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}
