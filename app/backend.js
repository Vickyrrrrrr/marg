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
    const note = $("#summary").parentElement.querySelector("p:last-child");
    if (note)
      note.textContent =
        "Amounts are tax-exclusive. Completed sales update stock immediately.";
  }
};
completeSale = async function () {
  try {
    await api("/api/documents", {
      kind: "sale",
      party: $("#customer").value,
      lines: cart.map((l) => ({ product: l.id, qty: l.qty })),
    });
    cart = [];
    go("activity");
    toast("Sale saved. Stock updated.");
  } catch (e) {
    toast(e.message);
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
    party: $("#customer").value,
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
      "Posted invoices and returns. Payments and statutory reporting are not yet included.",
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
    `<section class="card panel"><h2>Business identity and financial year</h2><form id="companyForm" class="formgrid"><label>Legal / business name<input name="name" required value="${esc(c.name || "")}"></label><label>Address<input name="address" required value="${esc(c.address || "")}"></label><label>GSTIN<input name="gstin" value="${esc(c.gstin || "")}"></label><label>Drug licence number<input name="drug_licence" value="${esc(c.drug_licence || "")}"></label><label>Financial year starts<input type="date" name="year_start" required value="${esc(c.year_start || "")}"></label><label>Financial year ends<input type="date" name="year_end" required value="${esc(c.year_end || "")}"></label><div class="wide"><button class="btn" type="submit">Save company</button></div></form></section><section class="card panel" style="margin-top:20px"><h2>Account ledgers</h2><form id="ledgerForm" class="formrow"><label>Ledger name<input name="name" required></label><label>Classification<select name="category">${["asset", "liability", "equity", "income", "expense", "customer", "supplier", "cash", "bank"].map((t) => `<option>${t}</option>`).join("")}</select></label><button class="btn">Create ledger</button></form></section><section class="card panel" style="margin-top:20px"><h2>Opening balances</h2><p class="muted">Post once, before invoices. Debits must equal credits.</p><form id="openingForm"><table><thead><tr><th>Ledger</th><th>Category</th><th>Debit (₹)</th><th>Credit (₹)</th></tr></thead><tbody>${(
      state.ledgers || []
    )
      .map((l) => {
        const o = (state.openings || []).find((o) => o.ledger === l.id) || {};
        return `<tr><td>${esc(l.name)}</td><td>${esc(l.category)}</td><td><input aria-label="Debit for ${esc(l.name)}" name="debit-${l.id}" type="number" min="0" step="0.01" value="${(o.debit || 0) / 100}" ${state.openings_posted ? "disabled" : ""}></td><td><input aria-label="Credit for ${esc(l.name)}" name="credit-${l.id}" type="number" min="0" step="0.01" value="${(o.credit || 0) / 100}" ${state.openings_posted ? "disabled" : ""}></td></tr>`;
      })
      .join(
        "",
      )}</tbody></table><button class="btn" style="margin-top:16px" ${state.openings_posted ? "disabled" : ""}>${state.openings_posted ? "Opening balances posted" : "Post balanced openings"}</button></form></section><section class="card panel" style="margin-top:20px"><h2>Lock a completed period</h2><p class="muted">Locks are permanent in this build. Check your entries before locking.</p><form id="lockForm" class="formrow"><label>Lock through<input type="date" name="locked_through" required value="${esc(c.locked_through || "")}"></label><button class="btn secondary">Lock period</button></form></section>`;
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
