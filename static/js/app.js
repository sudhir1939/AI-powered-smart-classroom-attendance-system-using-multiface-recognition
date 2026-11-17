document.querySelectorAll('.flash').forEach((element) => {
    window.setTimeout(() => element.remove(), 5000);
});
