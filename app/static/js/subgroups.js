/**
 * JavaScript para el builder de reglas y división automática de subgrupos
 */

(function () {
  "use strict";

  let ruleCounter = 0;
  let currentJobId = null;

  // Referencias a elementos del DOM
  const form = document.getElementById("division-form");
  const addRuleBtn = document.getElementById("add-rule-btn");
  const rulesBuilder = document.getElementById("rules-builder");
  const noRulesMsg = document.getElementById("no-rules-msg");
  const previewPanel = document.getElementById("preview-panel");
  const previewContent = document.getElementById("preview-content");
  const loadingOverlay = document.getElementById("loading-overlay");
  const thresholdSlider = document.getElementById("compatibility_threshold");
  const thresholdDisplay = document.getElementById("threshold_display");

  // Botones de acción del preview
  const confirmBtn = document.getElementById("confirm-btn");
  const redoBtn = document.getElementById("redo-btn");
  const exportBtn = document.getElementById("export-btn");
  const undoBtn = document.getElementById("undo-btn");

  // Templates
  const ruleTemplate = document.getElementById("rule-template");
  const conditionTemplate = document.getElementById("condition-template");

  /**
   * Inicialización
   */
  function init() {
    // Event listeners
    thresholdSlider.addEventListener("input", updateThresholdDisplay);
    addRuleBtn.addEventListener("click", addRule);
    form.addEventListener("submit", handleFormSubmit);

    confirmBtn.addEventListener("click", confirmDivision);
    redoBtn.addEventListener("click", redoDivision);
    exportBtn.addEventListener("click", exportResults);
    undoBtn.addEventListener("click", undoLastDivision);

    updateThresholdDisplay();
  }

  /**
   * Actualiza el display del threshold
   */
  function updateThresholdDisplay() {
    thresholdDisplay.textContent = `${thresholdSlider.value}%`;
  }

  /**
   * Añade un nuevo requisito al builder
   */
  function addRule() {
    ruleCounter++;

    // Clonar template
    const ruleNode = ruleTemplate.content.cloneNode(true);
    const ruleDiv = ruleNode.querySelector(".rule-builder");

    // Configurar índice
    ruleDiv.setAttribute("data-rule-index", ruleCounter);
    const ruleNumbers = ruleDiv.querySelectorAll(".rule-number");
    ruleNumbers.forEach((el) => (el.textContent = ruleCounter));

    // Event listeners
    const removeBtn = ruleDiv.querySelector(".remove-rule-btn");
    removeBtn.addEventListener("click", () => removeRule(ruleDiv));

    // Añadir al builder
    rulesBuilder.appendChild(ruleDiv);

    // Ocultar mensaje de "no rules"
    if (noRulesMsg) {
      noRulesMsg.style.display = "none";
    }

    // Añadir el contenido del requisito (una "condición" por defecto)
    addCondition(ruleDiv);
  }

  /**
   * Remueve una regla
   */
  function removeRule(ruleDiv) {
    ruleDiv.remove();

    // Mostrar mensaje si no hay reglas
    const remainingRules = rulesBuilder.querySelectorAll(".rule-builder");
    if (remainingRules.length === 0 && noRulesMsg) {
      noRulesMsg.style.display = "block";
    }
  }

  /**
   * Añade el contenido de un requisito
   */
  function addCondition(ruleDiv) {
    const conditionsContainer = ruleDiv.querySelector(".conditions-container");

    // Clonar template de contenido (antes llamado "condición")
    const conditionNode = conditionTemplate.content.cloneNode(true);
    const conditionDiv = conditionNode.querySelector(".condition-group");

    conditionsContainer.appendChild(conditionDiv);
  }

  /**
   * Serializa el formulario a JSON
   */
  function serializeForm() {
    const config = {
      num_groups: parseInt(document.getElementById("num_groups").value),
      max_group_size:
        parseInt(document.getElementById("max_group_size").value) || null,
      allow_multiple_membership: document.getElementById(
        "allow_multiple_membership"
      ).checked,
      require_all_members: document.getElementById("require_all_members")
        .checked,
      compatibility_threshold: parseFloat(thresholdSlider.value) / 100,
      category_rules: [],
    };

    // Serializar reglas
    const rules = rulesBuilder.querySelectorAll(".rule-builder");

    rules.forEach((ruleDiv) => {
      const conditions = [];

      // Obtener condiciones
      const conditionDivs = ruleDiv.querySelectorAll(".condition-group");
      conditionDivs.forEach((condDiv) => {
        const categoriesSelect = condDiv.querySelector(".condition-categories");
        const operatorSelect = condDiv.querySelector(".condition-operator");
        const minInput = condDiv.querySelector(".condition-min");
        const maxInput = condDiv.querySelector(".condition-max");

        const selectedCategories = Array.from(
          categoriesSelect.selectedOptions
        ).map((opt) => opt.value);

        if (selectedCategories.length > 0) {
          const condition = {
            categories: selectedCategories,
            operator: operatorSelect.value,
            min: parseInt(minInput.value) || 0,
          };

          const maxValue = parseInt(maxInput.value);
          if (maxValue && maxValue > 0) {
            condition.max = maxValue;
          }

          conditions.push(condition);
        }
      });

      // Solo añadir la regla si tiene condiciones válidas
      if (conditions.length > 0) {
        config.category_rules.push({
          conditions: conditions,
        });
      }
    });

    return config;
  }

  /**
   * Maneja el submit del formulario
   */
  async function handleFormSubmit(e) {
    e.preventDefault();

    // Validar
    const numGroups = parseInt(document.getElementById("num_groups").value);
    if (numGroups < 2) {
      alert("Debe haber al menos 2 subgrupos.");
      return;
    }

    // Serializar configuración
    const config = serializeForm();

    // Mostrar loading
    showLoading();

    try {
      const response = await fetch(
        `/groups/${window.GROUP_ID}/subgroups/generate`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(config),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Error al generar subgrupos");
      }

      // Guardar job_id
      currentJobId = data.job_id;

      // Renderizar preview
      renderPreview(data);
    } catch (error) {
      alert(`Error: ${error.message}`);
      console.error(error);
    } finally {
      hideLoading();
    }
  }

  /**
   * Renderiza el preview de subgrupos
   */
  function renderPreview(data) {
    previewPanel.style.display = "block";

    let html = "";

    // Resumen general
    html += `
      <div class="alert alert-info mb-3">
        <h6><i class="bi bi-info-circle"></i> Resumen</h6>
        <p class="mb-1"><strong>Miembros asignados:</strong> ${
          data.total_members_assigned
        } de ${data.total_members_available}</p>
        <p class="mb-0"><strong>Reglas incumplidas:</strong> ${
          data.unfulfilled_rules.length > 0
            ? data.unfulfilled_rules.join(", ")
            : "Ninguna"
        }</p>
      </div>
    `;

    // Renderizar cada subgrupo
    data.groups.forEach((group, idx) => {
      const compatPercent = Math.round(group.compatibility_avg * 100);
      const compatColor = getCompatibilityColor(group.compatibility_avg);

      html += `
        <div class="rounded-lg border-2 mb-3 overflow-hidden shadow-md ${
          idx === 0
            ? "preview-card border-indigo-500 dark:border-indigo-400"
            : "border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
        }">
          <div class="px-4 py-3 font-semibold ${
            idx === 0
              ? "bg-indigo-100 dark:bg-indigo-900 text-indigo-900 dark:text-indigo-100 border-b-2 border-indigo-500 dark:border-indigo-400"
              : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100 border-b border-gray-300 dark:border-gray-600"
          }">
            <div class="flex items-center justify-between">
              <span class="flex items-center gap-2">
                <i class="bi bi-people-fill"></i> ${group.name}
              </span>
              <span class="inline-block px-3 py-1 rounded-full bg-gray-600 dark:bg-gray-500 text-white text-sm font-medium">${
                group.members.length
              } miembros</span>
            </div>
          </div>
          <div class="px-4 py-3 bg-white dark:bg-gray-800">
            <!-- Compatibilidad -->
            <div class="mb-3">
              <small class="text-gray-600 dark:text-gray-300 block mb-1">Compatibilidad Promedio: <strong class="text-gray-900 dark:text-white">${compatPercent}%</strong></small>
              <div class="compatibility-bar">
                <div class="compatibility-indicator" style="left: ${compatPercent}%"></div>
              </div>
            </div>
            
            <!-- Estado de Reglas -->
            ${
              group.rules_status.length > 0
                ? `
              <div class="mb-3">
                <small class="text-gray-600 dark:text-gray-300 block mb-1">Estado de Requisitos:</small>
                <div class="flex flex-wrap gap-2">
                  ${group.rules_status
                    .map(
                      (r) => `
                    <span class="rule-status-badge ${
                      r.fulfilled ? "rule-fulfilled" : "rule-unfulfilled"
                    }">
                      Requisito ${r.rule}: ${r.count}/${r.min}${
                        r.max ? "-" + r.max : "+"
                      } 
                      ${r.fulfilled ? "✓" : "✗"}
                    </span>
                  `
                    )
                    .join("")}
                </div>
              </div>
            `
                : ""
            }
            
            <!-- Lista de Miembros -->
            <div>
              <small class="text-gray-600 dark:text-gray-300 block mb-2">Miembros:</small>
              <div class="rounded border border-gray-300 dark:border-gray-600 overflow-hidden" style="max-height: 200px; overflow-y: auto;">
                ${group.members
                  .map(
                    (member) => `
                  <div class="px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
                    <div class="flex items-center gap-2 text-gray-900 dark:text-white font-medium">
                      <i class="bi bi-person"></i> ${member.name}
                    </div>
                    ${
                      member.categories.length > 0
                        ? `
                      <div class="flex flex-wrap gap-1 mt-2">
                        ${member.categories
                          .map(
                            (cat) =>
                              `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-100">${cat}</span>`
                          )
                          .join(" ")}
                      </div>
                    `
                        : ""
                    }
                  </div>
                `
                  )
                  .join("")}
              </div>
            </div>
          </div>
        </div>
      `;
    });

    previewContent.innerHTML = html;

    // Scroll al preview
    previewPanel.scrollIntoView({ behavior: "smooth" });
  }

  /**
   * Obtiene el color según la compatibilidad
   */
  function getCompatibilityColor(compat) {
    if (compat >= 0.7) return "#198754"; // verde
    if (compat >= 0.4) return "#ffc107"; // amarillo
    return "#dc3545"; // rojo
  }

  /**
   * Confirma la división y persiste en BD
   */
  async function confirmDivision() {
    if (!currentJobId) {
      alert("No hay división pendiente para confirmar.");
      return;
    }

    if (
      !confirm(
        "¿Estás seguro de confirmar esta división? Se crearán los subgrupos en la base de datos."
      )
    ) {
      return;
    }

    showLoading();

    try {
      const response = await fetch(
        `/groups/${window.GROUP_ID}/subgroups/confirm`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ job_id: currentJobId }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Error al confirmar");
      }

      alert("¡División confirmada exitosamente!");

      // Redirigir
      if (data.redirect_url) {
        window.location.href = data.redirect_url;
      }
    } catch (error) {
      alert(`Error: ${error.message}`);
      console.error(error);
    } finally {
      hideLoading();
    }
  }

  /**
   * Rehacer división (oculta preview y permite nueva configuración)
   */
  function redoDivision() {
    previewPanel.style.display = "none";
    currentJobId = null;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /**
   * Exporta resultados a CSV
   */
  function exportResults() {
    if (!currentJobId) {
      alert("No hay división para exportar.");
      return;
    }

    window.location.href = `/groups/${window.GROUP_ID}/subgroups/export?job_id=${currentJobId}`;
  }

  /**
   * Deshace la última división confirmada
   */
  async function undoLastDivision() {
    if (
      !confirm(
        "¿Estás seguro de deshacer la última división confirmada? Esto eliminará todos los subgrupos creados."
      )
    ) {
      return;
    }

    showLoading();

    try {
      const response = await fetch(
        `/groups/${window.GROUP_ID}/subgroups/undo`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Error al deshacer");
      }

      alert(data.message || "¡División deshecha exitosamente!");

      // Ocultar preview y limpiar
      previewPanel.style.display = "none";
      currentJobId = null;
    } catch (error) {
      alert(`Error: ${error.message}`);
      console.error(error);
    } finally {
      hideLoading();
    }
  }

  /**
   * Muestra el overlay de loading
   */
  function showLoading() {
    loadingOverlay.style.display = "flex";
  }

  /**
   * Oculta el overlay de loading
   */
  function hideLoading() {
    loadingOverlay.style.display = "none";
  }

  // Inicializar cuando el DOM esté listo
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
