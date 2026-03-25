/**
 * Dev Portal — auth.js  v1.1.0
 * Token management, auth guards, API header injection.
 */

const AUTH_TOKEN_KEY = 'dp_token';
const AUTH_USER_KEY = 'dp_username';

function getToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function getUsername() {
  return localStorage.getItem(AUTH_USER_KEY);
}

function saveAuth(token, username) {
  localStorage.setItem(AUTH_TOKEN_KEY, token);
  localStorage.setItem(AUTH_USER_KEY, username);
}

function clearAuth() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

function isLoggedIn() {
  return !!getToken();
}

function authHeaders() {
  var token = getToken();
  if (!token) return {};
  return { 'Authorization': 'Bearer ' + token };
}

function requireAuth() {
  if (!isLoggedIn()) {
    window.location.href = '/login';
  }
}

function logout() {
  clearAuth();
  window.location.href = '/';
}
