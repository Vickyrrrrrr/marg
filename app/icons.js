const UI_PATHS = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  bill: "M5 3h14v18l-3-2-4 2-4-2-3 2z M8 7h8 M8 11h8 M8 15h5",
  stock: "M3 7l9-4 9 4-9 4z M3 7v10l9 4 9-4V7 M12 11v10",
  arrow: "M5 17L19 3 M8 3h11v11",
  clock: "M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  plus: "M12 4v16 M4 12h16",
  swap: "M4 7h15l-4-4 M20 17H5l4 4",
  list: "M8 6h13 M8 12h13 M8 18h13 M3 6h1 M3 12h1 M3 18h1",
  settings: "M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M9 15v6",
  users:
    "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M13 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.87 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  payments: "M7 3v18l-4-4 M17 21V3l4 4",
};
function uiIcon(name) {
  return `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${UI_PATHS[name] || UI_PATHS.list}"/></svg>`;
}
function paintIcons() {
  const menu = {
    overview: "grid",
    billing: "bill",
    inventory: "stock",
    activity: "arrow",
    operations: "swap",
    accounts: "list",
    setup: "settings",
    payments: "payments",
    operators: "users",
    parties: "users",
    prescriptions: "bill",
    recovery: "stock",
    recalls: "list",
  };
  document.querySelectorAll("nav button").forEach((b) => {
    const span = b.querySelector("span");
    if (span) span.innerHTML = uiIcon(menu[b.dataset.page]);
  });
  document
    .querySelectorAll(".statlabel span")
    .forEach(
      (e, i) => (e.innerHTML = uiIcon(["arrow", "stock", "stock", "clock"][i])),
    );
  document
    .querySelectorAll(".quick .icon")
    .forEach((e, i) => (e.innerHTML = uiIcon(["plus", "stock", "arrow"][i])));
  document
    .querySelectorAll(".notice .dot")
    .forEach((e, i) => (e.innerHTML = uiIcon(i ? "stock" : "clock")));
}
