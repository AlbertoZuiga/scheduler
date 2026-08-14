document.addEventListener('DOMContentLoaded', function () {
  const menuToggle = document.getElementById('menu-toggle');
  const mobileMenu = document.getElementById('mobile-menu');
  if (menuToggle && mobileMenu) {
    menuToggle.addEventListener('click', () => {
      const isExpanded = mobileMenu.classList.toggle('hidden');
      menuToggle.setAttribute('aria-expanded', !isExpanded);
      if (!isExpanded) {
        const closeMenu = (e) => {
          if (!mobileMenu.contains(e.target) && !menuToggle.contains(e.target)) {
            mobileMenu.classList.add('hidden');
            menuToggle.setAttribute('aria-expanded', 'false');
            document.removeEventListener('click', closeMenu);
          }
        };
        setTimeout(() => document.addEventListener('click', closeMenu), 0);
      }
    });
  }

  const userMenuButton = document.getElementById('user-menu');
  const userMenu = document.getElementById('user-menu-dropdown');
  if (userMenuButton && userMenu) {
    const menuItems = () => Array.from(userMenu.querySelectorAll('a[href]'));

    function setUserMenu(open, { focusButton = false } = {}) {
      userMenu.classList.toggle('hidden', !open);
      userMenuButton.setAttribute('aria-expanded', open ? 'true' : 'false');
      if (focusButton) userMenuButton.focus();
    }

    userMenuButton.addEventListener('click', () => {
      setUserMenu(userMenu.classList.contains('hidden'));
    });

    userMenuButton.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        setUserMenu(true);
        const items = menuItems();
        (event.key === 'ArrowDown' ? items[0] : items[items.length - 1])?.focus();
      }
    });

    userMenu.addEventListener('keydown', (event) => {
      const items = menuItems();
      const index = items.indexOf(document.activeElement);
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        items[(index + 1) % items.length]?.focus();
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        items[(index - 1 + items.length) % items.length]?.focus();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !userMenu.classList.contains('hidden')) {
        setUserMenu(false, { focusButton: true });
      }
    });

    document.addEventListener('click', (event) => {
      if (userMenu.classList.contains('hidden')) return;
      if (!userMenu.contains(event.target) && !userMenuButton.contains(event.target)) {
        setUserMenu(false);
      }
    });

    userMenu.addEventListener('focusout', (event) => {
      if (!userMenu.contains(event.relatedTarget) && event.relatedTarget !== userMenuButton) {
        setUserMenu(false);
      }
    });
  }

  const darkModeText = document.getElementById('dark-mode-text');
  const sunIcons = document.querySelectorAll('#icon-sun, #icon-sun-mobile');
  const moonIcons = document.querySelectorAll('#icon-moon, #icon-moon-mobile');

  function syncDarkModeUI(dark) {
    sunIcons.forEach((icon) => icon.classList.toggle('hidden', !dark));
    moonIcons.forEach((icon) => icon.classList.toggle('hidden', dark));
    if (darkModeText) darkModeText.textContent = dark ? 'Modo claro' : 'Modo oscuro';
  }

  function setDarkMode(dark) {
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('theme', dark ? 'dark' : 'light');
    syncDarkModeUI(dark);
  }

  syncDarkModeUI(document.documentElement.classList.contains('dark'));

  document.querySelectorAll('#dark-toggle, #dark-toggle-mobile').forEach((toggle) => {
    toggle.addEventListener('click', () => {
      setDarkMode(!document.documentElement.classList.contains('dark'));
    });
  });
});
