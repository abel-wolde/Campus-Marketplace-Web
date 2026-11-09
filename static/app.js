// Renders the signed-in state in the header on every page.
async function refreshAuth() {
  const slot = document.getElementById('auth-links');
  if (!slot) return;
  try {
    const res = await fetch('/api/me');
    const { user } = await res.json();
    if (user) {
      slot.innerHTML = `<span>Signed in as ${escapeHtml(user.name)}</span>
        <button class="link" id="logout-btn">Log out</button>`;
      document.getElementById('logout-btn').addEventListener('click', async () => {
        await fetch('/api/logout', { method: 'POST' });
        window.location.href = '/';
      });
    } else {
      slot.innerHTML = '<a href="/login">Log in</a><a href="/register">Register</a>';
    }
  } catch {
    slot.innerHTML = '<a href="/login">Log in</a>';
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
}
refreshAuth();
