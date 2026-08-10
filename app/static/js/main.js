/**
 * SCHEDULER - MAIN JAVASCRIPT
 * Utility functions and UI enhancements
 */

// ============================================
// GLOBAL UTILITIES
// ============================================

/**
 * Muestra una alerta inline (reemplaza a alert() nativo).
 * type: 'success' | 'danger' | 'warning' | 'info'
 * Los errores no se autocierran; el resto sí, tras 4s.
 */
function showInlineAlert(message, type = 'success') {
  const container = document.querySelector('main');
  const el = document.createElement('div');
  const styleMap = {
    success: 'bg-green-50 text-green-800 border-green-200 dark:bg-green-900/20 dark:text-green-200 dark:border-green-800',
    danger: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-900/20 dark:text-red-200 dark:border-red-800',
    warning: 'bg-yellow-50 text-yellow-800 border-yellow-200 dark:bg-yellow-900/20 dark:text-yellow-200 dark:border-yellow-800',
    info: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-900/20 dark:text-blue-200 dark:border-blue-800',
  };
  el.setAttribute('role', 'alert');
  el.className = `flex items-start justify-between gap-4 rounded-lg border px-4 py-3 text-sm ${styleMap[type] || styleMap.info}`;

  // textContent y no innerHTML: el mensaje suele traer nombres de categoría,
  // de subgrupo o de usuario, que son texto arbitrario del propio usuario.
  const body = document.createElement('div');
  body.textContent = message;
  const closeButton = document.createElement('button');
  closeButton.className = 'p-1 rounded hover:bg-black/5 dark:hover:bg-white/5';
  closeButton.setAttribute('aria-label', 'Cerrar');
  closeButton.textContent = '✕';
  closeButton.addEventListener('click', () => el.remove());
  el.append(body, closeButton);
  container?.prepend(el);
  if (type !== 'danger') {
    setTimeout(() => el.remove(), 4000);
  }
  return el;
}

/**
 * Diálogo de confirmación inline (reemplaza a confirm() nativo).
 * Devuelve una Promise<boolean>.
 */
function showConfirmDialog(message, { confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', danger = true } = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.className = 'fixed inset-0 z-50 flex items-center justify-center p-4';
    overlay.innerHTML = `
      <div class="absolute inset-0 bg-black/40"></div>
      <div class="relative w-full max-w-sm bg-light-card dark:bg-dark-card rounded-xl border border-light-border dark:border-dark-border shadow-lg p-4 space-y-4">
        <p class="text-sm text-light-text-primary dark:text-dark-text-primary" data-role="message"></p>
        <div class="flex justify-end gap-2">
          <button type="button" class="px-3 py-2 rounded-lg border border-light-border dark:border-dark-border hover:bg-light-muted/30 dark:hover:bg-dark-muted/30 text-sm" data-action="cancel"></button>
          <button type="button" class="px-3 py-2 rounded-lg text-white text-sm ${danger ? 'bg-red-600 hover:bg-red-700' : 'bg-primary hover:opacity-90'}" data-action="confirm"></button>
        </div>
      </div>
    `;
    // Como texto y no como HTML: el mensaje incluye nombres de usuario o de
    // subgrupo (p. ej. "¿Eliminar a {{ member.user.name }}?"), que vienen del
    // perfil de quien se unió al grupo y no son de confianza.
    overlay.querySelector('[data-role="message"]').textContent = message;
    overlay.querySelector('[data-action="cancel"]').textContent = cancelLabel;
    overlay.querySelector('[data-action="confirm"]').textContent = confirmLabel;
    const close = (result) => {
      overlay.remove();
      document.removeEventListener('keydown', onKeydown);
      resolve(result);
    };
    const onKeydown = (e) => {
      if (e.key === 'Escape') close(false);
    };
    overlay.querySelector('[data-action="cancel"]')?.addEventListener('click', () => close(false));
    overlay.querySelector('[data-action="confirm"]')?.addEventListener('click', () => close(true));
    overlay.addEventListener('click', (e) => { if (e.target === overlay || e.target.classList.contains('bg-black/40')) close(false); });
    document.addEventListener('keydown', onKeydown);
    document.body.appendChild(overlay);
    overlay.querySelector('[data-action="confirm"]')?.focus();
  });
}

/**
 * Enlaza los formularios con data-confirm al diálogo inline.
 * Reemplaza a onsubmit="return confirm(...)" sin duplicar JS por plantilla.
 */
function initConfirmForms() {
  document.addEventListener('submit', async (event) => {
    const form = event.target;
    const message = form?.dataset?.confirm;
    if (!message || form.dataset.confirmed === 'true') return;

    event.preventDefault();
    const confirmed = await showConfirmDialog(message, {
      confirmLabel: form.dataset.confirmLabel || 'Confirmar',
    });
    if (!confirmed) return;

    form.dataset.confirmed = 'true';
    form.submit();
  });
}

/**
 * Copy invite link to clipboard
 */
function copyInviteLink(groupId) {
  const input = document.getElementById(`inviteLink-${groupId}`);
  if (!input) {
    showInlineAlert("No se encontró el enlace de invitación.", "danger");
    return;
  }

  const onCopied = () => {
    input.classList.add('ring-2', 'ring-primary', 'bg-green-50', 'dark:bg-green-900/20');
    setTimeout(() => {
      input.classList.remove('ring-2', 'ring-primary', 'bg-green-50', 'dark:bg-green-900/20');
    }, 1500);
    showInlineAlert("✓ Link de invitación copiado.", "success");
  };

  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(input.value).then(onCopied).catch(() => {
      input.select();
      input.setSelectionRange(0, 99999);
      document.execCommand('copy');
      onCopied();
    });
  } else {
    input.select();
    input.setSelectionRange(0, 99999);
    document.execCommand('copy');
    onCopied();
  }
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener("DOMContentLoaded", () => {
  // Prevenir ejecución múltiple
  if (globalThis.__MAIN_JS_INITIALIZED__) return;
  globalThis.__MAIN_JS_INITIALIZED__ = true;

  initConfirmForms();

  // Add smooth scroll to anchors
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const target = document.querySelector(this.getAttribute("href"));
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
  });
});

// ============================================
// EXPORT FUNCTIONS FOR GLOBAL USE
// ============================================
window.schedulerApp = {
  showInlineAlert,
  showConfirmDialog,
  copyInviteLink,
};
