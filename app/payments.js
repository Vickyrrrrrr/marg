function settlementKind() {
  return document.querySelector("#settlementKind")?.value || "receipt";
}
function eligibleBalances(kind) {
  const sale = ["receipt", "refund"].includes(kind);
  const sign = ["receipt", "payment"].includes(kind) ? 1 : -1;
  return (state.outstanding || []).filter(
    (r) =>
      r.kind === (sale ? "sale" : "purchase") && r.balance_paise * sign > 0,
  );
}
function settlementRows() {
  const kind = settlementKind(),
    party = $("#settlementParty").value;
  const rows = eligibleBalances(kind).filter((r) => r.party === party);
  $("#allocationRows").innerHTML =
    rows
      .map(
        (r) =>
          `<tr><td><b>${esc(r.number)}</b></td><td>${esc(r.date)}</td><td>${money(Math.abs(r.balance_paise) / 100)}</td><td><input aria-label="Allocate ${esc(r.number)}" data-invoice="${r.invoice}" type="number" min="0" max="${Math.abs(r.balance_paise) / 100}" step="0.01" value="0" oninput="settlementTotal()"></td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="4" class="empty">No invoices available for this selection.</td></tr>';
  settlementTotal();
}
function settlementParties() {
  const parties = [
    ...new Set(eligibleBalances(settlementKind()).map((r) => r.party)),
  ];
  $("#settlementParty").innerHTML = parties
    .map((p) => `<option>${esc(p)}</option>`)
    .join("");
  settlementRows();
}
function amountPaise(value) {
  const parts = String(value).split(".");
  return Number(parts[0] || 0) * 100 + Number((parts[1] || "").padEnd(2, "0"));
}
function settlementTotal() {
  let total = 0;
  document
    .querySelectorAll("[data-invoice]")
    .forEach((e) => (total += amountPaise(e.value)));
  $("#settlementTotal").textContent = money(total / 100);
}
let settlementAttempt = null,
  settlementBusy = false;
async function saveSettlement(e) {
  e.preventDefault();
  if (settlementBusy) return;
  const allocations = [...document.querySelectorAll("[data-invoice]")]
    .filter((e) => amountPaise(e.value) > 0)
    .map((e) => ({ invoice: Number(e.dataset.invoice), amount: e.value }));
  const total = allocations.reduce((sum, l) => sum + amountPaise(l.amount), 0);
  const d = {
    kind: settlementKind(),
    date: $("#settlementDate").value,
    ledger: $("#settlementLedger").value,
    amount: (total / 100).toFixed(2),
    allocations,
  };
  const fingerprint = JSON.stringify(d);
  if (!settlementAttempt || settlementAttempt.fingerprint !== fingerprint)
    settlementAttempt = { fingerprint, key: crypto.randomUUID() };
  d.request_key = settlementAttempt.key;
  settlementBusy = true;
  $("#saveSettlement").disabled = true;
  try {
    await api("/api/settlements", d);
    settlementAttempt = null;
    render();
    toast("Voucher saved and invoice balances updated.");
  } catch (error) {
    $("#settlementError").textContent = error.message;
  } finally {
    settlementBusy = false;
    const b = $("#saveSettlement");
    if (b) b.disabled = false;
  }
}
function paymentsPage() {
  document
    .querySelectorAll("nav button")
    .forEach((b) =>
      b.classList.toggle("active", b.dataset.page === "payments"),
    );
  $("#crumb").textContent = "Receipts & payments";
  const now = new Date(),
    day = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, "0"),
      String(now.getDate()).padStart(2, "0"),
    ].join("-");
  const kinds =
    state.operator?.role === "cashier"
      ? ["receipt"]
      : ["receipt", "payment", "refund", "supplier_refund"];
  const labels = {
    receipt: "Customer receipt",
    payment: "Supplier payment",
    refund: "Customer refund",
    supplier_refund: "Supplier refund",
  };
  $("#content").innerHTML =
    heading(
      "INVOICE SETTLEMENT",
      "Receipts & payments",
      "Allocate money to invoices. Positive balances are due; negative balances require a refund.",
    ) +
    `<section class="card panel"><form id="settlementForm"><div class="formgrid"><label>Voucher type<select id="settlementKind" onchange="settlementParties()">${kinds.map((k) => `<option value="${k}">${labels[k]}</option>`).join("")}</select></label><label>Date<input type="date" id="settlementDate" required value="${day}"></label><label>Party<select id="settlementParty" onchange="settlementRows()"></select></label><label>Cash / bank ledger<select id="settlementLedger" required><option value="">Select account</option>${(
      state.ledgers || []
    )
      .filter((l) => ["cash", "bank"].includes(l.category))
      .map(
        (l) =>
          `<option value="${l.id}">${esc(l.name)} (${l.category})</option>`,
      )
      .join(
        "",
      )}</select></label></div><div class="tablewrap" style="margin-top:20px"><table><thead><tr><th>Invoice</th><th>Invoice date</th><th>Available amount</th><th>Allocate (₹)</th></tr></thead><tbody id="allocationRows"></tbody></table></div><div class="totals grand"><span>Allocated total</span><span id="settlementTotal"></span></div><p id="settlementError" role="alert"></p><button class="btn" id="saveSettlement">Post voucher</button></form></section><section class="card panel" style="margin-top:20px"><h2>Invoice balances</h2><div class="tablewrap"><table><thead><tr><th>Invoice</th><th>Party</th><th>Invoice total</th><th>Remaining balance</th></tr></thead><tbody>${(state.outstanding || []).map((r) => `<tr><td>${esc(r.number)}</td><td>${esc(r.party)}</td><td>${money(r.total_paise / 100)}</td><td>${money(r.balance_paise / 100)}</td></tr>`).join("")}</tbody></table></div></section><section class="card panel" style="margin-top:20px"><h2>Allocation history</h2><div class="tablewrap"><table><thead><tr><th>Voucher</th><th>Date</th><th>Party</th><th>Invoice</th><th>Cash / bank</th><th>Amount</th></tr></thead><tbody>${(state.settlements || []).map((r) => `<tr><td>${esc(r.kind.toUpperCase())}-${String(r.voucher).padStart(5, "0")}</td><td>${esc(r.date)}</td><td>${esc(r.party)}</td><td>${r.invoice}</td><td>${esc(r.cash_account)}</td><td>${money(r.amount / 100)}</td></tr>`).join("")}</tbody></table></div></section>`;
  $("#settlementForm").onsubmit = saveSettlement;
  settlementParties();
}
const beforePaymentsRender = render;
render = function () {
  if (page === "payments") paymentsPage();
  else beforePaymentsRender();
};
const paymentNav = document.createElement("button");
paymentNav.dataset.page = "payments";
paymentNav.innerHTML = "<span>⇅</span> Receipts & payments";
paymentNav.onclick = () => go("payments");
document.querySelector("nav").append(paymentNav);
