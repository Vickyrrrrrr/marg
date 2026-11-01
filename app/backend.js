async function api(path, data) {
  const r = await fetch(
    path,
    data
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        }
      : {},
  );
  const result = await r.json();
  if (!r.ok) {
    if (r.status === 401 && typeof showSignIn === "function") showSignIn(false);
    throw Error(result.error);
  }
  state = result;
  return result;
}
const originalRender = render;
render = function () {
  if (page === "operations") {
    operations();
    return;
  }
  originalRender();
  if (page === "inventory") {
    $("#productForm").onsubmit = async (e) => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(e.target));
      try {
        await api("/api/products", d);
        render();
        toast("Batch created. Receive a purchase to add stock.");
      } catch (e) {
        toast(e.message);
      }
    };
    const q = $("#productForm [name=stock]");
    q.value = 0;
    q.readOnly = true;
    q.parentElement.firstChild.textContent =
      "Opening stock (receive a purchase to add stock)";
  }
  if (page === "billing") {
    const note = $("#summary").parentElement.querySelector(":scope > p.muted");
    if (note)
      note.textContent =
        "Each batch uses its configured tax basis. Saved sales update local stock.";
  }
};
function operations() {
  document
    .querySelectorAll("nav button")
    .forEach((x) => x.classList.toggle("active", x.dataset.page === page));
  $("#crumb").textContent = "Purchases & returns";
  $("#content").innerHTML =
    heading(
      "STOCK & TRANSACTIONS",
      "Purchases & returns",
      "Receive stock or record a customer return against an existing invoice.",
    ) +
    `<section class="card panel"><div class="formrow"><label>Transaction<select id="kind" onchange="toggleReturn()"><option value="purchase">Purchase receipt</option><option value="return">Customer return</option><option value="purchase_return">Supplier return</option></select></label><label>Supplier / customer<input id="party" required placeholder="Party name"></label><label>Original document<select id="reference"><option value="">Select invoice</option>${state.sales.map((s) => `<option value="${s.id}">${esc(s.number)} · ${esc(s.customer)}</option>`).join("")}</select></label></div><div class="formrow" style="margin-top:18px"><label>Product / batch<select id="receiptProduct">${state.products.map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.batch)}</option>`).join("")}</select></label><label>Quantity<input type="number" min="1" step="1" value="1" id="receiptQty"></label><label>Purchase unit cost (₹)<input type="number" min="0" step="0.01" id="cost" value="0"></label>${btn("Save transaction", "postReceipt()")}</div></section><section class="card panel" style="margin-top:20px"><h2>Transaction register</h2><div class="tablewrap"><table><thead><tr><th>Document</th><th>Party</th><th>Date</th><th>Total</th></tr></thead><tbody>${state.documents
      .slice()
      .reverse()
      .map(
        (d) =>
          `<tr><td>${esc(d.number)}</td><td>${esc(d.party)}</td><td>${esc(d.date)}</td><td>${money(d.total)}</td></tr>`,
      )
      .join(
        "",
      )}</tbody></table></div></section><section class="card panel" style="margin-top:20px"><h2>Stock movement trail</h2><div class="tablewrap"><table><thead><tr><th>Product</th><th>Document ID</th><th>Quantity change</th></tr></thead><tbody>${state.movements.map((m) => `<tr><td>${esc(m.name)}</td><td>${m.document}</td><td>${m.quantity > 0 ? "+" : ""}${m.quantity}</td></tr>`).join("")}</tbody></table></div></section>`;
  toggleReturn();
}
function toggleReturn() {
  const kind = $("#kind").value;
  $("#reference").disabled = kind === "purchase";
  $("#cost").disabled = kind !== "purchase";
  const source = kind === "purchase_return" ? "purchase" : "sale";
  $("#reference").innerHTML =
    '<option value="">Select original document</option>' +
    state.documents
      .filter((d) => d.kind === source)
      .map(
        (d) =>
          `<option value="${d.id}">${esc(d.number)} · ${esc(d.party)}</option>`,
      )
      .join("");
}
async function postReceipt() {
  const b = document.querySelector("#content .btn");
  b.disabled = true;
  try {
    await api("/api/documents", {
      kind: $("#kind").value,
      party: $("#party").value,
      reference: Number($("#reference").value),
      lines: [
        {
          product: $("#receiptProduct").value,
          qty: Number($("#receiptQty").value),
          price: Number($("#cost").value),
        },
      ],
    });
    render();
    toast("Transaction saved. Stock updated.");
  } catch (e) {
    toast(e.message);
    b.disabled = false;
  }
}
const nav = document.createElement("button");
nav.dataset.page = "operations";
nav.innerHTML = "<span>⇄</span> Purchases & returns";
nav.onclick = () => go("operations");
document.querySelector("nav").append(nav);
$("#content").innerHTML =
  '<div class="card panel">Connecting to your workspace…</div>';
const workflowRender = render;
render = function () {
  workflowRender();
  if (page === "operations") {
    $("#content").insertAdjacentHTML(
      "beforeend",
      `<section class="card panel" style="margin-top:20px"><div class="panelhead"><div><h2>Returned stock inspection</h2><p class="muted">Customer returns remain unavailable for sale until inspected.</p></div></div><div class="formrow"><label>Quarantined batch<select id="inspectProduct">${state.products
        .filter((p) => p.quarantine > 0)
        .map(
          (p) =>
            `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.batch)} · ${p.quarantine} held</option>`,
        )
        .join(
          "",
        )}</select></label><label>Quantity<input id="inspectQty" type="number" min="1" step="1" value="1"></label><label>Decision<select id="inspectDecision"><option value="release">Release after inspection</option><option value="dispose">Record disposal</option></select></label><label>Inspection findings<input id="inspectReason" placeholder="Condition and reason" required></label>${btn("Record decision", "inspectReturn()")}</div><div class="tablewrap"><table><thead><tr><th>Batch / product</th><th>Quantity</th><th>Decision</th><th>Reason</th><th>Recorded</th></tr></thead><tbody>${(state.inspections || []).map((r) => `<tr><td>${esc(r.name)}</td><td>${r.quantity}</td><td>${esc(r.disposition)}</td><td>${esc(r.reason)}</td><td>${esc(r.created_at)}</td></tr>`).join("")}</tbody></table></div></section>`,
    );
  }
  if (page === "overview") {
    $("#content").insertAdjacentHTML(
      "beforeend",
      `<section class="card panel" style="margin-top:20px"><div class="panelhead"><div><h2>Database backup</h2><p class="muted">Create an integrity-checked copy in your application data folder.</p></div>${btn("Create backup", "createBackup()")}</div><p id="backupStatus" role="status"></p></section>`,
    );
  }
};
async function inspectReturn() {
  try {
    await api("/api/inspection", {
      product: $("#inspectProduct").value,
      qty: Number($("#inspectQty").value),
      disposition: $("#inspectDecision").value,
      reason: $("#inspectReason").value,
    });
    render();
    toast("Inspection recorded. Stock updated.");
  } catch (e) {
    toast(e.message);
  }
}
async function createBackup() {
  try {
    const response = await fetch("/api/backup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const result = await response.json();
    if (!response.ok) throw Error(result.error);
    $("#backupStatus").textContent = "Backup verified: " + result.filename;
  } catch (e) {
    toast(e.message);
  }
}
const pharmacyRender = render;
render = function () {
  pharmacyRender();
  if (page === "inventory") {
    const form = $("#productForm");
    form
      .querySelector(".wide")
      .insertAdjacentHTML(
        "beforebegin",
        `<label>Loose units per pack<input name="pack_size" type="number" min="1" step="1" value="1" required></label><label>MRP per loose unit, including tax (₹)<input name="mrp" type="number" min="0" step="0.01" placeholder="Optional for non-retail items"></label><label>Sale price basis<select name="tax_inclusive"><option value="true">Includes GST</option><option value="false">Excludes GST</option></select></label>`,
      );
    form.querySelector("[name=price]").parentElement.firstChild.textContent =
      "Selling price per loose unit (₹)";
    form.onsubmit = async (e) => {
      e.preventDefault();
      const d = Object.fromEntries(new FormData(form));
      d.tax_inclusive = d.tax_inclusive === "true";
      try {
        await api("/api/products", d);
        render();
        toast("Batch created. Receive stock before selling.");
      } catch (e) {
        toast(e.message);
      }
    };
  }
  if (page === "billing") {
    const q = $("#addQty");
    q.parentElement.insertAdjacentHTML(
      "afterend",
      `<label>Quantity unit<select id="saleUnit"><option value="loose">Loose units</option><option value="pack">Packs</option></select></label>`,
    );
    const notes = document.querySelectorAll("#content .panelhead p");
    for (const p of notes)
      if (p.textContent.includes("exclusive"))
        p.textContent =
          "Prices use the batch tax basis. Quantities below are loose units.";
    renderCart();
  }
};
const looseAddItem = addItem;
addItem = function () {
  const p = state.products.find((p) => p.id === $("#productSelect").value);
  const input = $("#addQty");
  const entered = input.value;
  if ($("#saleUnit")?.value === "pack" && p)
    input.value = Number(entered) * p.pack_size;
  looseAddItem();
  input.value = entered;
};
let quoteGeneration = 0;
renderCart = async function () {
  const generation = ++quoteGeneration;
  $("#cart").innerHTML = cart.length
    ? `<div class="tablewrap"><table><thead><tr><th>Product / batch</th><th>Loose qty</th><th>Unit price</th><th>Tax basis</th><th></th></tr></thead><tbody>${cart.map((l, i) => `<tr><td><b>${esc(l.name)}</b><br>${esc(l.batch)}</td><td>${l.qty}</td><td>${money(l.price)}</td><td>${l.tax_inclusive ? "GST included" : "GST additional"} (${l.tax}%)</td><td><button class="danger" aria-label="Remove item" onclick="removeItem(${i})">Remove</button></td></tr>`).join("")}</tbody></table></div>`
    : '<div class="empty">Select a batch and enter a quantity to begin.</div>';
  $("#summary").textContent = cart.length ? "Calculating…" : "No items";
  if (!cart.length) return;
  try {
    const r = await fetch("/api/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: "sale",
        lines: cart.map((l) => ({ product: l.id, qty: l.qty })),
      }),
    });
    const q = await r.json();
    if (generation !== quoteGeneration || page !== "billing") return;
    if (!r.ok) throw Error(q.error);
    $("#summary").innerHTML =
      `<div class="totals grand"><span>Total including tax</span><span>${money(q.total_paise / 100)}</span></div><p class="muted">${q.lines.reduce((sum, l) => sum + l.quantity, 0)} loose units · ${q.lines.length} batches</p>`;
  } catch (e) {
    if (page === "billing" && generation === quoteGeneration)
      $("#summary").textContent = e.message;
  }
};
let saleSubmitting = false,
  saleAttempt = null;
completeSale = async function () {
  if (saleSubmitting) return;
  if (!cart.length) return toast("Add an item before saving.");
  const payload = {
    kind: "sale",
    draft_id: typeof activeHeldBill === "undefined" ? null : activeHeldBill,
    party: $("#customer").value,
    trade: $("#trade")?.value || "retail",
    prescription:
      typeof prescriptionPayload === "function" ? prescriptionPayload() : null,
    lines: cart.map((l) => ({ product: l.id, qty: l.qty })),
  };
  const fingerprint = JSON.stringify(payload);
  if (!saleAttempt || saleAttempt.fingerprint !== fingerprint)
    saleAttempt = { fingerprint, key: crypto.randomUUID() };
  payload.request_key = saleAttempt.key;
  saleSubmitting = true;
  try {
    await api("/api/documents", payload);
    cart = [];
    saleAttempt = null;
    if (typeof activeHeldBill !== "undefined") activeHeldBill = null;
    go("activity");
    toast("Sale saved. Stock updated.");
  } catch (e) {
    toast(e.message);
  } finally {
    saleSubmitting = false;
  }
};
function accounting() {
  document
    .querySelectorAll("nav button")
    .forEach((x) =>
      x.classList.toggle("active", x.dataset.page === "accounts"),
    );
  $("#crumb").textContent = "Accounts";
  const accounts = state.accounts || [];
  const debits = accounts.reduce((s, a) => s + a.debit, 0),
    credits = accounts.reduce((s, a) => s + a.credit, 0);
  $("#content").innerHTML =
    heading(
      "TRANSACTION ACCOUNTING",
      "Journal & trial balance",
      "Posted invoices, settlements and year-end adjustments. Statutory reporting remains unfinished.",
    ) +
    `<section class="card panel"><div class="panelhead"><div><h2>Trial balance</h2><p class="muted">Amounts in INR. Tax awaits CGST / SGST / IGST classification.</p></div><span class="badge ${debits !== credits ? "warn" : ""}">${debits === credits ? "Balanced" : "Out of balance"}</span></div>${state.unposted_documents ? `<p role="alert">${state.unposted_documents} older documents predate this ledger and require reconciliation. These totals are incomplete.</p>` : ""}<table><thead><tr><th>Account</th><th>Debit balance</th><th>Credit balance</th></tr></thead><tbody>${accounts.map((a) => `<tr><td>${esc(a.account)}</td><td>${money(Math.max(0, a.debit - a.credit) / 100)}</td><td>${money(Math.max(0, a.credit - a.debit) / 100)}</td></tr>`).join("")}</tbody><tfoot><tr><td><b>Total balances</b></td><td>${money(accounts.reduce((s, a) => s + Math.max(0, a.debit - a.credit), 0) / 100)}</td><td>${money(accounts.reduce((s, a) => s + Math.max(0, a.credit - a.debit), 0) / 100)}</td></tr></tfoot></table></section><section class="card panel" style="margin-top:20px"><h2>Journal entries</h2><div class="tablewrap"><table><thead><tr><th>Document</th><th>Date</th><th>Party</th><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody>${(state.journal || []).map((j) => `<tr><td>${esc(j.kind.toUpperCase())}-${String(j.document).padStart(5, "0")}</td><td>${esc(j.date)}</td><td>${esc(j.party)}</td><td>${esc(j.account)}</td><td>${money(j.debit / 100)}</td><td>${money(j.credit / 100)}</td></tr>`).join("")}</tbody></table></div></section>`;
}
const accountingRender = render;
render = function () {
  if (page === "accounts") accounting();
  else accountingRender();
};
const accountNav = document.createElement("button");
accountNav.dataset.page = "accounts";
accountNav.innerHTML = "<span>≡</span> Accounts";
accountNav.onclick = () => go("accounts");
document.querySelector("nav").append(accountNav);
function setupPage() {
  const c = state.company || {};
  $("#crumb").textContent = "Company setup";
  document
    .querySelectorAll("nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.page === "setup"));
  $("#content").innerHTML =
    heading(
      "COMPANY & ACCOUNTING",
      "Company setup",
      "Configure your business before posting transactions.",
    ) +
    `<section class="card panel"><h2>Business identity and financial year</h2><form id="companyForm" class="formgrid"><label>Legal / business name<input name="name" required value="${esc(c.name || "")}"></label><label>Address<input name="address" required value="${esc(c.address || "")}"></label><label>GSTIN<input name="gstin" value="${esc(c.gstin || "")}"></label><label>Drug licence number<input name="drug_licence" value="${esc(c.drug_licence || "")}"></label><label>Financial year starts<input type="date" name="year_start" required value="${esc(c.year_start || "")}"></label><label>Financial year ends<input type="date" name="year_end" required value="${esc(c.year_end || "")}"></label><div class="wide"><button class="btn" type="submit">Save company</button></div></form></section><section class="card panel" style="margin-top:20px"><h2>Account ledgers</h2><form id="ledgerForm" class="formrow"><label>Ledger name<input name="name" required></label><label>Classification<select name="category">${["asset", "liability", "equity", "income", "expense", "customer", "supplier", "party", "cash", "bank"].map((t) => `<option>${t}</option>`).join("")}</select></label><button class="btn">Create ledger</button></form></section><section class="card panel" style="margin-top:20px"><h2>Opening balances</h2><p class="muted">Post once, before invoices. Debits must equal credits.</p><form id="openingForm"><table><thead><tr><th>Ledger</th><th>Category</th><th>Debit (₹)</th><th>Credit (₹)</th></tr></thead><tbody>${(
      state.ledgers || []
    )
      .map((l) => {
        const o = (state.openings || []).find((o) => o.ledger === l.id) || {};
        return `<tr><td>${esc(l.name)}</td><td>${esc(l.category)}</td><td><input aria-label="Debit for ${esc(l.name)}" name="debit-${l.id}" type="number" min="0" step="0.01" value="${(o.debit || 0) / 100}" ${state.openings_posted ? "disabled" : ""}></td><td><input aria-label="Credit for ${esc(l.name)}" name="credit-${l.id}" type="number" min="0" step="0.01" value="${(o.credit || 0) / 100}" ${state.openings_posted ? "disabled" : ""}></td></tr>`;
      })
      .join(
        "",
      )}</tbody></table><button class="btn" style="margin-top:16px" ${state.openings_posted ? "disabled" : ""}>${state.openings_posted ? "Opening balances posted" : "Post balanced openings"}</button></form></section><section class="card panel" style="margin-top:20px"><h2>Lock a completed period</h2><p class="muted">Locks are permanent in this build. Check your entries before locking.</p><form id="lockForm" class="formrow"><label>Lock through<input type="date" name="locked_through" required value="${esc(c.locked_through && c.locked_through >= c.year_start ? c.locked_through : c.year_start || "")}"></label><button class="btn secondary">Lock period</button></form></section>`;
  for (const [id, path] of [
    ["companyForm", "/api/company"],
    ["ledgerForm", "/api/ledgers"],
    ["lockForm", "/api/period-lock"],
  ])
    $("#" + id).onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api(path, Object.fromEntries(new FormData(e.target)));
        render();
        toast("Saved.");
      } catch (e) {
        toast(e.message);
      }
    };
  $("#openingForm").onsubmit = async (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    try {
      await api("/api/openings", {
        lines: state.ledgers.map((l) => ({
          ledger: l.id,
          debit: data.get("debit-" + l.id) || 0,
          credit: data.get("credit-" + l.id) || 0,
        })),
      });
      render();
      toast("Opening balances posted.");
    } catch (e) {
      toast(e.message);
    }
  };
}
const setupRender = render;
render = function () {
  if (page === "setup") setupPage();
  else setupRender();
  const label = document.querySelector(".workspace b");
  if (label)
    label.textContent = state.company?.name || "Company setup required";
};
const setupNav = document.createElement("button");
setupNav.dataset.page = "setup";
setupNav.innerHTML = "<span>⚙</span> Company setup";
setupNav.onclick = () => go("setup");
document.querySelector("nav").append(setupNav);

async function recoveryPage() {
  $("#crumb").textContent = "Backup & recovery";
  const response = await fetch("/api/backups");
  const result = await response.json();
  if (!response.ok) return toast(result.error);
  if (page !== "recovery") return;
  $("#content").innerHTML =
    heading(
      "LOCAL DATA",
      "Backup & recovery",
      "Export a copy to another drive. Restore replaces this workspace and signs out every operator.",
    ) +
    `<section class="card panel"><div class="panelhead"><h2>Saved backups</h2>${btn("Create backup", "saveRecoveryBackup()")}</div><div class="tablewrap"><table><thead><tr><th>File</th><th>Size</th><th>Actions</th></tr></thead><tbody>${result.backups.map((b) => `<tr><td>${esc(b.filename)}</td><td>${(b.bytes / 1024).toFixed(0)} KB</td><td><a class="btn secondary" download href="/api/backup-download?filename=${encodeURIComponent(b.filename)}">Export</a> <button class="btn secondary" onclick="inspectBackup('${esc(b.filename)}')">Inspect for restore</button></td></tr>`).join("") || '<tr><td colspan="3">No backups saved yet.</td></tr>'}</tbody></table></div></section>
    <section class="card panel" style="margin-top:20px"><h2>Import backup</h2><p class="muted">Select a Ledgerly SQLite backup made with this application version. Maximum 64 MB.</p><input id="backupFile" type="file" accept=".sqlite3"><button class="btn secondary" id="importBackup">Validate & import</button></section><div id="restorePreview" style="margin-top:20px"></div>`;
  $("#importBackup").onclick = async () => {
    const file = $("#backupFile").files[0];
    if (!file || file.size > 64 * 1024 * 1024)
      return toast("Select a backup up to 64 MB.");
    const button = $("#importBackup");
    button.disabled = true;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      let binary = "";
      for (let i = 0; i < bytes.length; i += 32768)
        binary += String.fromCharCode(...bytes.subarray(i, i + 32768));
      const info = await recoveryRequest("/api/backup-import", {
        content: btoa(binary),
      });
      showRestorePreview(info);
    } catch (e) {
      toast(e.message);
    } finally {
      button.disabled = false;
    }
  };
}
async function recoveryRequest(path, data) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const result = await r.json();
  if (!r.ok) throw Error(result.error);
  return result;
}
async function saveRecoveryBackup() {
  try {
    await recoveryRequest("/api/backup", {});
    await recoveryPage();
    toast("Backup created and checked.");
  } catch (e) {
    toast(e.message);
  }
}
async function inspectBackup(filename) {
  try {
    showRestorePreview(
      await recoveryRequest("/api/backup-inspect", { filename }),
    );
  } catch (e) {
    toast(e.message);
  }
}
function showRestorePreview(info) {
  const name = state.company?.name || "RESTORE";
  $("#restorePreview").innerHTML =
    `<section class="card panel"><h2>Review replacement</h2><p><b>${esc(info.company?.name || "Company not configured")}</b> · ${info.documents} documents · ${info.products} batches · ${info.operators} operators</p><p class="muted">${esc(info.filename)} · integrity and accounting checks passed. Credentials from this backup will be restored. A safety copy of the current database is saved first.</p><form id="restoreForm" class="formgrid"><label>Enter current business name: ${esc(name)}<input name="confirm" required autocomplete="off"></label><label>Current administrator password<input name="password" type="password" required autocomplete="current-password"></label><div class="wide"><button class="btn danger">Replace workspace with this backup</button></div><p id="restoreError" class="wide" role="alert"></p></form></section>`;
  $("#restoreForm").onsubmit = async (e) => {
    e.preventDefault();
    const button = e.target.querySelector("button");
    button.disabled = true;
    try {
      const result = await recoveryRequest("/api/restore", {
        ...Object.fromEntries(new FormData(e.target)),
        filename: info.filename,
        sha256: info.sha256,
      });
      cart = [];
      activeHeldBill = null;
      state = { products: [], sales: [], documents: [] };
      showSignIn(false);
      toast(
        "Restored. Sign in with the backup's credentials. Safety copy: " +
          result.safety_backup,
      );
    } catch (error) {
      $("#restoreError").textContent = error.message;
      button.disabled = false;
    }
  };
}
const recoveryRender = render;
render = function () {
  if (page === "recovery") {
    recoveryPage();
    return;
  }
  recoveryRender();
};
const recoveryNav = document.createElement("button");
recoveryNav.dataset.page = "recovery";
recoveryNav.innerHTML = "<span></span> Backup & recovery";
recoveryNav.onclick = () => go("recovery");
document.querySelector("nav").append(recoveryNav);

const yearSetupPage = setupPage;
setupPage = function () {
  yearSetupPage();
  const archived = state.closed_years || [];
  $("#content").insertAdjacentHTML(
    "beforeend",
    `<section class="card panel" style="margin-top:20px"><div class="panelhead"><div><h2>Financial-year close</h2><p class="muted">Close a completed year and carry balances into the next. Stock, unpaid invoices and original documents remain available. Closed dates cannot receive new entries.</p></div>${state.operator?.role === "admin" ? btn("Review year close", "reviewYearClose()") : ""}</div><div id="yearClosePreview"></div><h3>Closed years</h3>${archived.length ? `<table><thead><tr><th>Period</th><th>Profit / loss</th><th>Closed by</th><th>Closing trial balance</th></tr></thead><tbody>${archived.map((y, i) => `<tr><td>${esc(y.year_start)} – ${esc(y.year_end)}</td><td>${money(y.profit / 100)}</td><td>${esc(y.closed_by)}</td><td><button class="btn secondary" onclick="showClosedTrial(${i})">View balances</button></td></tr>`).join("")}</tbody></table><div id="closedTrial"></div>` : '<p class="muted">No years closed yet.</p>'}</section>`,
  );
  if (archived.length) {
    $("#openingForm").innerHTML =
      `<p>Balances were carried from the previous year. Initial opening entries remain in the original year's records.</p><table><thead><tr><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody>${(state.year_openings || []).map((r) => `<tr><td>${esc(r.account)}</td><td>${money(r.debit / 100)}</td><td>${money(r.credit / 100)}</td></tr>`).join("")}</tbody></table>`;
  }
};
function balanceTable(rows) {
  return `<div class="tablewrap"><table><thead><tr><th>Account</th><th>Debit balance</th><th>Credit balance</th></tr></thead><tbody>${rows.map((r) => `<tr><td>${esc(r.account)}</td><td>${money(Math.max(0, r.debit - r.credit) / 100)}</td><td>${money(Math.max(0, r.credit - r.debit) / 100)}</td></tr>`).join("")}</tbody></table></div>`;
}
function showClosedTrial(index) {
  const y = state.closed_years[index];
  $("#closedTrial").innerHTML =
    `<h3>Closing balances · ${esc(y.year_end)}</h3>` +
    balanceTable(y.trial_balance);
}
async function reviewYearClose() {
  try {
    const info = await recoveryRequest("/api/year-preview", {});
    $("#yearClosePreview").innerHTML =
      `<h3>Carry forward from ${esc(info.year_end)}</h3><p>Income / expense balance before stock adjustment: <b>${money(info.profit_paise / 100)}</b>. Review closing inventory at cost after impairment, including any recoverable quarantine value. Enter the reviewed amount and its basis; the app posts opening/closing inventory adjustments and carries the resulting profit or loss.</p><div id="stockCarry">${balanceTable(info.carry_forward)}</div><p id="stockProfit" role="status"></p><form id="yearCloseForm" class="formgrid"><label>Next year starts<input name="next_start" type="date" required readonly value="${esc(info.next_start)}"></label><label>Next year ends<input name="next_end" type="date" required value="${esc(info.next_end)}"></label><label>Reviewed closing-stock value (₹)<input name="closing_stock" type="number" min="0" step="0.01" required></label><label>Valuation basis / review reference<input name="valuation_note" maxlength="500" required></label><div class="wide"><button type="button" class="btn secondary" id="reviewStockCarry">Preview adjusted balances</button></div><label class="wide">Enter business name to close: ${esc(state.company.name)}<input name="confirm" required autocomplete="off"></label><div class="wide"><button class="btn">Close year & carry balances</button></div><p id="yearCloseError" class="wide" role="alert"></p></form>`;
    $("#reviewStockCarry").onclick = async () => {
      try {
        const adjusted = await recoveryRequest("/api/year-preview", {
          closing_stock: $("#yearCloseForm [name=closing_stock]").value,
        });
        $("#stockCarry").innerHTML = balanceTable(adjusted.carry_forward);
        $("#stockProfit").textContent =
          "Profit / loss after inventory adjustment: " +
          money(adjusted.profit_paise / 100);
      } catch (error) {
        $("#yearCloseError").textContent = error.message;
      }
    };
    $("#yearCloseForm").onsubmit = async (e) => {
      e.preventDefault();
      const button = e.target.querySelector("button");
      button.disabled = true;
      try {
        await api("/api/year-close", {
          ...Object.fromEntries(new FormData(e.target)),
          year_start: info.year_start,
          year_end: info.year_end,
        });
        render();
        toast("Year closed. Balances carried forward.");
      } catch (error) {
        $("#yearCloseError").textContent = error.message;
        button.disabled = false;
      }
    };
  } catch (e) {
    toast(e.message);
  }
}
