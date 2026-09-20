/* =====================================================================
   Spendwise – Data Layer (window.SWApi)

   Communicates directly with the Python Flask Backend REST API (`/api/*`)
   and Cloud MongoDB Atlas Database.
   ===================================================================== */
(function (w) {
  'use strict';

  var host = (w.location && w.location.hostname) ? w.location.hostname : '127.0.0.1';
  if (host === 'localhost') host = '127.0.0.1';
  var API_BASE = (w.location && w.location.protocol && w.location.protocol.indexOf('http') === 0)
    ? w.location.protocol + '//' + host + ':5001/api'
    : 'http://127.0.0.1:5001/api';

  var USERS_KEY = 'sw-users';
  var SESSION_KEY = 'sw-session';

  /* Helper to perform JSON fetch requests to Python Flask backend */
  function apiFetch(endpoint, method, payload) {
    var isFile = (w.location && w.location.protocol === 'file:');
    var opts = {
      method: method || 'GET',
      headers: { 'Content-Type': 'application/json' },
      credentials: isFile ? 'same-origin' : 'include'
    };
    if (payload && method !== 'GET') {
      opts.body = JSON.stringify(payload);
    }

    var sessionUser = read(SESSION_KEY, null);
    var url = API_BASE + endpoint;
    if (sessionUser && (method === 'GET' || endpoint === '/check-purchase' || endpoint === '/buy' || endpoint === '/send-report')) {
      var sep = url.indexOf('?') > -1 ? '&' : '?';
      url += sep + 'username=' + encodeURIComponent(sessionUser);
    }

    return fetch(url, opts)
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) {
            var err = new Error(data.message || data.error || 'Server error occurred.');
            if (data.field) err.field = data.field;
            throw err;
          }
          return data;
        });
      })
      .catch(function (err) {
        var msg = err && err.message ? err.message : '';
        if (msg.indexOf('Failed to fetch') > -1 || msg.indexOf('Load failed') > -1 || msg.indexOf('NetworkError') > -1) {
          throw new Error('Unable to connect to Python backend server at ' + API_BASE + '. Please make sure backend/app.py is running.');
        }
        throw err;
      });
  }

  function read(key, fallback) {
    try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; }
    catch (e) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch (e) { return false; }
  }

  // Clear legacy mock localStorage users to eliminate shadow conflicts
  try { localStorage.removeItem(USERS_KEY); } catch (e) {}

  var SWApi = {
    /* Register user account directly in MongoDB via Python API */
    register: function (d) {
      return apiFetch('/register', 'POST', d).then(function (user) {
        write(SESSION_KEY, user.username);
        return user;
      });
    },

    /* Log in user directly against MongoDB via Python API */
    login: function (username, password) {
      return apiFetch('/login', 'POST', { username: username, password: password })
        .then(function (user) {
          write(SESSION_KEY, user.username);
          return user;
        });
    },

    /* Log out user */
    logout: function () {
      var username = read(SESSION_KEY, null);
      try { localStorage.removeItem(SESSION_KEY); } catch (e) {}
      return apiFetch('/logout', 'POST', { username: username }).catch(function () { return true; });
    },

    /* Active logged-in user profile */
    me: function () {
      var username = read(SESSION_KEY, null);
      if (!username) return Promise.resolve(null);
      return apiFetch('/me?username=' + encodeURIComponent(username), 'GET').catch(function () { return null; });
    },

    /* Update user profile details in MongoDB */
    updateProfile: function (data) {
      var username = read(SESSION_KEY, null);
      if (data && !data.username) data.username = username;
      return apiFetch('/profile/update', 'POST', data);
    },

    /* Delete user profile and all items from MongoDB */
    deleteProfile: function () {
      var username = read(SESSION_KEY, null);
      return apiFetch('/profile/delete', 'POST', { username: username }).then(function (res) {
        try { localStorage.removeItem(SESSION_KEY); } catch (e) {}
        return res;
      });
    },

    /* Evaluate purchase against limit and buffer */
    checkPurchase: function (item, price) {
      var username = read(SESSION_KEY, null);
      return apiFetch('/check-purchase', 'POST', { username: username, item: item, price: price });
    },

    /* Execute actual item purchase */
    buy: function (item, price) {
      var username = read(SESSION_KEY, null);
      return apiFetch('/buy', 'POST', { username: username, item: item, price: price });
    },

    /* Retrieve items added by user */
    getItems: function () {
      var username = read(SESSION_KEY, null);
      return apiFetch('/items?username=' + encodeURIComponent(username), 'GET')
        .then(function (res) { return res.items || []; })
        .catch(function () { return []; });
    },

    /* Send summary report via email */
    sendReport: function () {
      var username = read(SESSION_KEY, null);
      return apiFetch('/send-report', 'POST', { username: username });
    }
  };

  w.SWApi = SWApi;
})(window);
