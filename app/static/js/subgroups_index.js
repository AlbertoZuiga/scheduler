document.addEventListener('DOMContentLoaded', () => {
  for (const toggle of document.querySelectorAll('.rename-toggle')) {
    toggle.addEventListener('click', () => {
      const form = document.querySelector(`.rename-form[data-subgroup-id="${toggle.dataset.subgroupId}"]`);
      if (!form) return;
      const willShow = form.classList.contains('hidden');
      form.classList.toggle('hidden', !willShow);
      form.classList.toggle('flex', willShow);
      if (willShow) form.querySelector('input[name="name"]')?.focus();
    });
  }
});
