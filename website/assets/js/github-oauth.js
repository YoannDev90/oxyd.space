/**
 * GitHub OAuth via Supabase Auth.
 * Handles sign-in, session management, and GitHub token retrieval.
 * Free tier: 50K monthly active users.
 */
var GitHubOAuth = (function () {
  var REPO = 'YoannDev90/oxyd.space';
  var TOKEN_KEY = 'oxyd-gh-token';

  // Supabase project URL — create at https://supabase.com (free)
  var SUPABASE_URL = 'https://dqguiuyyhjqrrscncnnr.supabase.co';
  var SUPABASE_ANON_KEY = 'sb_publishable_aoaeIJ3lLeLohAXKcTeYxw_VOjD3Vxt';

  var supabase = null;

  function init() {
    if (typeof window.supabase !== 'undefined' && window.supabase.createClient) {
      supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
    }
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
  }

  function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
  }

  async function login() {
    if (!supabase) init();
    if (!supabase) {
      console.error('Supabase client not loaded');
      return;
    }
    await supabase.auth.signInWithOAuth({
      provider: 'github',
      options: {
        redirectTo: window.location.origin + '/dashboard',
        scopes: 'public_repo user:email',
      }
    });
  }

  async function handleRedirect() {
    if (!supabase) init();
    if (!supabase) return false;

    var url = window.location.href;
    if (!url.includes('#') && !url.includes('code=')) return false;

    var session = await supabase.auth.getSession();
    if (session.data.session && session.data.session.provider_token) {
      setToken(session.data.session.provider_token);
      return true;
    }
    return false;
  }

  async function getSessionEmail() {
    if (!supabase) init();
    if (!supabase) return null;
    var session = await supabase.auth.getSession();
    return session.data.session?.user?.email || null;
  }

  async function getAuthUser() {
    if (!supabase) init();
    if (!supabase) return null;
    var session = await supabase.auth.getSession();
    return session.data.session?.user || null;
  }

  async function getUser(token) {
    var resp = await fetch('https://api.github.com/user', {
      headers: {
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json'
      }
    });
    if (!resp.ok) return null;
    return resp.json();
  }

  async function logout() {
    if (supabase) await supabase.auth.signOut();
    clearToken();
  }

  function getSupabase() {
    if (!supabase) init();
    return supabase;
  }

  init();

  return {
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    getUser: getUser,
    login: login,
    logout: logout,
    handleRedirect: handleRedirect,
    getSessionEmail: getSessionEmail,
    getAuthUser: getAuthUser,
    getSupabase: getSupabase,
    REPO: REPO
  };
})();
