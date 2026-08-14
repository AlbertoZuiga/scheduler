const loginLink = document.getElementById('google-login');

function setLoading(loading) {
  if (!loginLink) return;
  loginLink.setAttribute('aria-busy', loading ? 'true' : 'false');
  loginLink.classList.toggle('pointer-events-none', loading);
  loginLink.classList.toggle('opacity-70', loading);
  loginLink.querySelector('[data-state="idle"]').classList.toggle('hidden', loading);
  loginLink.querySelector('[data-state="loading"]').classList.toggle('hidden', !loading);
}

loginLink?.addEventListener('click', () => setLoading(true));

window.addEventListener('pageshow', (event) => {
  if (event.persisted) setLoading(false);
});
