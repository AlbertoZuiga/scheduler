document.addEventListener('DOMContentLoaded', () => {
  const nameInput = document.getElementById('group_name');
  nameInput?.focus();

  const descInput = document.getElementById('group_description');
  if (descInput) {
    const maxLength = descInput.getAttribute('maxlength');
    const counterDiv = document.createElement('div');
    counterDiv.className = 'text-xs text-right text-light-text-secondary dark:text-dark-text-secondary mt-1';
    counterDiv.innerHTML = `<span id="charCount">0</span>/${maxLength} caracteres`;
    descInput.parentElement.appendChild(counterDiv);
    descInput.addEventListener('input', () => {
      document.getElementById('charCount').textContent = descInput.value.length;
    });
  }
});
