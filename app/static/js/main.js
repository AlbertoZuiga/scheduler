/**
 * SCHEDULER - MAIN JAVASCRIPT
 * Utility functions and UI enhancements
 */

// ============================================
// GLOBAL UTILITIES
// ============================================

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
    showToast("No se encontró el enlace de invitación", "error");
    return;
  }

  copyToClipboard(input.value, "✓ Link de invitación copiado");
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
  // Initialize Bootstrap components
  initTooltips();
  initPopovers();

  // Enhance forms
  enhanceFormValidation();

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
