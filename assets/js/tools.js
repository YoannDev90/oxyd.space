(async () => {
  const i18n = await initI18n('tools');
  document.getElementById('langBtn').addEventListener('click', () => {
    // i18n auto-reloads on click
  });
})();
