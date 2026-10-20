try {
  document.documentElement.classList.toggle(
    "dark",
    (localStorage.getItem("basis-theme") ||
      (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark",
  );
} catch (_) {
  /* Storage may be unavailable. */
}
