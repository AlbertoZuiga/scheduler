const __GM__ = JSON.parse(document.getElementById('embed-gm').textContent || '{}');
const CAN_EDIT = !!__GM__.can_edit;
const API_URL = __GM__.api_url;

async function toggleCategory(catId, checked) {
  const opts = checked
    ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category_id: catId }) }
    : { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ category_id: catId }) };
  const res = await fetch(API_URL, opts);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    showInlineAlert(data.message || 'No se pudo actualizar la categoría', 'danger');
    return false;
  }
  return true;
}

document.addEventListener('DOMContentLoaded', () => {
  if (CAN_EDIT) {
    const inputs = document.querySelectorAll('input[data-cat-id]');
    for (const input of inputs) {
      input.addEventListener('change', async (e) => {
        const ok = await toggleCategory(Number(e.target.dataset.catId), e.target.checked);
        if (!ok) e.target.checked = !e.target.checked;
      });
    }
  }
});
