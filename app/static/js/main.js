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
 * Show loading spinner overlay
 */
function showLoader(message = "Cargando...") {
  const existingLoader = document.getElementById("global-loader");
  if (existingLoader) return;

  const loader = document.createElement("div");
  loader.id = "global-loader";
  loader.className = "spinner-overlay fade-in";
  loader.innerHTML = `
    <div class="text-center">
      <div class="spinner-border text-light" role="status">
        <span class="visually-hidden">${message}</span>
      </div>
      <p class="text-light mt-3 fw-bold">${message}</p>
    </div>
  `;
  document.body.appendChild(loader);
}

/**
 * Hide loading spinner overlay
 */
function hideLoader() {
  const loader = document.getElementById("global-loader");
  if (loader) {
    loader.style.opacity = "0";
    setTimeout(() => loader.remove(), 300);
  }
}

/**
 * Show toast notification
 */
function showToast(message, type = "info", duration = 3000) {
  const toastContainer =
    document.getElementById("toast-container") || createToastContainer();

  const toastId = "toast-" + Date.now();
  const icons = {
    success: "✓",
    error: "✗",
    warning: "⚠",
    info: "ℹ",
  };

  const toast = document.createElement("div");
  toast.id = toastId;
  toast.className = `toast align-items-center text-white bg-${
    type === "error" ? "danger" : type
  } border-0 fade-in`;
  toast.setAttribute("role", "alert");
  toast.innerHTML = `
    <div class="d-flex">
      <div class="toast-body">
        <strong>${icons[type] || "ℹ"}</strong> ${message}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;

  toastContainer.appendChild(toast);
  const bsToast = new bootstrap.Toast(toast, {
    autohide: true,
    delay: duration,
  });
  bsToast.show();

  toast.addEventListener("hidden.bs.toast", () => toast.remove());
}

/**
 * Create toast container if it doesn't exist
 */
function createToastContainer() {
  const container = document.createElement("div");
  container.id = "toast-container";
  container.className = "toast-container position-fixed top-0 end-0 p-3";
  container.style.zIndex = "9999";
  document.body.appendChild(container);
  return container;
}

/**
 * Confirm action with modal
 */
function confirmAction(
  title,
  message,
  onConfirm,
  confirmText = "Confirmar",
  cancelText = "Cancelar"
) {
  const modalId = "confirm-modal-" + Date.now();
  const modal = document.createElement("div");
  modal.innerHTML = `
    <div class="modal fade" id="${modalId}" tabindex="-1">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">${title}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <p>${message}</p>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>
            <button type="button" class="btn btn-danger" id="confirm-btn">${confirmText}</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.appendChild(modal);
  const modalElement = document.getElementById(modalId);
  const bsModal = new bootstrap.Modal(modalElement);

  document.getElementById("confirm-btn").addEventListener("click", () => {
    bsModal.hide();
    onConfirm();
  });

  modalElement.addEventListener("hidden.bs.modal", () => modal.remove());
  bsModal.show();
}

/**
 * Copy text to clipboard with feedback
 */
async function copyToClipboard(
  text,
  successMessage = "Copiado al portapapeles"
) {
  try {
    await navigator.clipboard.writeText(text);
    showToast(successMessage, "success");
    return true;
  } catch (err) {
    showToast("Error al copiar", "error");
    return false;
  }
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

/**
 * Format date to locale string
 */
function formatDate(dateString, options = {}) {
  const date = new Date(dateString);
  const defaultOptions = {
    year: "numeric",
    month: "long",
    day: "numeric",
    ...options,
  };
  return date.toLocaleDateString("es-ES", defaultOptions);
}

/**
 * Debounce function for input events
 */
function debounce(func, wait = 300) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

/**
 * Validate email format
 */
function isValidEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

/**
 * Initialize tooltips
 */
function initTooltips() {
  const tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  tooltipTriggerList.map((el) => new bootstrap.Tooltip(el));
}

/**
 * Initialize popovers
 */
function initPopovers() {
  const popoverTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="popover"]')
  );
  popoverTriggerList.map((el) => new bootstrap.Popover(el));
}

/**
 * Add fade-in animation to elements
 */
function animateElements(selector = ".animate-on-load", delay = 100) {
  const elements = document.querySelectorAll(selector);
  elements.forEach((el, index) => {
    setTimeout(() => {
      el.classList.add("fade-in");
    }, index * delay);
  });
}

/**
 * Handle form submission with loader
 */
function handleFormSubmit(formSelector, loaderMessage = "Procesando...") {
  const forms = document.querySelectorAll(formSelector);
  forms.forEach((form) => {
    // Evitar agregar múltiples listeners al mismo formulario
    if (form.dataset.loaderInitialized === "true") return;
    form.dataset.loaderInitialized = "true";

    form.addEventListener("submit", (e) => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML =
          '<span class="spinner-border spinner-border-sm me-2"></span>Procesando...';
      }
      showLoader(loaderMessage);
    });
  });
}

