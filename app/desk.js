// Desktop actions expose existing records and server-validated transactions.
const deskPages = {
  Transactions: [
    ["Sale entry", "billing", "Alt+N"],
    ["Purchases & returns", "operations", "Alt+P"],
    ["Sales register", "activity", "Alt+M"],
    ["Receipts & payments", "payments", ""],
  ],
  Masters: [
    ["Medicine batches", "inventory", "Alt+I"],
    ["Customers & suppliers", "parties", ""],
    ["Company & accounts", "setup", ""],
  ],
  Reports: [
    ["Expiry stock", "expiry", ""],
    ["Accounts & trial balance", "accounts", ""],
    ["Prescription register", "prescriptions", ""],
    ["Batch recalls", "recalls", ""],
  ],
  Administration: [
    ["Backup & recovery", "recovery", ""],
    ["Operators", "operators", ""],
  ],
};
let deskReturnFocus = null,
  expiryRows = [];
function deskAllowed(target) {
  const role = state.operator?.role;
  if (target === "expiry") return !!role;
  const nav = document.querySelector(`nav button[data-page="${target}"]`);
  // Match the permissions in auth.js before its render pass updates hidden flags.
  if (["operators", "recovery"].includes(target)) return role === "admin";
  if (target === "setup") return ["admin", "accountant"].includes(role);
  if (
    ["accounts", "operations"].includes(target) &&
    ["cashier", "pharmacist"].includes(role)
  )
    return false;
  if (target === "prescriptions") return ["admin", "pharmacist"].includes(role);
  return !!nav && !!role;
}
function deskNavigate(target) {
  if (!deskAllowed(target)) return;
  document
    .querySelectorAll("#desktopMenu details")
    .forEach((d) => (d.open = false));
  go(target);
}
function deskMenu() {
  $("#desktopMenu")?.remove();
  const bar = document.createElement("div");
  bar.id = "desktopMenu";
  bar.setAttribute("aria-label", "Desktop commands");
  for (const [group, entries] of Object.entries(deskPages)) {
    const available = entries.filter((e) => deskAllowed(e[1]));
    if (!available.length) continue;
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = group;
    details.append(summary);
    const list = document.createElement("div");
    list.className = "desk-dropdown";
    for (const [label, target, key] of available) {
      const b = document.createElement("button");
      b.textContent = label + (key ? "  ·  " + key : "");
      b.onclick = () => deskNavigate(target);
      list.append(b);
    }
    details.append(list);
    details.ontoggle = () => {
      if (details.open)
        bar.querySelectorAll("details").forEach((d) => {
          if (d !== details) d.open = false;
        });
    };
    bar.append(details);
  }
  const help = document.createElement("button");
  help.textContent = "Keyboard & row actions";
  help.onclick = deskHelp;
  bar.append(help);
  document.querySelector("main > header").after(bar);
}
function deskDialog(title, body) {
  $("#deskDialog")?.remove();
  closeContext();
  deskReturnFocus = document.activeElement;
  const dialog = document.createElement("dialog");
  dialog.id = "deskDialog";
  dialog.innerHTML = `<div class="desk-dialog-head"><h2>${esc(title)}</h2><button class="btn secondary" id="deskClose">Close</button></div><div class="desk-dialog-body">${body}</div>`;
  document.body.append(dialog);
  $("#deskClose").onclick = () => dialog.close();
  dialog.onclose = () => {
    dialog.remove();
    if (deskReturnFocus?.isConnected) deskReturnFocus.focus();
  };
  dialog.showModal();
}
function batchDetails(id) {
  const p = state.products.find((p) => p.id === id);
  if (!p) return;
  const docs = state.documents
    .filter((d) => d.lines.some((l) => l.product === id))
    .slice()
    .reverse();
  const info = [
    ["Medicine", p.name],
    [
      "Generic / strength",
      [p.generic_name, p.strength].filter(Boolean).join(" "),
    ],
    ["Manufacturer", p.manufacturer],
    ["Batch", p.batch],
    ["Expiry", p.expiry || "Not recorded"],
    ["Shelf / quarantine", `${p.stock} / ${p.quarantine} loose units`],
    ["Pack size", p.pack_size],
    ["MRP per loose unit", p.mrp == null ? "Not recorded" : money(p.mrp)],
    [
      "Selling price",
      money(p.price) + (p.tax_inclusive ? " incl. tax" : " excl. tax"),
    ],
    ["Classification", p.schedule],
    ["Recall", activeRecall(id) ? "Supply blocked" : "No active recall"],
  ];
  deskDialog(
    "Batch details & transaction history",
    `<dl class="desk-facts">${info.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl><h3>Recorded transactions · latest first</h3><div class="tablewrap"><table><thead><tr><th>Document</th><th>Date</th><th>Party</th><th>Loose qty</th><th>Free qty</th><th>Discount</th><th>Line value</th></tr></thead><tbody>${
      docs
        .map((d) => {
          const l = d.lines.find((l) => l.product === id);
          return `<tr><td><button class="link" data-open-document="${d.id}">${esc(d.number)}</button></td><td>${esc(d.date)}</td><td>${esc(d.party)}</td><td>${l.qty}</td><td>${l.free_qty || 0}</td><td>${(l.discount_bps || 0) / 100}%</td><td>${money(l.total)}</td></tr>`;
        })
        .join("") ||
      '<tr><td colspan="7">No transactions available to this operator.</td></tr>'
    }</tbody></table></div>`,
  );
  $("#deskDialog")
    .querySelectorAll("[data-open-document]")
    .forEach(
      (b) =>
        (b.onclick = () => {
          $("#deskDialog").close();
          openInvoice(Number(b.dataset.openDocument));
        }),
    );
}
function deskTax() {
  if (page !== "billing" || !counterQuote)
    return toast("Add items and wait for a valid quote.");
  const groups = new Map();
  for (const l of counterQuote.lines) {
    const product = cart.find((p) => p.id === l.product);
    const g = groups.get(product.tax) || { net: 0, tax: 0, total: 0 };
    g.net += l.taxable_paise;
    g.tax += l.tax_paise;
    g.total += l.total_paise;
    groups.set(product.tax, g);
  }
  deskDialog(
    "Invoice tax details",
    `<table><thead><tr><th>Rate</th><th>Taxable after discount</th><th>Tax</th><th>Total</th></tr></thead><tbody>${[...groups].map(([rate, g]) => `<tr><td>${rate}%</td><td>${money(g.net / 100)}</td><td>${money(g.tax / 100)}</td><td>${money(g.total / 100)}</td></tr>`).join("")}</tbody></table><p>Amounts come from the backend quote. CGST/SGST/IGST classification and statutory reporting remain pending.</p>`,
  );
}
function deskHelp() {
  deskDialog(
    "Keyboard & row actions",
    "<table><tbody><tr><th>Alt+N / Alt+P / Alt+M / Alt+I</th><td>Sale / purchases / sales register / inventory</td></tr><tr><th>F2</th><td>Find medicine in sale entry</td></tr><tr><th>Up / Down, Enter</th><td>Select a batch in medicine search</td></tr><tr><th>Ctrl+Enter</th><td>Post the sale after a valid quote</td></tr><tr><th>F10</th><td>View invoice tax details</td></tr><tr><th>Right-click / Shift+F10</th><td>Actions for the focused batch or invoice row</td></tr><tr><th>Escape</th><td>Close an action menu or dialog</td></tr></tbody></table><p>Batch details show stored attributes and transaction history. Invoice rows open their saved document. Sale-line actions change quantity/discount or remove the unsaved line.</p>",
  );
}
function closeContext(restore = false) {
  const menu = $("#contextMenu");
  if (!menu) return;
  const origin = menu.origin;
  menu.remove();
  if (restore && origin?.isConnected) origin.focus();
}
function rowContext(row, x, y) {
  const entries = [];
  const product = row.dataset.product;
  if (product) {
    entries.push([
      "Batch details & last transactions",
      () => batchDetails(product),
    ]);
    if (page === "billing" && row.closest("#batchRows"))
      entries.push(["Select this batch", () => chooseCounterBatch(product)]);
    if (row.hasAttribute("data-cart-index")) {
      const index = Number(row.dataset.cartIndex);
      entries.push(
        ["Edit quantity", () => row.querySelector("input").focus()],
        [
          "Edit discount",
          () => row.querySelector('input[aria-label^="Discount"]').focus(),
        ],
        ["Remove unsaved line", () => removeItem(index)],
        ["Tax details", deskTax],
      );
    }
  }
  if (row.dataset.document)
    entries.push([
      "Open saved document",
      () => openInvoice(Number(row.dataset.document)),
    ]);
  if (!entries.length) return false;
  closeContext();
  const menu = document.createElement("div");
  menu.id = "contextMenu";
  menu.setAttribute("role", "menu");
  menu.origin = row;
  for (const [label, action] of entries) {
    const b = document.createElement("button");
    b.setAttribute("role", "menuitem");
    b.textContent = label;
    b.onclick = () => {
      closeContext();
      action();
    };
    menu.append(b);
  }
  document.body.append(menu);
  const rect = menu.getBoundingClientRect();
  menu.style.left =
    Math.max(0, Math.min(x, innerWidth - rect.width - 8)) + "px";
  menu.style.top =
    Math.max(0, Math.min(y, innerHeight - rect.height - 8)) + "px";
  menu.querySelector("button").focus();
  menu.onkeydown = (e) => {
    const buttons = [...menu.querySelectorAll("button")],
      i = buttons.indexOf(document.activeElement);
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(e.key)) {
      e.preventDefault();
      buttons[
        e.key === "Home"
          ? 0
          : e.key === "End"
            ? buttons.length - 1
            : (i + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) %
              buttons.length
      ].focus();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeContext(true);
    }
  };
  return true;
}
document.addEventListener("contextmenu", (e) => {
  if (!signedIn || e.target.closest("input,textarea,select,dialog")) return;
  const row = e.target.closest("tr[data-product],tr[data-document]");
  if (row && rowContext(row, e.clientX, e.clientY)) e.preventDefault();
});
document.addEventListener("pointerdown", (e) => {
  if (!e.target.closest("#contextMenu")) closeContext();
  if (!e.target.closest("#desktopMenu"))
    document
      .querySelectorAll("#desktopMenu details")
      .forEach((d) => (d.open = false));
});
document.addEventListener("keydown", (e) => {
  if (!signedIn || document.querySelector("dialog[open]")) return;
  if (e.shiftKey && e.key === "F10") {
    const row = e.target.closest("tr[data-product],tr[data-document]");
    if (row) {
      e.preventDefault();
      const r = row.getBoundingClientRect();
      rowContext(row, r.left + 20, r.top + 20);
    }
    return;
  }
  if (e.altKey && !e.ctrlKey) {
    const target = {
      n: "billing",
      p: "operations",
      m: "activity",
      i: "inventory",
    }[e.key.toLowerCase()];
    if (target && deskAllowed(target)) {
      e.preventDefault();
      deskNavigate(target);
    }
  }
  if (e.key === "F10" && !e.shiftKey && page === "billing") {
    e.preventDefault();
    deskTax();
  }
});
function expiryPage() {
  $("#crumb").textContent = "Expiry stock";
  const manufacturers = [
    ...new Set(state.products.map((p) => p.manufacturer).filter(Boolean)),
  ].sort();
  const suppliers = [
    ...new Set(
      state.documents.filter((d) => d.kind === "purchase").map((d) => d.party),
    ),
  ].sort();
  $("#content").innerHTML =
    `${heading("STOCK REPORT", "Expiry stock", "Current quantities grouped by batch expiry. Filters do not reconstruct historical stock.", "")}<section class="card panel"><div class="formgrid"><label>Expiry from<input id="expiryFrom" type="month"></label><label>Expiry through<input id="expiryTo" type="month" value="${localDay().slice(0, 7)}"></label><label>Manufacturer<select id="expiryManufacturer"><option value="">All manufacturers</option>${manufacturers.map((m) => `<option>${esc(m)}</option>`).join("")}</select></label><label>Received from supplier<select id="expirySupplier"><option value="">All suppliers</option>${suppliers.map((s) => `<option>${esc(s)}</option>`).join("")}</select></label><label>Search<input id="expirySearch" placeholder="Medicine, generic, batch or barcode"></label><label>Quantity<select id="expiryQuantity"><option value="positive">Stock or quarantine present</option><option value="all">All batches</option></select></label></div><p>Supplier filter matches recorded receipts; it does not attribute remaining stock to a particular supplier.</p><div class="desk-report-actions"><button class="btn secondary" id="expiryRefresh">Refresh from database</button><button class="btn" id="expiryExport">Export CSV</button><span id="expirySummary" role="status"></span></div><div class="tablewrap"><table><thead><tr><th>Medicine</th><th>Manufacturer</th><th>Batch</th><th>Expiry</th><th>Shelf units</th><th>Quarantine</th><th>Pack</th><th>MRP / unit</th><th>Status</th></tr></thead><tbody id="expiryRows"></tbody></table></div></section>`;
  [
    "expiryFrom",
    "expiryTo",
    "expiryManufacturer",
    "expirySupplier",
    "expirySearch",
    "expiryQuantity",
  ].forEach((id) => ($("#" + id).oninput = drawExpiry));
  $("#expiryRefresh").onclick = async () => {
    try {
      await api("/api/state");
      render();
    } catch (e) {
      toast(e.message);
    }
  };
  $("#expiryExport").onclick = exportExpiry;
  drawExpiry();
}
function drawExpiry() {
  const from = $("#expiryFrom").value,
    to = $("#expiryTo").value,
    m = $("#expiryManufacturer").value,
    s = $("#expirySupplier").value,
    q = $("#expirySearch").value.toLowerCase();
  if (from && to && from > to) {
    expiryRows = [];
    $("#expiryRows").innerHTML = "";
    $("#expirySummary").textContent =
      "Expiry start must not be after expiry end.";
    return;
  }
  const ids = new Set(
    state.documents
      .filter((d) => d.kind === "purchase" && d.party === s)
      .flatMap((d) => d.lines.map((l) => l.product)),
  );
  expiryRows = state.products
    .filter(
      (p) =>
        p.expiry &&
        (!from || p.expiry >= from) &&
        (!to || p.expiry <= to) &&
        (!m || p.manufacturer === m) &&
        (!s || ids.has(p.id)) &&
        ($("#expiryQuantity").value === "all" || p.stock + p.quarantine > 0) &&
        [p.name, p.generic_name, p.batch, p.barcode]
          .join(" ")
          .toLowerCase()
          .includes(q),
    )
    .sort(
      (a, b) =>
        a.expiry.localeCompare(b.expiry) || a.name.localeCompare(b.name),
    );
  $("#expiryRows").innerHTML =
    expiryRows
      .map(
        (p) =>
          `<tr tabindex="0" data-product="${p.id}"><td><button class="link" onclick="batchDetails('${p.id}')">${esc(p.name)}</button></td><td>${esc(p.manufacturer)}</td><td>${esc(p.batch)}</td><td>${esc(p.expiry)}</td><td>${p.stock}</td><td>${p.quarantine}</td><td>${p.pack_size}</td><td>${p.mrp == null ? "—" : money(p.mrp)}</td><td>${activeRecall(p.id) ? "Recalled" : p.expiry < localDay().slice(0, 7) ? "Expired" : p.expiry === localDay().slice(0, 7) ? "Expires this month" : "Future expiry"}</td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="9">No batches match these filters.</td></tr>';
  $("#expirySummary").textContent =
    `${expiryRows.length} batches · ${expiryRows.reduce((n, p) => n + p.stock, 0)} shelf units · ${expiryRows.reduce((n, p) => n + p.quarantine, 0)} quarantined`;
}
function exportExpiry() {
  const rows = [
    [
      "Medicine",
      "Manufacturer",
      "Batch",
      "Expiry",
      "Shelf units",
      "Quarantine units",
      "Pack size",
      "MRP per loose unit",
    ],
    ...expiryRows.map((p) => [
      p.name,
      p.manufacturer,
      p.batch,
      p.expiry,
      p.stock,
      p.quarantine,
      p.pack_size,
      p.mrp ?? "",
    ]),
  ];
  const cell = (value) => {
    let s = String(value);
    if (/^[\s]*[=+@-]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  const url = URL.createObjectURL(
    new Blob(["\ufeff" + rows.map((r) => r.map(cell).join(",")).join("\r\n")], {
      type: "text/csv;charset=utf-8",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `expiry-stock-${localDay()}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
const beforeDeskRender = render;
render = function () {
  closeContext();
  $("#deskDialog")?.remove();
  if (page === "expiry") {
    document.body.classList.remove("counter-mode");
    expiryPage();
  } else beforeDeskRender();
  deskMenu();
};
