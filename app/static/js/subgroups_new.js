// Leer datos del servidor inyectados como JSON en el DOM
const _groupData = JSON.parse(document.getElementById('group-data').textContent);
globalThis.GROUP_ID = _groupData.groupId;
globalThis.CATEGORIES = _groupData.categories;
globalThis.MEMBERS = _groupData.members;

document.addEventListener('DOMContentLoaded', function () {
  const numGroups = document.getElementById('num_groups');
  const maxGroupSize = document.getElementById('max_group_size');
  const threshold = document.getElementById('compatibility_threshold');
  const summaryNumGroups = document.getElementById('summary-num-groups');
  const summaryMaxSize = document.getElementById('summary-max-size');
  const summaryThreshold = document.getElementById('summary-threshold');
  const summaryTogetherGroups = document.getElementById('summary-together-groups');
  const requireAllMembers = document.getElementById('require_all_members');
  const requiredCategoriesContainer = document.getElementById('required-categories-container');

  function toggleRequiredCategories() {
    if (!requiredCategoriesContainer || !requireAllMembers) return;
    requiredCategoriesContainer.classList.toggle('hidden', requireAllMembers.checked);
  }

  function updateSummary() {
    summaryNumGroups.innerHTML = 'Subgrupos: <b>' + (numGroups.value || '-') + '</b>';
    summaryMaxSize.innerHTML = 'Máx. por subgrupo: <b>' + (maxGroupSize.value || 'Sin límite') + '</b>';
    summaryThreshold.innerHTML = 'Compatibilidad mínima: <b>' + (threshold.value || '-') + ' bloques</b>';
    const manualCount = document.querySelectorAll('#together-groups-list .together-group-chip').length;
    if (summaryTogetherGroups) summaryTogetherGroups.innerHTML = 'Grupos juntos: <b>' + manualCount + '</b>';
  }
  if (numGroups) numGroups.addEventListener('input', updateSummary);
  if (maxGroupSize) maxGroupSize.addEventListener('input', updateSummary);
  if (threshold) threshold.addEventListener('input', updateSummary);
  if (requireAllMembers) requireAllMembers.addEventListener('change', toggleRequiredCategories);
  updateSummary();
  toggleRequiredCategories();

  const requiredCategoriesSelect = document.getElementById('required_membership_categories');
  for (const chip of document.querySelectorAll('.required-category-chip')) {
    chip.addEventListener('click', () => {
      const option = Array.from(requiredCategoriesSelect?.options || []).find((opt) => opt.value === chip.dataset.value);
      if (!option) return;
      option.selected = !option.selected;
      chip.classList.toggle('bg-sky-600', option.selected);
      chip.classList.toggle('text-white', option.selected);
      chip.classList.toggle('border-sky-600', option.selected);
    });
  }

  // Reemplaza __IDX__ por un índice único al clonar el template de condición
  const rulesBuilder = document.getElementById('rules-builder');
  if (!rulesBuilder) return;
  let condCounter = 0;
  rulesBuilder.addEventListener('click', function (e) {
    if (e.target.closest('.add-condition-btn')) {
      setTimeout(() => {
        const lastCond = rulesBuilder.querySelectorAll('.condition-group');
        if (lastCond.length) {
          const cond = lastCond.at(-1);
          cond.innerHTML = cond.innerHTML.replaceAll('__IDX__', condCounter);
          condCounter++;
        }
      }, 10);
    }
  });
});
