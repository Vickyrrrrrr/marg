// Counter entry owns its screen and draft; posting remains authoritative on the backend.
let counterDraft = null,
  counterQuote = null,
  counterGeneration = 0,
  counterSaving = false,
  counterAttempt = null;
let batchCursor = 0,
  batchResults = [];
function newCounterDraft() {
  const cash = (state.ledgers || []).find((l) => l.category === "cash");
  return {
    party: "",
    date: localDay(),
    trade: "retail",
    prescription: {},
    label: "",
    search: "",
    selected: "",
    unit: "loose",
    qty: "1",
    payment: cash ? "cash" : "credit",
    ledger: cash ? String(cash.id) : "",
    amount: "",
    amountEdited: false,
  };
}
function counterRead() {
  if (!$("#counterEntry")) return;
  counterDraft = {
    ...counterDraft,
    party: $("#customer").value,
    date: $("#saleDate").value,
    trade: $("#trade").value,
    prescription: prescriptionPayload(),
    label: $("#holdLabel").value,
    payment: $("#paymentMode").value,
    ledger: $("#paymentLedger").value,
    amount: $("#paymentAmount").value,
  };
}
function counterError(message = "") {
  if ($("#counterError")) $("#counterError").textContent = message;
}
function counterPayload() {
  counterRead();
  return {
    kind: "sale",
    date: counterDraft.date,
    party: counterDraft.party,
    trade: counterDraft.trade,
    prescription: counterDraft.prescription,
    draft_id: activeHeldBill,
    lines: cart.map((l) => ({
      product: l.id,
      qty: l.qty,
      discount_percent: l.discount_percent || 0,
    })),
    payment: {
      mode: counterDraft.payment,
      ledger:
        counterDraft.payment === "credit" ? null : Number(counterDraft.ledger),
      amount: counterDraft.payment === "credit" ? "0" : counterDraft.amount,
    },
  };
}
function counterBillKey() {
  return JSON.stringify({
    date: $("#saleDate")?.value,
    lines: cart.map((l) => ({
      product: l.id,
      qty: l.qty,
      discount_percent: l.discount_percent || 0,
    })),
  });
}
function counterScreen() {
  counterDraft ||= newCounterDraft();
  document.body.classList.add("counter-mode");
  $("#crumb").textContent = "Sales / Counter entry";
  $("#content").innerHTML =
    `<div id="counterEntry"><div class="counter-title"><div><h1>Sale entry</h1><span>${esc(state.company?.name || "Company setup required")} · ${activeHeldBill ? "Resumed held bill" : "Unsaved invoice"}</span></div><div class="counter-actions"><button class="btn secondary" onclick="resetCounter()">New bill</button><button class="btn secondary" onclick="openHeldCounter()">Held bills (${(state.held_bills || []).length})</button><button class="btn secondary" onclick="go('activity')">Sales register</button></div></div>
  <div class="counter-meta"><label>Customer / account<input id="customer" value="${esc(counterDraft.party)}" placeholder="Walk-in customer" autocomplete="off"></label><label>Invoice date<input id="saleDate" type="date" value="${esc(counterDraft.date)}" required></label><label>Supply type<select id="trade"><option value="retail">Retail</option><option value="wholesale">Wholesale</option></select></label><div id="counterParty" class="counter-party"></div></div>
  <p id="counterError" role="alert" aria-live="polite"></p><div class="counter-layout"><div class="counter-lines"><section class="counter-box counter-search"><div class="counter-entryrow"><label>Find medicine / scan barcode <kbd>F2</kbd><input id="barcodeSearch" autocomplete="off" placeholder="Name, generic, manufacturer, batch or barcode" value="${esc(counterDraft.search)}"></label><label>Quantity<input id="addQty" type="number" min="1" step="1" value="${esc(counterDraft.qty)}"></label><label>Unit<select id="saleUnit"><option value="loose">Loose</option><option value="pack">Packs</option></select></label><button class="btn" onclick="addItem()">Add item</button></div><select id="productSelect" hidden>${state.products.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.batch)}</option>`).join("")}</select><div class="counter-batch-scroll"><table class="counter-batches"><thead><tr><th>Medicine / manufacturer</th><th>Batch</th><th>Expiry</th><th>Available</th><th>Pack</th><th>MRP / unit</th><th>Sale price / unit</th></tr></thead><tbody id="batchRows"></tbody></table></div><div id="selectedBatch" class="counter-batch-detail"></div></section>
  <section class="counter-box counter-invoice"><div class="counter-sectionhead"><h2>Invoice items</h2><span id="lineCount"></span></div><div class="counter-grid-scroll"><table class="counter-grid"><thead><tr><th>#</th><th>Medicine / batch</th><th>Expiry</th><th>Loose qty</th><th>MRP / unit</th><th>Price / unit</th><th>Disc. %</th><th>Tax</th><th>Line total</th><th></th></tr></thead><tbody id="cartRows"></tbody></table></div></section>
  <details id="rxSection" class="counter-box"><summary>Prescription & dispensing details <span id="rxRequired"></span></summary><div id="prescriptionFields" class="formgrid">${[
    ["reference", "Prescription reference"],
    ["prescription_date", "Prescription date"],
    ["patient", "Patient name"],
    ["patient_address", "Patient address"],
    ["prescriber", "Prescriber name"],
    ["prescriber_address", "Prescriber address"],
  ]
    .map(
      ([k, label]) =>
        `<label>${label}<input name="${k}" ${k === "prescription_date" ? 'type="date"' : ""} maxlength="500" value="${esc(counterDraft.prescription[k] || "")}"></label>`,
    )
    .join("")}</div></details>
  <div class="counter-holdrow"><label>Held-bill reference<input id="holdLabel" maxlength="120" value="${esc(counterDraft.label)}" placeholder="Customer / counter reference"></label><button class="btn secondary" onclick="holdCurrentBill()">Hold bill</button><span>Held bills do not reserve stock.</span></div></div>
  <aside class="counter-checkout counter-box"><h2>Bill summary</h2><div id="summary"></div><div class="counter-payment"><label>Payment<select id="paymentMode"><option value="cash">Cash</option><option value="bank">Bank / UPI</option><option value="credit">Credit / unpaid</option></select></label><label id="paymentLedgerLabel">Receive into<select id="paymentLedger"></select></label><label id="paymentAmountLabel">Amount received (₹)<input id="paymentAmount" type="number" min="0" step="0.01" value="${esc(counterDraft.amount)}"></label><div id="paymentBalance"></div></div><button id="counterSave" class="btn" onclick="completeSale()" disabled>Save invoice & receipt</button><p id="checkoutNote"></p><div class="counter-shortcuts"><span><kbd>F2</kbd> Find medicine</span><span><kbd>↑ ↓</kbd> Select batch</span><span><kbd>Enter</kbd> Select / add</span><span><kbd>Ctrl Enter</kbd> Save</span></div></aside></div><dialog id="heldCounter"><div class="counter-sectionhead"><h2>Held bills</h2><button class="btn secondary" onclick="$('#heldCounter').close()">Close</button></div><div id="heldCounterRows"></div></dialog></div>`;
  $("#trade").value = counterDraft.trade;
  $("#saleUnit").value = counterDraft.unit;
  $("#productSelect").value = counterDraft.selected;
  $("#paymentMode").value = counterDraft.payment;
  partySuggestions($("#customer"), "customer");
  $("#customer").oninput = () => {
    counterRead();
    counterParty();
  };
  $("#trade").onchange = () => {
    counterRead();
    counterPrescription();
  };
  $("#saleDate").onchange = () => {
    counterRead();
    drawCounterBatches();
    renderCart();
  };
  $("#barcodeSearch").oninput = () => {
    counterDraft.search = $("#barcodeSearch").value;
    counterDraft.selected = "";
    batchCursor = 0;
    drawCounterBatches();
  };
  $("#barcodeSearch").onkeydown = (e) => {
    if (["ArrowDown", "ArrowUp"].includes(e.key)) {
      e.preventDefault();
      batchCursor = Math.max(
        0,
        Math.min(
          79,
          batchResults.length - 1,
          batchCursor + (e.key === "ArrowDown" ? 1 : -1),
        ),
      );
      drawCounterBatches();
      document
        .querySelector('[data-batch-cursor="true"]')
        ?.scrollIntoView({ block: "nearest" });
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const p = batchResults[batchCursor];
      if (p) chooseCounterBatch(p.id);
    }
  };
  $("#addQty").onkeydown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addItem();
    }
  };
  $("#saleUnit").onchange = () => (counterDraft.unit = $("#saleUnit").value);
  $("#paymentMode").onchange = () => {
    counterDraft.payment = $("#paymentMode").value;
    counterDraft.ledger = "";
    counterDraft.amountEdited = false;
    counterPaymentSetup();
  };
  $("#paymentLedger").onchange = () => {
    counterRead();
    counterPaymentBalance();
  };
  $("#paymentAmount").oninput = () => {
    counterDraft.amountEdited = true;
    counterRead();
    counterPaymentBalance();
  };
  $("#counterEntry").addEventListener("input", (e) => {
    if (e.target.closest("#prescriptionFields")) counterRead();
  });
  counterParty();
  counterPaymentSetup();
  drawCounterBatches();
  renderCart();
}
function batchUnavailable(p) {
  if (activeRecall(p.id)) return "RECALLED";
  if (p.expiry && p.expiry < $("#saleDate").value.slice(0, 7)) return "EXPIRED";
  const remaining = p.stock - (cart.find((l) => l.id === p.id)?.qty || 0);
  return remaining <= 0 ? "NO STOCK" : "";
}
function drawCounterBatches() {
  const q = (counterDraft.search || "").trim().toLowerCase();
  const exactBarcode =
    q && state.products.some((p) => p.barcode?.toLowerCase() === q);
  batchResults = state.products
    .filter((p) =>
      exactBarcode
        ? p.barcode?.toLowerCase() === q
        : [
            p.name,
            p.generic_name,
            p.strength,
            p.manufacturer,
            p.batch,
            p.barcode,
          ]
            .join(" ")
            .toLowerCase()
            .includes(q),
    )
    .sort(
      (a, b) =>
        Number(Boolean(batchUnavailable(a))) -
          Number(Boolean(batchUnavailable(b))) ||
        (a.expiry || "9999-12").localeCompare(b.expiry || "9999-12") ||
        a.name.localeCompare(b.name),
    );
  batchCursor = Math.max(0, Math.min(batchCursor, 79, batchResults.length - 1));
  $("#batchRows").innerHTML =
    batchResults
      .slice(0, 80)
      .map((p, i) => {
        const blocked = batchUnavailable(p),
          left = p.stock - (cart.find((l) => l.id === p.id)?.qty || 0);
        return `<tr tabindex="0" data-product="${p.id}" data-batch-cursor="${i === batchCursor}" class="${i === batchCursor ? "batch-current" : ""} ${blocked ? "batch-blocked" : ""}"><td><button class="counter-product" ${blocked ? "disabled" : ""} onclick="chooseCounterBatch('${p.id}')"><b>${esc(p.name)} ${esc(p.strength)}</b><small>${esc(p.generic_name)} · ${esc(p.manufacturer)} ${blocked ? " · " + blocked : ""}</small></button></td><td>${esc(p.batch)}</td><td>${esc(p.expiry || "—")}</td><td>${Math.max(0, left)}</td><td>${p.pack_size}</td><td>${p.mrp == null ? "—" : money(p.mrp)}</td><td>${money(p.price)}<small>${p.tax_inclusive ? "incl." : "excl."} ${p.tax}% tax</small></td></tr>`;
      })
      .join("") ||
    '<tr><td colspan="7">No matching medicine or batch.</td></tr>';
  const selected = state.products.find((p) => p.id === counterDraft.selected);
  $("#selectedBatch").textContent = selected
    ? `${selected.name} · Batch ${selected.batch} · ${selected.schedule} · ${selected.pack_size} loose units per pack · ${selected.tax_inclusive ? "Tax included in price" : "Tax added to price"}`
    : `${batchResults.length} matching batches · Choose the exact medicine and batch. Quantities and MRP are per loose unit.`;
}
function chooseCounterBatch(identifier) {
  const p = state.products.find((p) => p.id === identifier);
  if (!p) return;
  const blocked = batchUnavailable(p);
  if (blocked) return counterError("This batch cannot be selected: " + blocked);
  counterDraft.selected = p.id;
  $("#productSelect").value = p.id;
  counterError();
  drawCounterBatches();
  $("#addQty").focus();
  $("#addQty").select();
}
addItem = function () {
  const p = state.products.find((p) => p.id === counterDraft.selected),
    entered = Number($("#addQty").value);
  if (!p) return counterError("Choose a medicine batch first.");
  const qty = entered * ($("#saleUnit").value === "pack" ? p.pack_size : 1),
    existing = cart.find((l) => l.id === p.id);
  if (
    !Number.isSafeInteger(entered) ||
    entered < 1 ||
    !Number.isSafeInteger(qty)
  )
    return counterError("Enter a positive whole quantity.");
  if (batchUnavailable(p) || qty + (existing?.qty || 0) > p.stock)
    return counterError("This quantity is unavailable, expired or recalled.");
  if (existing) existing.qty += qty;
  else cart.push({ ...p, qty });
  counterDraft.qty = "1";
  $("#addQty").value = "1";
  counterError();
  renderCart();
  drawCounterBatches();
  $("#barcodeSearch").focus();
  $("#barcodeSearch").select();
};
function counterChangeQty(index, value) {
  const qty = Number(value),
    line = cart[index],
    p = state.products.find((p) => p.id === line.id);
  if (!Number.isSafeInteger(qty) || qty < 1 || qty > p.stock) {
    counterError("Quantity must be a whole number within available stock.");
    renderCart();
    return;
  }
  line.qty = qty;
  counterError();
  renderCart();
  drawCounterBatches();
}
removeItem = function (index) {
  cart.splice(index, 1);
  counterError();
  renderCart();
  drawCounterBatches();
};
function counterPrescription() {
  const required =
    $("#trade").value === "retail" &&
    cart.some((l) => ["H", "H1"].includes(l.schedule));
  $("#rxRequired").textContent = required ? "Required for this sale" : "";
  if (required) $("#rxSection").open = true;
  $("#prescriptionFields")
    .querySelectorAll("input")
    .forEach((e) => (e.required = required));
}
function counterParty() {
  const party = (state.ledgers || []).find(
    (l) =>
      ["customer", "party"].includes(l.category) &&
      l.name.toLowerCase() === $("#customer").value.trim().toLowerCase(),
  );
  const rows = (state.outstanding || []).filter(
      (r) => r.kind === "sale" && r.party_ledger === party?.id,
    ),
    balance = rows.reduce((n, r) => n + r.balance_paise, 0);
  $("#counterParty").textContent = party
    ? `${party.phone || "No phone recorded"} · Outstanding ${money(balance / 100)}${party.drug_licence ? " · DL " + party.drug_licence : ""}`
    : "New / walk-in account";
}
function counterPaymentSetup() {
  const mode = counterDraft.payment,
    ledgers = (state.ledgers || []).filter((l) => l.category === mode);
  $("#paymentLedger").innerHTML = ledgers
    .map((l) => `<option value="${l.id}">${esc(l.name)}</option>`)
    .join("");
  if (ledgers.some((l) => String(l.id) === counterDraft.ledger))
    $("#paymentLedger").value = counterDraft.ledger;
  counterDraft.ledger = $("#paymentLedger").value;
  $("#paymentLedgerLabel").hidden = mode === "credit";
  $("#paymentAmountLabel").hidden = mode === "credit";
  $("#counterSave").textContent =
    mode === "credit" ? "Save credit invoice" : "Save invoice & receipt";
  $("#checkoutNote").textContent =
    mode === "credit"
      ? "The invoice remains outstanding for later collection."
      : "Invoice, stock movement and receipt are saved together.";
  counterPaymentBalance();
}
function counterPaymentBalance() {
  if (!counterQuote) {
    $("#paymentBalance").textContent = "";
    return;
  }
  if (!counterDraft.amountEdited) {
    $("#paymentAmount").value = (counterQuote.total_paise / 100).toFixed(2);
    counterDraft.amount = $("#paymentAmount").value;
  }
  const total = counterQuote.total_paise,
    amount = Number($("#paymentAmount").value),
    paid = counterDraft.payment === "credit" ? 0 : Math.round(amount * 100);
  const change =
      counterDraft.payment === "cash" ? Math.max(0, paid - total) : 0,
    balance = Math.max(0, total - paid);
  $("#paymentBalance").innerHTML =
    `<div><span>Balance due</span><strong>${money(balance / 100)}</strong></div>${counterDraft.payment === "cash" ? `<div><span>Cash change</span><strong>${money(change / 100)}</strong></div>` : ""}`;
}
renderCart = async function () {
  const generation = ++counterGeneration;
  counterQuote = null;
  $("#counterSave").disabled = true;
  counterPrescription();
  $("#lineCount").textContent =
    `${cart.length} batches · ${cart.reduce((n, l) => n + l.qty, 0)} loose units`;
  $("#cartRows").innerHTML =
    cart
      .map(
        (l, i) =>
          `<tr tabindex="0" data-product="${l.id}" data-cart-index="${i}"><td>${i + 1}</td><td><b>${esc(l.name)}</b><small>${esc(l.batch)} · ${esc(l.schedule)}</small></td><td>${esc(l.expiry || "—")}</td><td><input aria-label="Loose quantity for ${esc(l.name)}" type="number" min="1" max="${l.stock}" step="1" value="${l.qty}" onchange="counterChangeQty(${i},this.value)"></td><td>${l.mrp == null ? "—" : money(l.mrp)}</td><td>${money(l.price)}<small>${l.tax_inclusive ? "incl." : "excl."} tax</small></td><td><input aria-label="Discount percent for ${esc(l.name)}" type="number" min="0" max="100" step="0.01" value="${l.discount_percent || 0}" onchange="counterDiscount(${i},this.value)"></td><td>${l.tax}%</td><td data-quote-line="${l.id}">…</td><td><button class="counter-remove" aria-label="Remove ${esc(l.name)}" onclick="removeItem(${i})">Remove</button></td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="10" class="counter-empty">Search a medicine or scan its barcode, select the batch, then enter quantity.</td></tr>';
  $("#summary").innerHTML =
    '<div class="counter-total"><span>Invoice total</span><strong>—</strong></div>';
  $("#paymentBalance").textContent = "";
  if (!cart.length) return;
  const fingerprint = counterBillKey();
  try {
    const r = await fetch("/api/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kind: "sale",
          date: $("#saleDate").value,
          lines: cart.map((l) => ({
            product: l.id,
            qty: l.qty,
            discount_percent: l.discount_percent || 0,
          })),
        }),
      }),
      q = await r.json();
    if (
      page !== "billing" ||
      generation !== counterGeneration ||
      fingerprint !== counterBillKey()
    )
      return;
    if (!r.ok) throw Error(q.error);
    counterQuote = { ...q, fingerprint };
    const taxable = q.lines.reduce((n, l) => n + l.taxable_paise, 0),
      tax = q.lines.reduce((n, l) => n + l.tax_paise, 0);
    for (const l of q.lines)
      document.querySelector(`[data-quote-line="${l.product}"]`).textContent =
        money(l.total_paise / 100);
    $("#summary").innerHTML =
      `<div class="counter-sumrow"><span>Taxable value</span><b>${money(taxable / 100)}</b></div><div class="counter-sumrow"><span>Tax amount</span><b>${money(tax / 100)}</b></div><div class="counter-total"><span>Invoice total</span><strong>${money(q.total_paise / 100)}</strong></div>`;
    $("#counterSave").disabled = counterSaving;
    counterPaymentBalance();
  } catch (e) {
    if (page === "billing" && generation === counterGeneration)
      counterError(e.message);
  }
};
completeSale = async function () {
  if (counterSaving) return;
  if (!counterQuote || counterQuote.fingerprint !== counterBillKey())
    return counterError("Wait for a valid invoice total before posting.");
  const payload = counterPayload(),
    fingerprint = JSON.stringify(payload);
  if (!counterAttempt || counterAttempt.fingerprint !== fingerprint)
    counterAttempt = { fingerprint, key: crypto.randomUUID() };
  counterSaving = true;
  $("#counterSave").disabled = true;
  counterError();
  try {
    const result = await api("/api/checkout", {
      ...payload,
      request_key: counterAttempt.key,
    });
    const identifier = result.posted_document;
    cart = [];
    activeHeldBill = null;
    counterDraft = null;
    counterQuote = null;
    counterAttempt = null;
    openInvoice(identifier);
    toast("Invoice saved. Stock and payment posted.");
  } catch (e) {
    counterError(e.message);
  } finally {
    counterSaving = false;
    if ($("#counterSave")) $("#counterSave").disabled = !counterQuote;
  }
};
holdCurrentBill = async function () {
  if (counterSaving) return;
  counterRead();
  if (!cart.length)
    return counterError("Add medicines before holding this bill.");
  try {
    await api("/api/held", {
      id: activeHeldBill,
      label: counterDraft.label,
      payload: {
        party: counterDraft.party,
        date: counterDraft.date,
        trade: counterDraft.trade,
        prescription: counterDraft.prescription,
        lines: cart.map((l) => ({
          product: l.id,
          qty: l.qty,
          discount_percent: l.discount_percent || 0,
        })),
      },
    });
    cart = [];
    activeHeldBill = null;
    counterDraft = null;
    render();
    toast("Bill held. Stock is not reserved.");
  } catch (e) {
    counterError(e.message);
  }
};
resumeHeldBill = function (identifier) {
  if (cart.length && !window.confirm("Replace the current unsaved invoice?"))
    return;
  const held = (state.held_bills || []).find((h) => h.id === identifier);
  if (!held) return;
  activeHeldBill = identifier;
  counterDraft = {
    ...newCounterDraft(),
    party: held.payload.party,
    date: held.payload.date || localDay(),
    trade: held.payload.trade,
    prescription: held.payload.prescription || {},
    label: held.label,
  };
  cart = held.payload.lines.map((l) => ({
    ...state.products.find((p) => p.id === l.product),
    qty: l.qty,
    discount_percent: l.discount_percent || 0,
  }));
  render();
};
function resetCounter() {
  if (cart.length && !window.confirm("Discard this unsaved invoice?")) return;
  cart = [];
  activeHeldBill = null;
  counterDraft = null;
  counterAttempt = null;
  render();
}
function openHeldCounter() {
  counterRead();
  $("#heldCounterRows").innerHTML =
    (state.held_bills || [])
      .map(
        (h) =>
          `<div class="counter-heldrow"><div><b>${esc(h.label)}</b><small>${esc(h.payload.party)} · ${h.payload.lines.length} batches</small></div><button class="btn secondary" onclick="resumeHeldBill('${h.id}')">Resume</button><button class="btn secondary" onclick="deleteHeldBill('${h.id}')">Delete</button></div>`,
      )
      .join("") || "<p>No held bills.</p>";
  $("#heldCounter").showModal();
}
const beforeCounterRender = render;
render = function () {
  if (page === "billing") counterScreen();
  else {
    document.body.classList.remove("counter-mode");
    beforeCounterRender();
  }
};
document.addEventListener("keydown", (e) => {
  if (page !== "billing" || !signedIn || document.querySelector("dialog[open]")) return;
  if (e.key === "F2") {
    e.preventDefault();
    $("#barcodeSearch").focus();
    $("#barcodeSearch").select();
  }
  if (e.ctrlKey && e.key === "Enter") {
    e.preventDefault();
    completeSale();
  }
});

function counterDiscount(index, value) {
  const amount = Number(value);
  if (
    !Number.isFinite(amount) ||
    amount < 0 ||
    amount > 100 ||
    Math.abs(amount * 100 - Math.round(amount * 100)) > 0.000001
  ) {
    counterError(
      "Enter a discount from 0 to 100 with at most two decimal places.",
    );
    renderCart();
    return;
  }
  cart[index].discount_percent = value;
  counterError();
  renderCart();
}
