  globalThis.__EMBED__ = JSON.parse(document.getElementById('embed-data').textContent || '{}');
  globalThis.GROUP_ID = globalThis.__EMBED__.group_id;
  globalThis.CAN_MANAGE = !!globalThis.__EMBED__.can_manage;
  globalThis.CAN_VIEW_AVAILABILITY = !!globalThis.__EMBED__.can_view_availability;
  globalThis.__GROUP_MEMBERS__ = globalThis.__EMBED__.members || [];

  function setupScheduleFiltering() {
    const chips = Array.from(document.querySelectorAll('.availability-user-chip'));
    const missingUserItems = Array.from(document.querySelectorAll('.availability-missing-user'));
    const filterButtons = Array.from(document.querySelectorAll('.schedule-filter-chip'));
    for (const button of filterButtons) button.setAttribute('aria-pressed', 'false');
    const filterModeSelect = document.getElementById('scheduleFilterMode');
    const stats = document.getElementById('scheduleFilterStats');
    const allList = document.getElementById('availabilityAllList');
    const partialList = document.getElementById('availabilityPartialList');
    const missingUsersFilterEmpty = document.getElementById('availabilityMissingUsersFilterEmpty');
    if (filterButtons.length === 0) {
      return;
    }

    const userToGroupMember = globalThis.__EMBED__.user_gm_map || {};
    const memberToCategories = globalThis.__EMBED__.member_category_map || {};
    const userToSubgroups = globalThis.__EMBED__.user_subgroup_map || {};
    const availabilityRows = Array.isArray(globalThis.__EMBED__.availability) ? globalThis.__EMBED__.availability : [];
    const respondedUserIds = new Set(
      (Array.isArray(globalThis.__EMBED__.responded_user_ids) ? globalThis.__EMBED__.responded_user_ids : [])
        .map((value) => Number.parseInt(value))
        .filter((value) => Number.isInteger(value))
    );

    const selectedCategoryIds = new Set();
    const selectedSubgroupIds = new Set();
    let includeNoCategory = false;
    let includeNoSubgroup = false;
    let filterMode = (filterModeSelect?.value || 'or').toLowerCase() === 'and' ? 'and' : 'or';

    const weekdayNames = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
    const memberByUserId = new Map(
      (globalThis.__GROUP_MEMBERS__ || []).map((member) => [Number.parseInt(member.user_id), member])
    );

    const activePalette = [
      'bg-blue-600 text-white border-blue-600 ring-2 ring-blue-200 dark:ring-blue-900/40',
      'bg-green-600 text-white border-green-600 ring-2 ring-green-200 dark:ring-green-900/40',
      'bg-amber-500 text-white border-amber-500 ring-2 ring-amber-200 dark:ring-amber-700',
      'bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-200 dark:ring-indigo-900/40',
      'bg-teal-600 text-white border-teal-600 ring-2 ring-teal-300 dark:ring-teal-900/40',
      'bg-purple-600 text-white border-purple-600 ring-2 ring-purple-200 dark:ring-purple-900/40',
    ];
    const neutralActiveStyles = 'bg-primary text-white border-primary ring-2 ring-amber-200 dark:ring-amber-700';

    const normalizeIdList = (values) => {
      if (!Array.isArray(values)) {
        return [];
      }
      return values
        .map((value) => Number.parseInt(value))
        .filter((value) => Number.isInteger(value));
    };

    const getCategoryIdsByUserId = (userId) => {
      const gmId = userToGroupMember[String(userId)] ?? userToGroupMember[userId];
      if (!gmId) return [];
      const categories = memberToCategories[String(gmId)] ?? memberToCategories[gmId] ?? [];
      return normalizeIdList(categories);
    };

    const getSubgroupIdsByUserId = (userId) => {
      const subgroups = userToSubgroups[String(userId)] ?? userToSubgroups[userId] ?? [];
      return normalizeIdList(subgroups);
    };

    const matchesFilterGroup = (values, selectedValues, includeEmptyValue) => {
      if (selectedValues.size === 0 && !includeEmptyValue) {
        return true;
      }

      const normalizedValues = normalizeIdList(values);
      const hasNoValue = normalizedValues.length === 0;
      const conditions = [];

      for (const selectedValue of selectedValues) {
        conditions.push(normalizedValues.includes(selectedValue));
      }
      if (includeEmptyValue) {
        conditions.push(hasNoValue);
      }

      if (conditions.length === 0) {
        return true;
      }

      return filterMode === 'and'
        ? conditions.every(Boolean)
        : conditions.some(Boolean);
    };

    const userMatchesSelectedFilters = (userId) => {
      const hasCategoryFilters = selectedCategoryIds.size > 0 || includeNoCategory;
      const hasSubgroupFilters = selectedSubgroupIds.size > 0 || includeNoSubgroup;

      if (!hasCategoryFilters && !hasSubgroupFilters) {
        return true;
      }

      const matchesCategories = matchesFilterGroup(
        getCategoryIdsByUserId(userId),
        selectedCategoryIds,
        includeNoCategory
      );
      const matchesSubgroups = matchesFilterGroup(
        getSubgroupIdsByUserId(userId),
        selectedSubgroupIds,
        includeNoSubgroup
      );

      if (hasCategoryFilters && hasSubgroupFilters) {
        return matchesCategories && matchesSubgroups;
      }

      return hasCategoryFilters ? matchesCategories : matchesSubgroups;
    };

    const buildUserVisibilityMap = () => {
      const visibility = new Map();
      for (const member of (globalThis.__GROUP_MEMBERS__ || [])) {
        const userId = Number.parseInt(member.user_id);
        if (!Number.isInteger(userId) || !respondedUserIds.has(userId)) continue;
        visibility.set(userId, userMatchesSelectedFilters(userId));
      }
      return visibility;
    };

    const toTimeString = (startMinutes) => {
      const h = Math.floor(startMinutes / 60);
      const m = startMinutes % 60;
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    };

    const paintButtonAsActive = (button) => {
      const colorIndex = Number.parseInt(button.dataset.filterColorIndex);
      const style = activePalette[(Number.isInteger(colorIndex) ? colorIndex : 0) % activePalette.length];
      button.classList.add(...style.split(' '));
      button.setAttribute('aria-pressed', 'true');
    };

    const paintNeutralButtonAsActive = (button) => {
      button.classList.add(...neutralActiveStyles.split(' '));
      button.setAttribute('aria-pressed', 'true');
    };

    const clearButtonActiveStyles = (button) => {
      for (const style of activePalette) {
        button.classList.remove(...style.split(' '));
      }
      button.classList.remove(...neutralActiveStyles.split(' '));
      button.setAttribute('aria-pressed', 'false');
    };

    const buildFilteredAvailability = (filteredUsers) => {
      const availabilityBySlot = new Map();

      for (const [userId, weekday, startMinutes] of availabilityRows) {
        const parsedUserId = Number.parseInt(userId);
        const parsedWeekday = Number.parseInt(weekday);
        const parsedMinutes = Number.parseInt(startMinutes);
        if (!Number.isInteger(parsedUserId) || !Number.isInteger(parsedWeekday) || !Number.isInteger(parsedMinutes)) {
          continue;
        }

        if (!filteredUsers.has(parsedUserId)) {
          continue;
        }

        const key = `${parsedWeekday}|${parsedMinutes}`;
        if (!availabilityBySlot.has(key)) {
          availabilityBySlot.set(key, new Set());
        }
        availabilityBySlot.get(key).add(parsedUserId);
      }

      return availabilityBySlot;
    };

    const renderAllSection = (availabilityBySlot, filteredCount) => {
      if (!allList) return;
      allList.innerHTML = '';

      if (filteredCount === 0) {
        allList.innerHTML = '<li class="text-xs text-light-text-secondary dark:text-dark-text-secondary">No hay usuarios que coincidan con el filtro.</li>';
        return;
      }

      const allSlots = [];
      for (const [slot, users] of availabilityBySlot.entries()) {
        if (users.size === filteredCount) {
          const [weekday, startMinutes] = slot.split('|');
          allSlots.push({ weekday: Number.parseInt(weekday), startMinutes: Number.parseInt(startMinutes) });
        }
      }

      allSlots.sort((a, b) => (a.weekday - b.weekday) || (a.startMinutes - b.startMinutes));

      if (allSlots.length === 0) {
        allList.innerHTML = '<li class="text-xs text-light-text-secondary dark:text-dark-text-secondary">No hay bloques donde puedan todos los usuarios filtrados.</li>';
        return;
      }

      for (const slot of allSlots) {
        const li = document.createElement('li');
        li.textContent = `${weekdayNames[slot.weekday]} ${toTimeString(slot.startMinutes)}`;
        allList.appendChild(li);
      }
    };

    const renderPartialSection = (availabilityBySlot, filteredUsers) => {
      if (!partialList) return;
      partialList.innerHTML = '';

      const filteredCount = filteredUsers.size;
      if (filteredCount === 0) {
        partialList.innerHTML = '<div class="text-xs text-light-text-secondary dark:text-dark-text-secondary">No hay usuarios que coincidan con el filtro.</div>';
        return;
      }

      const partialSlots = [];
      for (const [slot, users] of availabilityBySlot.entries()) {
        if (users.size > 0 && users.size < filteredCount) {
          const [weekday, startMinutes] = slot.split('|');
          partialSlots.push({ weekday: Number.parseInt(weekday), startMinutes: Number.parseInt(startMinutes), users: Array.from(users) });
        }
      }

      partialSlots.sort((a, b) => {
        const byCount = b.users.length - a.users.length;
        if (byCount !== 0) return byCount;
        return (a.weekday - b.weekday) || (a.startMinutes - b.startMinutes);
      });

      if (partialSlots.length === 0) {
        partialList.innerHTML = '<div class="text-xs text-light-text-secondary dark:text-dark-text-secondary">No hay bloques parciales con los filtros actuales.</div>';
        return;
      }

      for (const slot of partialSlots) {
        const details = document.createElement('details');
        details.className = 'bg-light-surface dark:bg-dark-surface border border-light-border dark:border-dark-border rounded p-3';

        const summary = document.createElement('summary');
        summary.className = 'cursor-pointer text-sm';
        const count = slot.users.length;
        summary.textContent = `${weekdayNames[slot.weekday]} ${toTimeString(slot.startMinutes)} — ${count} ${count === 1 ? 'persona disponible' : 'personas disponibles'}`;
        details.appendChild(summary);

        const ul = document.createElement('ul');
        ul.className = 'mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2';
        for (const userId of slot.users) {
          const li = document.createElement('li');
          const member = memberByUserId.get(Number.parseInt(userId));
          const label = document.createElement('span');
          label.className = 'inline-block text-xs px-2 py-1 rounded bg-light-muted/40 dark:bg-dark-muted/40';
          label.textContent = member ? `${member.name} ${member.email || ''}`.trim() : `Usuario ${userId}`;
          li.appendChild(label);
          ul.appendChild(li);
        }
        details.appendChild(ul);
        partialList.appendChild(details);
      }
    };

    const resetTableCellVisuals = () => {
      for (const cell of document.querySelectorAll('td .schedule-cell-body')) {
        cell.classList.remove('hidden');
        const wrapper = cell.closest('td');
        if (wrapper) {
          wrapper.classList.remove('bg-light-muted/20', 'dark:bg-dark-muted/20');
        }
      }
    };

    const updateVisibleScheduleUsers = (visibilityByUser) => {
      const filteredUsers = new Set();
      let visibleChips = 0;

      for (const chip of chips) {
        const userId = Number.parseInt(chip.dataset.userId);
        const show = visibilityByUser.get(userId) === true;
        chip.style.display = show ? '' : 'none';

        if (show && Number.isInteger(userId)) {
          filteredUsers.add(userId);
          visibleChips += 1;
        }
      }

      return { filteredUsers, visibleChips };
    };

    const updateVisibleMissingUsers = () => {
      let visibleMissingUsers = 0;

      for (const missingUserItem of missingUserItems) {
        const userId = Number.parseInt(missingUserItem.dataset.userId);
        const show = userMatchesSelectedFilters(userId);
        missingUserItem.classList.toggle('hidden', !show);
        if (show) {
          visibleMissingUsers += 1;
        }
      }

      if (missingUsersFilterEmpty) {
        missingUsersFilterEmpty.classList.toggle('hidden', visibleMissingUsers > 0);
      }

      return visibleMissingUsers;
    };

    const updateFilterStats = (visibleChips, visibleMissingUsers) => {
      if (!stats) {
        return;
      }

      const categoryCount = selectedCategoryIds.size + (includeNoCategory ? 1 : 0);
      const subgroupCount = selectedSubgroupIds.size + (includeNoSubgroup ? 1 : 0);
      const totalActiveCount = categoryCount + subgroupCount;
      stats.textContent = totalActiveCount > 0
        ? `${visibleChips} coincidencia(s) en horarios y ${visibleMissingUsers} sin horario con ${totalActiveCount} filtro(s) en modo ${filterMode.toUpperCase()}`
        : 'Sin filtros activos';
    };

    const applyFilters = () => {
      const visibilityByUser = buildUserVisibilityMap();
      const { filteredUsers, visibleChips } = updateVisibleScheduleUsers(visibilityByUser);
      const visibleMissingUsers = updateVisibleMissingUsers();

      // En la grilla solo ocultamos nombres que no cumplen filtro, sin cambiar fondo de celdas.
      resetTableCellVisuals();

      const availabilityBySlot = buildFilteredAvailability(filteredUsers);
      renderAllSection(availabilityBySlot, filteredUsers.size);
      renderPartialSection(availabilityBySlot, filteredUsers);

      updateFilterStats(visibleChips, visibleMissingUsers);
    };

    filterModeSelect?.addEventListener('change', () => {
      filterMode = (filterModeSelect.value || 'or').toLowerCase() === 'and' ? 'and' : 'or';
      applyFilters();
    });

    for (const button of filterButtons) {
      button.addEventListener('click', () => {
        if (button.dataset.scheduleFilterNone === 'true') {
          includeNoCategory = !includeNoCategory;
          clearButtonActiveStyles(button);
          if (includeNoCategory) {
            paintNeutralButtonAsActive(button);
          }
          applyFilters();
          return;
        }

        if (button.dataset.scheduleFilterNoSubgroup === 'true') {
          includeNoSubgroup = !includeNoSubgroup;
          clearButtonActiveStyles(button);
          if (includeNoSubgroup) {
            paintNeutralButtonAsActive(button);
          }
          applyFilters();
          return;
        }

        const subgroupId = Number.parseInt(button.dataset.scheduleFilterSubgroup);
        if (Number.isInteger(subgroupId)) {
          if (selectedSubgroupIds.has(subgroupId)) {
            selectedSubgroupIds.delete(subgroupId);
            clearButtonActiveStyles(button);
          } else {
            selectedSubgroupIds.add(subgroupId);
            paintButtonAsActive(button);
          }
          applyFilters();
          return;
        }

        const categoryId = Number.parseInt(button.dataset.scheduleFilterCategory);
        if (!Number.isInteger(categoryId)) return;
        if (selectedCategoryIds.has(categoryId)) {
          selectedCategoryIds.delete(categoryId);
          clearButtonActiveStyles(button);
        } else {
          selectedCategoryIds.add(categoryId);
          paintButtonAsActive(button);
        }
        applyFilters();
      });
    }

    document.getElementById('clearScheduleFilters')?.addEventListener('click', () => {
      selectedCategoryIds.clear();
      selectedSubgroupIds.clear();
      includeNoCategory = false;
      includeNoSubgroup = false;
      filterMode = 'or';
      if (filterModeSelect) {
        filterModeSelect.value = 'or';
      }
      for (const button of filterButtons) {
        clearButtonActiveStyles(button);
      }
      applyFilters();
    });

    applyFilters();
  }

  function memberNameByGmId(gmId) {
    const m = (globalThis.__GROUP_MEMBERS__ || []).find(x => Number.parseInt(x.group_member_id) === Number.parseInt(gmId));
    return m ? (m.name || m.email) : `Miembro ${gmId}`;
  }

  async function loadCategories() {
  const list = document.getElementById('categoriesList');
  list.innerHTML = '<div class="text-light-text-secondary dark:text-dark-text-secondary">Cargando categorías…</div>';
    try {
      const res = await fetch(`/categories/group/${globalThis.GROUP_ID}`, { headers: { 'Accept': 'application/json' } });
      if (!res.ok) throw new Error('Error al cargar categorías');
      const data = await res.json();
      if (!Array.isArray(data)) { list.innerHTML = '<span class="text-light-text-secondary dark:text-dark-text-secondary">Sin datos</span>'; return; }
      if (data.length === 0) { list.innerHTML = '<span class="text-light-text-secondary dark:text-dark-text-secondary">No hay categorías aún.</span>'; return; }
      list.innerHTML = '';
      for (const c of data) {
        const count = Array.isArray(c.member_ids) ? c.member_ids.length : (c.count || 0);
        const card = document.createElement('div');
        card.className = 'bg-light-card dark:bg-dark-card rounded-lg border border-light-border dark:border-dark-border shadow p-4 flex flex-col gap-2';
        card.innerHTML = `
          <div class="flex items-center justify-between">
            <h3 class="font-semibold" data-category-name></h3>
            <div class="flex items-center gap-2">
              <span class="inline-flex items-center justify-center w-6 h-6 text-xs rounded-full bg-light-muted/40 dark:bg-dark-muted/40 text-light-text-primary dark:text-dark-text-primary">${count}</span>
              ${globalThis.CAN_MANAGE ? '<button class="px-2 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 delete-category-btn">Eliminar</button>' : ''}
            </div>
          </div>
          <div data-category-members></div>`;

        card.querySelector('[data-category-name]').textContent = c.name;

        const membersBox = card.querySelector('[data-category-members]');
        const memberIds = c.member_ids || [];
        if (memberIds.length === 0) {
          const empty = document.createElement('span');
          empty.className = 'text-light-text-secondary dark:text-dark-text-secondary';
          empty.textContent = 'Sin miembros asignados';
          membersBox.appendChild(empty);
        } else {
          for (const gmId of memberIds) {
            const badge = document.createElement('span');
            badge.className = 'inline-block text-xs rounded px-2 py-1 bg-light-muted/40 dark:bg-dark-muted/40 text-light-text-primary dark:text-dark-text-primary mr-1 mb-1';
            badge.textContent = memberNameByGmId(gmId);
            membersBox.append(badge, ' ');
          }
        }

        card.dataset.categoryCard = c.id;
        const deleteBtn = card.querySelector('.delete-category-btn');
        if (deleteBtn) {
          deleteBtn.dataset.categoryId = c.id;
          deleteBtn.dataset.categoryName = c.name;
        }
        list.appendChild(card);
      }
    } catch (err) {
      console.error('Error loading categories:', err);
      list.innerHTML = '<span class="text-red-600">Error al cargar categorías</span>';
    }
  }

  document.getElementById('categoriesList')?.addEventListener('click', (event) => {
    const btn = event.target.closest('.delete-category-btn');
    if (!btn) return;
    deleteCategory(btn.dataset.categoryId, btn.dataset.categoryName);
  });

  async function deleteCategory(catId, catName) {
    const confirmed = await showConfirmDialog(`¿Eliminar la categoría "${catName}"? Se desasociarán todos los miembros.`);
    if (!confirmed) return;
    try {
      const res = await fetch(`/categories/group/${globalThis.GROUP_ID}/${catId}`, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        }
      });
      if (res.ok) {
        showInlineAlert(`Categoría "${catName}" eliminada.`, 'success');
        // El chip de filtro viene del servidor: si no se saca acá, queda
        // filtrando por una categoría que ya no existe hasta recargar.
        document.querySelector(`[data-schedule-filter-category="${catId}"]`)?.remove();
        await loadCategories();
      } else {
        const data = await res.json().catch(() => ({}));
        showInlineAlert(data.message || 'No se pudo eliminar la categoría.', 'danger');
      }
    } catch (err) {
      console.error('Error deleting category:', err);
      showInlineAlert('Error al eliminar la categoría.', 'danger');
    }
  }

  let checkTimer = null;
  function setupCategoryCreate() {
    if (!globalThis.CAN_MANAGE) return;
    const input = document.getElementById('newCategoryName');
    const feedback = document.getElementById('nameFeedback');
    const btn = document.getElementById('createCategoryBtn');
    const form = document.getElementById('createCategoryForm');

    if (form?.dataset.initialized === 'true') return;
    if (form) form.dataset.initialized = 'true';

    const updateBtn = (enabled) => { btn.disabled = !enabled; };
    const validate = async () => {
      const name = (input.value || '').trim();
      if (!name) { feedback.textContent = ''; updateBtn(false); return; }
      const res = await fetch(`/categories/group/${globalThis.GROUP_ID}/check?name=${encodeURIComponent(name)}`);
      const data = await res.json();
      if (data.available) {
        feedback.textContent = 'Disponible';
        feedback.className = 'form-text text-success';
        updateBtn(true);
      } else {
        feedback.textContent = data.message || 'No disponible';
        feedback.className = 'form-text text-danger';
        updateBtn(false);
      }
    };
    input?.addEventListener('input', () => {
      clearTimeout(checkTimer);
      checkTimer = setTimeout(validate, 300);
    });
    form?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = (input.value || '').trim();
      if (!name) { return; }
      const res = await fetch(`/categories/group/${globalThis.GROUP_ID}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
      if (res.ok) {
        input.value = '';
        feedback.textContent = '';
        updateBtn(false);
        showInlineAlert('Categoría creada correctamente.','success');
        await loadCategories();
      } else {
        const data = await res.json().catch(() => ({}));
        showInlineAlert(data.message || 'No se pudo crear la categoría.','danger');
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    // Las categorías ya vienen renderizadas por el servidor; loadCategories()
    // solo se usa para refrescar tras crear/eliminar.
    setupCategoryCreate();
    setupScheduleFiltering();
  });