/**
 * Enhanced delete confirmation
 */
function confirmDelete(itemName, deleteUrl, method = "POST") {
  confirmAction(
    "⚠️ Confirmar eliminación",
    `¿Estás seguro de que deseas eliminar "${itemName}"? Esta acción no se puede deshacer.`,
    async () => {
      showLoader("Eliminando...");
      try {
        const response = await fetch(deleteUrl, {
          method: method,
          headers: {
            "Content-Type": "application/json",
          },
        });

        if (response.ok) {
          showToast("Eliminado correctamente", "success");
          setTimeout(() => location.reload(), 1000);
        } else {
          showToast("Error al eliminar", "error");
        }
      } catch (error) {
        showToast("Error de conexión", "error");
      } finally {
        hideLoader();
      }
    },
    "Sí, eliminar",
    "Cancelar"
  );

  return false; // Prevent default form submission
}

// ============================================
// FORM ENHANCEMENTS
// ============================================

/**
 * Add real-time validation to forms
 */
function enhanceFormValidation() {
  const forms = document.querySelectorAll(".needs-validation");

  forms.forEach((form) => {
    // Evitar agregar múltiples listeners al mismo formulario
    if (form.dataset.validationInitialized === "true") return;
    form.dataset.validationInitialized = "true";

    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });

    // Real-time validation on input
    const inputs = form.querySelectorAll("input, textarea, select");
    inputs.forEach((input) => {
      input.addEventListener("blur", () => {
        if (input.checkValidity()) {
          input.classList.remove("is-invalid");
          input.classList.add("is-valid");
        } else {
          input.classList.remove("is-valid");
          input.classList.add("is-invalid");
        }
      });
    });
  });
}

/**
 * Auto-resize textarea
 */
function autoResizeTextarea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = textarea.scrollHeight + "px";
}

// ============================================
// AVAILABILITY CALENDAR ENHANCEMENTS
// ============================================

/**
 * Initialize availability calendar interactions
 */
function initAvailabilityCalendar() {
  const cells = document.querySelectorAll(".availability-cell");

  cells.forEach((cell) => {
    cell.addEventListener("click", function () {
      this.classList.toggle("selected");
      const checkbox = this.querySelector('input[type="checkbox"]');
      if (checkbox) {
        checkbox.checked = !checkbox.checked;
      }
    });

    // Add hover effects
    cell.addEventListener("mouseenter", function () {
      this.style.transform = "scale(1.02)";
    });

    cell.addEventListener("mouseleave", function () {
      this.style.transform = "scale(1)";
    });
  });
}

/**
 * Highlight available time slots
 */
function highlightAvailableSlots() {
  const slots = document.querySelectorAll(".availability-slot");
  slots.forEach((slot) => {
    const count = parseInt(slot.dataset.availableCount || 0);
    const total = parseInt(slot.dataset.totalMembers || 1);
    const percentage = (count / total) * 100;

    if (percentage === 100) {
      slot.classList.add("bg-success", "bg-opacity-25");
    } else if (percentage >= 50) {
      slot.classList.add("bg-warning", "bg-opacity-25");
    } else if (percentage > 0) {
      slot.classList.add("bg-info", "bg-opacity-25");
    }
  });
}

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener("DOMContentLoaded", () => {
  // Prevenir ejecución múltiple
  if (globalThis.__MAIN_JS_INITIALIZED__) return;
  globalThis.__MAIN_JS_INITIALIZED__ = true;

  // Initialize Bootstrap components
  initTooltips();
  initPopovers();

  // Enhance forms
  enhanceFormValidation();
  initConfirmForms();

  // Auto-resize textareas
  const textareas = document.querySelectorAll("textarea[data-auto-resize]");
  textareas.forEach((textarea) => {
    textarea.addEventListener("input", () => autoResizeTextarea(textarea));
    autoResizeTextarea(textarea);
  });

  // Animate elements on load
  animateElements(".card, .list-group-item");

  // Handle form submissions with loaders
  handleFormSubmit("form[data-loader]");

  // Initialize availability calendar if present
  if (document.querySelector(".availability-cell")) {
    initAvailabilityCalendar();
  }

  // Highlight available slots if present
  if (document.querySelector(".availability-slot")) {
    highlightAvailableSlots();
  }

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

  // Enhance tables with hover effect on rows
  const tableRows = document.querySelectorAll(".table tbody tr");
  tableRows.forEach((row) => {
    row.style.cursor = "pointer";
  });
});

// ============================================
// EXPORT FUNCTIONS FOR GLOBAL USE
// ============================================
window.schedulerApp = {
  showLoader,
  hideLoader,
  showToast,
  confirmAction,
  confirmDelete,
  copyToClipboard,
  copyInviteLink,
  formatDate,
  debounce,
  isValidEmail,
  initTooltips,
  initPopovers,
};
