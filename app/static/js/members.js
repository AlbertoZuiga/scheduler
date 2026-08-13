document.addEventListener('DOMContentLoaded', () => {
    const data = JSON.parse(document.getElementById('members-embed-data').textContent || '{}');
    const groupId = Number.parseInt(data.group_id);
    const canManage = !!data.can_manage;
    const categories = Array.isArray(data.categories) ? data.categories : [];
    const members = Array.isArray(data.members) ? data.members : [];

    const colorPalette = [
      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200',
      'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-200',
      'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-200',
      'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-200',
      'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-200',
      'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-200'
    ];

    const membersById = new Map(members.map((m) => [Number.parseInt(m.group_member_id), {
      ...m,
      categories: Array.isArray(m.categories) ? m.categories.map((id) => Number.parseInt(id)) : []
    }]));
    const categoryById = new Map(categories.map((c) => [Number.parseInt(c.id), c]));

    const selectedFilters = new Set();
    let includeNoCategory = false;
    let searchTerm = '';
    let categoryFilterMode = 'or';
    let showSelectedOnly = false;
    const selectedMembers = new Set();
    const selectedBulkCategories = new Set();

    const activeFilterPalette = [
      'bg-blue-600 text-white border-blue-600 ring-2 ring-blue-200 dark:ring-blue-900/40',
      'bg-green-600 text-white border-green-600 ring-2 ring-green-200 dark:ring-green-900/40',
      'bg-amber-500 text-white border-amber-500 ring-2 ring-amber-200 dark:ring-amber-700',
      'bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-200 dark:ring-indigo-900/40',
      'bg-teal-600 text-white border-teal-600 ring-2 ring-teal-300 dark:ring-teal-900/40',
      'bg-purple-600 text-white border-purple-600 ring-2 ring-purple-200 dark:ring-purple-900/40',
    ];

    function getCategoryStyle(categoryId) {
      return colorPalette[Number.parseInt(categoryId) % colorPalette.length];
    }

    function paintFilterAsActive(button) {
      const id = Number.parseInt(button.dataset.filterCategoryId || '0');
      const style = activeFilterPalette[Math.abs(id) % activeFilterPalette.length];
      button.classList.add(...style.split(' '));
      button.setAttribute('aria-pressed', 'true');
    }

    function clearFilterActiveStyles(button) {
      for (const style of activeFilterPalette) {
        button.classList.remove(...style.split(' '));
      }
      button.classList.remove('bg-primary', 'text-white', 'border-primary', 'ring-2', 'ring-amber-200', 'dark:ring-amber-700');
      button.setAttribute('aria-pressed', 'false');
    }

    function categoryName(categoryId) {
      return categoryById.get(Number.parseInt(categoryId))?.name || `Categoría ${categoryId}`;
    }

    const normalizeForSearch = (value) => String(value || '')
      .normalize('NFD')
      .replaceAll(/[̀-ͯ]/g, '')
      .toLowerCase();

    const tokenizeSearch = (value) => normalizeForSearch(value)
        .split(/\s+/)
        .map((token) => token.trim())
        .filter(Boolean);

    function updateRowDataset(memberId) {
      const row = document.querySelector(`.member-row[data-member-id="${memberId}"]`);
      const member = membersById.get(Number.parseInt(memberId));
      if (!row || !member) return;
      row.dataset.categoryIds = member.categories.join(',');
    }

    function renderMemberChips(memberId) {
      const member = membersById.get(Number.parseInt(memberId));
      const container = document.querySelector(`[data-member-chips="${memberId}"]`);
      if (!member || !container) return;

      container.innerHTML = '';
      if (member.categories.length === 0) {
        const empty = document.createElement('span');
        empty.className = 'member-empty-cat text-xs text-light-text-secondary dark:text-dark-text-secondary';
        empty.textContent = 'Sin categorías';
        container.appendChild(empty);
      } else {
        for (const categoryId of member.categories) {
          const chip = document.createElement('button');
          chip.type = 'button';
          chip.dataset.memberId = memberId;
          chip.dataset.categoryId = categoryId;
          chip.className = `member-cat-chip inline-flex items-center gap-1 text-xs rounded-full px-2 py-1 border border-light-border dark:border-dark-border ${getCategoryStyle(categoryId)} ${member.can_edit_categories ? 'cursor-pointer' : 'cursor-default'}`;
          chip.title = member.can_edit_categories ? 'Click para quitar' : 'Categoría asignada';
          chip.disabled = !member.can_edit_categories;
          const chipLabel = document.createElement('span');
          chipLabel.textContent = categoryName(categoryId);
          chip.appendChild(chipLabel);
          if (member.can_edit_categories) {
            const chipRemove = document.createElement('span');
            chipRemove.setAttribute('aria-hidden', 'true');
            chipRemove.textContent = 'x';
            chip.appendChild(chipRemove);
          }
          container.appendChild(chip);
        }
      }

      updateRowDataset(memberId);
      applyFilters();
    }

    async function updateCategory(memberId, categoryId, shouldAssign) {
      const member = membersById.get(Number.parseInt(memberId));
      if (!member) return;
      const hasCategory = member.categories.includes(Number.parseInt(categoryId));
      if (shouldAssign && hasCategory) return;
      if (!shouldAssign && !hasCategory) return;

      const optimistic = shouldAssign
        ? [...member.categories, Number.parseInt(categoryId)]
        : member.categories.filter((id) => id !== Number.parseInt(categoryId));

      const previous = [...member.categories];
      member.categories = optimistic;
      renderMemberChips(memberId);

      try {
        const endpoint = `/categories/group_member/${memberId}`;
        const response = await fetch(endpoint, {
          method: shouldAssign ? 'POST' : 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify({ category_id: Number.parseInt(categoryId) })
        });

        if (!response.ok) {
          member.categories = previous;
          renderMemberChips(memberId);
          const errorBody = await response.json().catch(() => ({}));
          showInlineAlert(errorBody.message || 'No se pudo actualizar la categoría.', 'danger');
          return;
        }

        showInlineAlert(shouldAssign ? 'Categoría agregada.' : 'Categoría removida.', 'success');
      } catch (error) {
        console.error('updateCategory error:', error);
        member.categories = previous;
        renderMemberChips(memberId);
        showInlineAlert('Error de red al actualizar la categoría.', 'danger');
      }
    }

    function memberMatches(member) {
      const searchable = normalizeForSearch(`${member.name} ${member.email}`);
      const searchTokens = tokenizeSearch(searchTerm);
      if (searchTokens.length > 0) {
        const matchesText = searchTokens.every((token) => searchable.includes(token));
        if (!matchesText) {
          return false;
        }
      }

      if (showSelectedOnly && canManage && !selectedMembers.has(Number.parseInt(member.group_member_id))) {
        return false;
      }

      if (selectedFilters.size === 0 && !includeNoCategory) {
        return true;
      }

      const hasNoCategory = member.categories.length === 0;
      const conditions = [];

      for (const categoryId of selectedFilters) {
        conditions.push(member.categories.includes(categoryId));
      }
      if (includeNoCategory) {
        conditions.push(hasNoCategory);
      }

      if (conditions.length === 0) {
        return true;
      }

      return categoryFilterMode === 'and'
        ? conditions.every(Boolean)
        : conditions.some(Boolean);
    }

    function applyFilters() {
      const rows = Array.from(document.querySelectorAll('.member-row'));
      let visible = 0;

      for (const row of rows) {
        const memberId = Number.parseInt(row.dataset.memberId);
        const member = membersById.get(memberId);
        if (!member) continue;
        const isVisible = memberMatches(member);
        row.classList.toggle('hidden', !isVisible);
        if (isVisible) visible += 1;
      }

      const empty = document.getElementById('membersEmptyState');
      if (empty) {
        empty.classList.toggle('hidden', visible > 0);
      }
    }

    function closeAllAddMenus() {
      for (const menu of document.querySelectorAll('.add-category-menu')) {
        menu.classList.add('hidden');
      }
    }

    function buildAddMenu(memberId) {
      const member = membersById.get(Number.parseInt(memberId));
      const menu = document.querySelector(`[data-member-menu="${memberId}"]`);
      if (!member || !menu) return;

      const available = categories.filter((c) => !member.categories.includes(Number.parseInt(c.id)));
      menu.innerHTML = '';

      if (available.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'px-3 py-2 text-xs text-light-text-secondary dark:text-dark-text-secondary';
        empty.textContent = 'Sin categorías disponibles';
        menu.appendChild(empty);
      } else {
        for (const cat of available) {
          const btn = document.createElement('button');
          btn.type = 'button';
          btn.className = `w-full text-left px-3 py-2 text-xs hover:bg-light-muted/30 dark:hover:bg-dark-muted/30 ${getCategoryStyle(cat.id)}`;
          btn.textContent = cat.name;
          btn.addEventListener('click', async () => {
            await updateCategory(memberId, cat.id, true);
            buildAddMenu(memberId);
          });
          menu.appendChild(btn);
        }
      }
    }

    function updateBulkPanel() {
      const panel = document.getElementById('bulkPanel');
      if (!panel || !canManage) return;
      const count = selectedMembers.size;
      panel.classList.toggle('hidden', count === 0);
      const countEl = document.getElementById('bulkSelectedCount');
      if (countEl) countEl.textContent = String(count);
    }

    function renderBulkCategoryChoices() {
      const container = document.getElementById('bulkCategoryChoices');
      if (!container) return;
      container.innerHTML = '';

      for (const cat of categories) {
        const btn = document.createElement('button');
        const active = selectedBulkCategories.has(Number.parseInt(cat.id));
        btn.type = 'button';
        btn.dataset.bulkCategoryId = cat.id;
        btn.className = `inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs border ${active ? 'border-primary bg-primary text-white' : 'border-light-border dark:border-dark-border bg-light-background dark:bg-dark-background hover:bg-light-muted/30 dark:hover:bg-dark-muted/30'} ${active ? '' : getCategoryStyle(cat.id)}`;
        btn.textContent = cat.name;
        btn.addEventListener('click', () => {
          const id = Number.parseInt(cat.id);
          if (selectedBulkCategories.has(id)) {
            selectedBulkCategories.delete(id);
          } else {
            selectedBulkCategories.add(id);
          }
          renderBulkCategoryChoices();
        });
        container.appendChild(btn);
      }
    }

    function applyBulkUpdates(memberIds, categoryIds, action) {
      for (const memberId of memberIds) {
        const member = membersById.get(Number.parseInt(memberId));
        if (!member) continue;

        if (action === 'assign') {
          for (const categoryId of categoryIds) {
            if (!member.categories.includes(Number.parseInt(categoryId))) {
              member.categories.push(Number.parseInt(categoryId));
            }
          }
        } else {
          member.categories = member.categories.filter((id) => !categoryIds.includes(Number.parseInt(id)));
        }

        renderMemberChips(memberId);
      }
    }

    async function requestBulkAction(memberIds, categoryIds, action) {
      const response = await fetch('/categories/bulk_assign', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          group_id: groupId,
          member_ids: memberIds,
          category_ids: categoryIds,
          action
        })
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || 'No se pudo completar la acción masiva.');
      }
    }

    async function runBulk(action) {
      if (selectedMembers.size === 0 || selectedBulkCategories.size === 0) {
        showInlineAlert('Selecciona miembros y categorías para la acción masiva.', 'warning');
        return;
      }

      const memberIds = Array.from(selectedMembers);
      const categoryIds = Array.from(selectedBulkCategories);

      try {
        await requestBulkAction(memberIds, categoryIds, action);
        applyBulkUpdates(memberIds, categoryIds, action);

        selectedBulkCategories.clear();
        renderBulkCategoryChoices();
        showInlineAlert(action === 'assign' ? 'Categorías agregadas en bloque.' : 'Categorías removidas en bloque.', 'success');
      } catch (error) {
        console.error('runBulk error:', error);
        showInlineAlert(error?.message || 'Error de red al ejecutar la acción masiva.', 'danger');
      }
    }

    function setupCategoryModal() {
      if (!canManage) return;

      const modal = document.getElementById('categoryMembersModal');
      const modalTitle = document.getElementById('categoryMembersModalTitle');
      const modalMembers = document.getElementById('categoryModalMembers');
      const saveBtn = document.getElementById('saveCategoryMembers');
      const toggleAllBtn = document.getElementById('toggleAllCategoryMembers');

      if (!modal || !modalTitle || !modalMembers || !saveBtn || !toggleAllBtn) return;

      let activeCategoryId = null;
      let originalSelection = new Set();
      let lastFocusedElement = null;

      function getFocusableElements() {
        return Array.from(modal.querySelectorAll('button, input, [tabindex]:not([tabindex="-1"])'))
          .filter((el) => !el.disabled && el.offsetParent !== null);
      }

      function trapFocus(event) {
        if (event.key === 'Escape') {
          closeModal();
          return;
        }
        if (event.key !== 'Tab') return;
        const focusable = getFocusableElements();
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }

      function closeModal() {
        modal.classList.add('hidden');
        modal.removeEventListener('keydown', trapFocus);
        lastFocusedElement?.focus();
      }

      function openModal(categoryId) {
        activeCategoryId = Number.parseInt(categoryId);
        const category = categoryById.get(activeCategoryId);
        modalTitle.textContent = `Categoría: ${category ? category.name : activeCategoryId}`;

        modalMembers.parentElement.querySelector('[data-modal-alert]')?.remove();
        modalMembers.innerHTML = '';
        originalSelection = new Set();

        for (const member of membersById.values()) {
          const checked = member.categories.includes(activeCategoryId);
          if (checked) originalSelection.add(member.group_member_id);

          const item = document.createElement('label');
          item.className = 'flex items-center justify-between gap-2 rounded-lg border border-light-border dark:border-dark-border p-2 hover:bg-light-muted/30 dark:hover:bg-dark-muted/30';
          const info = document.createElement('div');
          const nameEl = document.createElement('p');
          nameEl.className = 'text-sm font-medium';
          nameEl.textContent = member.name;
          const emailEl = document.createElement('p');
          emailEl.className = 'text-xs text-light-text-secondary dark:text-dark-text-secondary';
          emailEl.textContent = member.email;
          info.append(nameEl, emailEl);

          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.className = 'category-modal-member accent-primary w-4 h-4';
          checkbox.value = member.group_member_id;
          checkbox.checked = checked;

          item.append(info, checkbox);
          modalMembers.appendChild(item);
        }

        lastFocusedElement = document.activeElement;
        modal.classList.remove('hidden');
        modal.addEventListener('keydown', trapFocus);
        getFocusableElements()[0]?.focus();
      }

      for (const openBtn of document.querySelectorAll('[data-open-category-modal]')) {
        openBtn.addEventListener('click', () => openModal(openBtn.dataset.openCategoryModal));
      }

      for (const closeBtn of modal.querySelectorAll('[data-close-category-modal="true"]')) {
        closeBtn.addEventListener('click', closeModal);
      }

      modal.addEventListener('click', (event) => {
        if (event.target?.dataset?.closeCategoryModal === 'true') {
          closeModal();
        }
      });

      toggleAllBtn.addEventListener('click', () => {
        const inputs = modalMembers.querySelectorAll('.category-modal-member');
        const allChecked = Array.from(inputs).every((i) => i.checked);
        for (const input of inputs) {
          input.checked = !allChecked;
        }
        toggleAllBtn.textContent = allChecked ? 'Seleccionar todos' : 'Deseleccionar todos';
      });

      saveBtn.addEventListener('click', async () => {
        if (!activeCategoryId) return;

        const currentSelection = new Set(
          Array.from(modalMembers.querySelectorAll('.category-modal-member:checked')).map((input) => Number.parseInt(input.value))
        );

        const toAssign = Array.from(currentSelection).filter((id) => !originalSelection.has(id));
        const toUnassign = Array.from(originalSelection).filter((id) => !currentSelection.has(id));

        // El modal solo se cierra si el server confirmó ambos lotes; cada lote
        // aplicado en el server se refleja localmente aunque el otro falle.
        // El modal es un overlay fixed con backdrop; showInlineAlert prepende en
        // <main>, que queda tapado, así que el aviso se mueve dentro del modal.
        const alertInModal = (message) => {
          modalMembers.parentElement.querySelector('[data-modal-alert]')?.remove();
          const alertEl = showInlineAlert(message, 'danger');
          alertEl.dataset.modalAlert = 'true';
          modalMembers.parentElement.prepend(alertEl);
        };

        const failWith = async (response) => {
          const errorBody = await response.json().catch(() => ({}));
          alertInModal(errorBody.message || 'No se pudo guardar el cambio de categoría.');
        };

        const applyAssigned = () => {
          for (const memberId of toAssign) {
            const member = membersById.get(Number.parseInt(memberId));
            if (member && !member.categories.includes(activeCategoryId)) {
              member.categories.push(activeCategoryId);
              renderMemberChips(memberId);
            }
            originalSelection.add(Number.parseInt(memberId));
          }
        };

        const applyUnassigned = () => {
          for (const memberId of toUnassign) {
            const member = membersById.get(Number.parseInt(memberId));
            if (member) {
              member.categories = member.categories.filter((id) => id !== activeCategoryId);
              renderMemberChips(memberId);
            }
            originalSelection.delete(Number.parseInt(memberId));
          }
        };

        try {
          if (toAssign.length > 0) {
            const response = await fetch('/categories/bulk_assign', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
              },
              body: JSON.stringify({
                group_id: groupId,
                member_ids: toAssign,
                category_ids: [activeCategoryId],
                action: 'assign'
              })
            });
            if (!response.ok) {
              await failWith(response);
              return;
            }
            applyAssigned();
          }

          if (toUnassign.length > 0) {
            const response = await fetch('/categories/bulk_assign', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
              },
              body: JSON.stringify({
                group_id: groupId,
                member_ids: toUnassign,
                category_ids: [activeCategoryId],
                action: 'unassign'
              })
            });
            if (!response.ok) {
              await failWith(response);
              return;
            }
            applyUnassigned();
          }

          showInlineAlert('Miembros actualizados para la categoría.', 'success');
          closeModal();
        } catch (error) {
          console.error('saveCategoryMembers error:', error);
          alertInModal('No se pudo guardar el cambio de categoría.');
        }
      });
    }

    const searchInput = document.getElementById('memberSearch');
    searchInput?.addEventListener('input', (event) => {
      searchTerm = String(event.target.value || '').trim();
      applyFilters();
    });

    const categoryModeSelect = document.getElementById('categoryFilterMode');
    categoryModeSelect?.addEventListener('change', (event) => {
      categoryFilterMode = String(event.target.value || 'or').toLowerCase() === 'and' ? 'and' : 'or';
      applyFilters();
    });

    const showSelectedOnlyInput = document.getElementById('showSelectedOnly');
    showSelectedOnlyInput?.addEventListener('change', (event) => {
      showSelectedOnly = !!event.target.checked;
      applyFilters();
    });

    const clearFiltersBtn = document.getElementById('clearFilters');
    clearFiltersBtn?.addEventListener('click', () => {
      searchTerm = '';
      if (searchInput) searchInput.value = '';
      selectedFilters.clear();
      includeNoCategory = false;
      categoryFilterMode = 'or';
      if (categoryModeSelect) {
        categoryModeSelect.value = 'or';
      }
      showSelectedOnly = false;
      if (showSelectedOnlyInput) {
        showSelectedOnlyInput.checked = false;
      }
      for (const chip of document.querySelectorAll('.filter-chip')) {
        clearFilterActiveStyles(chip);
      }
      applyFilters();
    });

    for (const filterBtn of document.querySelectorAll('.filter-chip')) {
      filterBtn.addEventListener('click', () => {
        if (filterBtn.dataset.filterNone === 'true') {
          includeNoCategory = !includeNoCategory;
          if (includeNoCategory) {
            filterBtn.classList.add('bg-amber-500', 'text-white', 'border-amber-500', 'ring-2', 'ring-amber-200', 'dark:ring-amber-700');
            filterBtn.setAttribute('aria-pressed', 'true');
          } else {
            clearFilterActiveStyles(filterBtn);
          }
          applyFilters();
          return;
        }

        const categoryId = Number.parseInt(filterBtn.dataset.filterCategoryId);
        if (selectedFilters.has(categoryId)) {
          selectedFilters.delete(categoryId);
          clearFilterActiveStyles(filterBtn);
        } else {
          selectedFilters.add(categoryId);
          paintFilterAsActive(filterBtn);
        }
        applyFilters();
      });
    }

    for (const chip of document.querySelectorAll('.member-cat-chip')) {
      chip.classList.add(...getCategoryStyle(chip.dataset.categoryId).split(' '));
    }

    for (const chip of document.querySelectorAll('.filter-chip')) {
      chip.setAttribute('aria-pressed', 'false');
    }

    document.addEventListener('click', async (event) => {
      const removeChip = event.target.closest('.member-cat-chip');
      if (removeChip) {
        if (removeChip.disabled) return;
        await updateCategory(removeChip.dataset.memberId, removeChip.dataset.categoryId, false);
        return;
      }

      const openAdd = event.target.closest('.open-add-category');
      if (openAdd) {
        const memberId = openAdd.dataset.memberId;
        const menu = document.querySelector(`[data-member-menu="${memberId}"]`);
        if (!menu) return;
        const isHidden = menu.classList.contains('hidden');
        closeAllAddMenus();
        if (isHidden) {
          buildAddMenu(memberId);
          menu.classList.remove('hidden');
        }
        return;
      }

      if (!event.target.closest('.add-category-menu')) {
        closeAllAddMenus();
      }
    });

    if (canManage) {
      for (const checkbox of document.querySelectorAll('.member-select')) {
        checkbox.addEventListener('change', () => {
          const memberId = Number.parseInt(checkbox.value);
          if (checkbox.checked) {
            selectedMembers.add(memberId);
          } else {
            selectedMembers.delete(memberId);
          }
          updateBulkPanel();
          if (showSelectedOnly) {
            applyFilters();
          }
        });
      }

      document.getElementById('selectVisibleMembers')?.addEventListener('click', () => {
        for (const row of document.querySelectorAll('.member-row')) {
          if (row.classList.contains('hidden')) continue;
          const checkbox = row.querySelector('.member-select');
          if (!checkbox) continue;
          checkbox.checked = true;
          selectedMembers.add(Number.parseInt(checkbox.value));
        }
        updateBulkPanel();
        if (showSelectedOnly) {
          applyFilters();
        }
      });

      document.getElementById('clearSelectedMembers')?.addEventListener('click', () => {
        selectedMembers.clear();
        for (const checkbox of document.querySelectorAll('.member-select')) {
          checkbox.checked = false;
        }
        updateBulkPanel();
        if (showSelectedOnly) {
          applyFilters();
        }
      });

      document.getElementById('bulkAssignBtn')?.addEventListener('click', () => runBulk('assign'));
      document.getElementById('bulkRemoveBtn')?.addEventListener('click', () => runBulk('unassign'));

      renderBulkCategoryChoices();
      setupCategoryModal();
    }

    applyFilters();
  });
