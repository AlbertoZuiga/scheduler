document.addEventListener('DOMContentLoaded', () => {
  const { group_id: GROUP_ID, active_weekdays: ACTIVE_WEEKDAYS } = JSON.parse(
    document.getElementById('availability-embed-data').textContent
  );

  const checkboxes = document.querySelectorAll('.availability-checkbox');
  const toggleButtons = document.querySelectorAll('.availability-toggle');
  const countDisplay = document.getElementById('selected-count');
  const saveStatus = document.getElementById('save-status');
  const checkboxById = new Map(Array.from(checkboxes).map((checkbox) => [checkbox.id, checkbox]));

  function updateVisualState(inputId, checked) {
    const controls = document.querySelectorAll(`.availability-toggle[data-target="${inputId}"]`);
    for (const control of controls) {
      control.classList.toggle('is-checked', checked);
      control.setAttribute('aria-pressed', checked ? 'true' : 'false');

      const slotLabel = control.dataset.slotLabel;
      if (slotLabel) {
        control.setAttribute(
          'aria-label',
          `${slotLabel}, ${checked ? 'disponible' : 'no disponible'}`
        );
      }

      for (const checkedState of control.querySelectorAll('[data-state="checked"]')) {
        checkedState.classList.toggle('hidden', !checked);
      }
      for (const uncheckedState of control.querySelectorAll('[data-state="unchecked"]')) {
        uncheckedState.classList.toggle('hidden', checked);
      }
    }
  }

  function setChecked(checkbox, checked, { skipSave = false } = {}) {
    if (checkbox.checked === checked) return;
    checkbox.checked = checked;
    updateVisualState(checkbox.id, checked);
    if (!skipSave) scheduleSave();
  }

  function updateCounters() {
    const totalChecked = document.querySelectorAll('.availability-checkbox:checked').length;
    countDisplay.textContent = totalChecked;

    for (const day of ACTIVE_WEEKDAYS) {
      const dayCount = document.querySelectorAll(`.availability-checkbox[data-day="${day}"]:checked`).length;
      const dayCountDisplay = document.querySelector(`.day-${day}-count`);
      if (dayCountDisplay) {
        dayCountDisplay.textContent = dayCount;
      }
    }
  }

  // Inicializar estado visual con base en los inputs canónicos
  for (const checkbox of checkboxes) {
    updateVisualState(checkbox.id, checkbox.checked);
  }
  updateCounters();

  // ------- Autoguardado (debounced) -------
  let saveTimer = null;
  let saveInFlight = false;
  let pendingResave = false;

  function scheduleSave() {
    updateCounters();
    if (saveStatus) saveStatus.textContent = 'Cambios sin guardar…';
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persistAvailability, 600);
  }

  async function persistAvailability() {
    if (saveInFlight) {
      pendingResave = true;
      return;
    }
    saveInFlight = true;
    if (saveStatus) saveStatus.textContent = 'Guardando…';

    const slots = Array.from(checkboxes)
      .filter((checkbox) => checkbox.checked)
      .map((checkbox) => ({
        weekday: Number.parseInt(checkbox.dataset.day),
        block_index: Number.parseInt(checkbox.dataset.blockIndex),
      }));

    try {
      const response = await fetch(`/groups/${GROUP_ID}/availability/autosave`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slots }),
      });
      if (!response.ok) throw new Error('save failed');
      if (saveStatus) saveStatus.textContent = 'Guardado ✓';
    } catch (error) {
      console.error('autosave error:', error);
      if (saveStatus) saveStatus.textContent = 'No se pudo guardar. Reintentando…';
      clearTimeout(saveTimer);
      saveTimer = setTimeout(persistAvailability, 2000);
    } finally {
      saveInFlight = false;
      if (pendingResave) {
        pendingResave = false;
        persistAvailability();
      }
    }
  }

  document.getElementById('availability-form')?.addEventListener('submit', () => {
    clearTimeout(saveTimer);
  });

  // ------- Clic simple -------
  for (const button of toggleButtons) {
    button.addEventListener('click', () => {
      const targetId = button.dataset.target;
      const checkbox = checkboxById.get(targetId);
      if (!checkbox || button.dataset.suppressClick === 'true') return;
      setChecked(checkbox, !checkbox.checked);
    });
  }

  // ------- Arrastre para pintar varias celdas -------
  let dragging = false;
  let dragValue = true;
  let dragMoved = false;

  function applyDragTo(button) {
    const checkbox = checkboxById.get(button.dataset.target);
    if (!checkbox) return;
    setChecked(checkbox, dragValue);
  }

  for (const button of toggleButtons) {
    button.addEventListener('pointerdown', (event) => {
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      dragging = true;
      dragMoved = false;
      const checkbox = checkboxById.get(button.dataset.target);
      dragValue = !(checkbox && checkbox.checked);
      button.dataset.suppressClick = 'false';
    });
  }

  document.addEventListener('pointermove', (event) => {
    if (!dragging) return;
    const el = document.elementFromPoint(event.clientX, event.clientY);
    const button = el?.closest('.availability-toggle');
    if (button) {
      dragMoved = true;
      button.dataset.suppressClick = 'true';
      applyDragTo(button);
      event.preventDefault();
    }
  }, { passive: false });

  document.addEventListener('pointerup', () => {
    if (dragging && dragMoved) {
      setTimeout(() => {
        for (const button of toggleButtons) button.dataset.suppressClick = 'false';
      }, 50);
    }
    dragging = false;
  });

  // ------- Marcar/desmarcar fila (bloque horario) completa -------
  for (const header of document.querySelectorAll('.toggle-block-header')) {
    header.addEventListener('click', () => {
      const blockIndex = header.dataset.blockIndex;
      const rowCheckboxes = ACTIVE_WEEKDAYS.map((day) => checkboxById.get(`availability_${day}_${blockIndex}`)).filter(Boolean);
      const shouldCheck = !rowCheckboxes.every((cb) => cb.checked);
      for (const cb of rowCheckboxes) setChecked(cb, shouldCheck, { skipSave: true });
      scheduleSave();
    });
  }

  // ------- Marcar/desmarcar día completo -------
  for (const header of document.querySelectorAll('.toggle-day-header')) {
    header.addEventListener('click', () => {
      const day = header.dataset.day;
      const dayCheckboxes = Array.from(document.querySelectorAll(`.availability-checkbox[data-day="${day}"]`));
      const shouldCheck = !dayCheckboxes.every((cb) => cb.checked);
      for (const cb of dayCheckboxes) setChecked(cb, shouldCheck, { skipSave: true });
      scheduleSave();
    });
  }

  // ------- Copiar selección del día anterior -------
  for (const button of document.querySelectorAll('.copy-previous-day')) {
    button.addEventListener('click', () => {
      const day = button.dataset.day;
      const prevDay = button.dataset.prevDay;
      const prevChecked = new Set(
        Array.from(document.querySelectorAll(`.availability-checkbox[data-day="${prevDay}"]:checked`))
          .map((cb) => cb.dataset.blockIndex)
      );
      const dayCheckboxes = Array.from(document.querySelectorAll(`.availability-checkbox[data-day="${day}"]`));
      for (const cb of dayCheckboxes) {
        setChecked(cb, prevChecked.has(cb.dataset.blockIndex), { skipSave: true });
      }
      scheduleSave();
      showInlineAlert(`Horario copiado desde ${button.textContent.replace('Copiar de ', '').trim()}.`, 'success');
    });
  }

  for (const checkbox of checkboxes) {
    checkbox.addEventListener('change', (event) => {
      updateVisualState(event.target.id, event.target.checked);
    });
  }

  for (const detail of document.querySelectorAll('details')) {
    detail.addEventListener('toggle', (e) => {
      const arrow = e.target.querySelector('.details-arrow');
      if (arrow) {
        arrow.style.transform = detail.open ? 'rotate(180deg)' : 'rotate(0deg)';
      }
    });
  }
});
