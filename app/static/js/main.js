const imageInput = document.querySelector('#image-input');
const preview = document.querySelector('#image-preview');
let previewUrl;

imageInput?.addEventListener('change', () => {
  const file = imageInput.files[0];
  if (!file) return;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  preview.src = previewUrl;
  preview.hidden = false;
  document.querySelector('#image-placeholder').hidden = true;
});

const dialog = document.querySelector('#confirm-dialog');
let pendingForm;
document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    pendingForm = form;
    document.querySelector('#confirm-message').textContent = form.dataset.confirm;
    dialog.showModal();
    document.querySelector('#confirm-cancel').focus();
  });
});
document.querySelector('#confirm-cancel')?.addEventListener('click', () => dialog.close());
document.querySelector('#confirm-submit')?.addEventListener('click', () => {
  if (!pendingForm) return;
  pendingForm.submit();
  pendingForm = null;
  dialog.close();
});
dialog?.addEventListener('close', () => { pendingForm = null; });
