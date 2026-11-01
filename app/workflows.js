let activeHeldBill = null;
function activeRecall(product) {
  return (state.recalls || []).find(
    (r) => r.product === product && !r.closed_at,
  );
}
async function holdCurrentBill() {
  if (!cart.length) return toast("Add a medicine before holding the bill.");
  try {
    await api("/api/held", {
      id: activeHeldBill,
      label: $("#holdLabel").value,
      payload: {
        party: $("#customer").value,
        trade: $("#trade").value,
        prescription: prescriptionPayload(),
        lines: cart.map((l) => ({ product: l.id, qty: l.qty })),
      },
    });
    activeHeldBill = null;
    cart = [];
    render();
    toast("Bill held. Stock is not reserved.");
  } catch (e) {
    toast(e.message);
  }
}
function resumeHeldBill(identifier) {
  if (
    cart.length &&
    activeHeldBill !== identifier &&
    !window.confirm("Replace the current unsaved counter bill?")
  )
    return;
  const held = (state.held_bills || []).find((h) => h.id === identifier);
  if (!held) return toast("Held bill is unavailable.");
  const lines = held.payload.lines.map((l) => {
    const p = state.products.find((p) => p.id === l.product);
    if (!p) throw Error("A batch from this bill is unavailable.");
    return { ...p, qty: l.qty };
  });
  activeHeldBill = identifier;
  cart = lines;
  render();
  $("#customer").value = held.payload.party;
  $("#trade").value = held.payload.trade;
  $("#trade").dispatchEvent(new Event("change"));
  $("#holdLabel").value = held.label;
  for (const [key, value] of Object.entries(held.payload.prescription || {})) {
    const input = document.querySelector(`#prescriptionFields [name="${key}"]`);
    if (input) input.value = value;
  }
  toast(
    "Held bill loaded. Review current prices, stock and prescription before posting.",
  );
}
async function deleteHeldBill(identifier) {
  if (
    !window.confirm(
      "Delete this held bill? No invoice or stock entry will be deleted.",
    )
  )
    return;
  try {
    await api("/api/held-delete", { id: identifier });
    if (activeHeldBill === identifier) activeHeldBill = null;
    render();
    toast("Held bill deleted.");
  } catch (e) {
    toast(e.message);
  }
}
function recallPage() {
  $("#crumb").textContent = "Batch recalls";
  const editable = ["admin", "manager"].includes(state.operator?.role);
  $("#content").innerHTML =
    heading(
      "BATCH SAFETY",
      "Recalls & traceability",
      "Active recalls block sales and quarantine release. Original stock and supply records remain intact.",
    ) +
    `<section class="card panel"><h2>Recall register</h2><div class="tablewrap"><table><thead><tr><th>Medicine / batch</th><th>Reason / reference</th><th>Opened by</th><th>Status</th><th>Actions</th></tr></thead><tbody>${(state.recalls || []).map((r) => `<tr><td>${esc(r.name)}<br>${esc(r.batch)}</td><td>${esc(r.reason)}<br>${esc(r.reference)}</td><td>${esc(r.opened_by_name)}<br>${new Date(r.opened_at * 1000).toLocaleDateString()}</td><td>${r.closed_at ? `Closed · ${esc(r.closure)}` : '<span class="badge warn">Supply blocked</span>'}</td><td><button class="btn secondary" onclick="traceBatch('${r.product}')">Trace</button>${editable && !r.closed_at ? ` <button class="btn secondary" onclick="reviewRecallClose(${r.id})">Review closure</button>` : ""}</td></tr>`).join("") || '<tr><td colspan="5">No recalls recorded.</td></tr>'}</tbody></table></div></section>${editable ? `<section class="card panel" style="margin-top:20px"><h2>Record batch recall</h2><form id="recallForm" class="formgrid"><label>Medicine / batch<select name="product">${state.products.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.batch)}</option>`).join("")}</select></label><label>Manufacturer / regulator reference<input name="reference" maxlength="160"></label><label class="wide">Reason<input name="reason" maxlength="500" required></label><div class="wide"><button class="btn">Block batch supply</button></div><p id="recallError" role="alert"></p></form></section>` : ""}<section class="card panel" style="margin-top:20px"><h2>Trace any batch</h2><div class="formrow"><label>Medicine / batch<select id="traceProduct">${state.products.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.batch)}</option>`).join("")}</select></label>${btn("Show history", "traceBatch($('#traceProduct').value)")}</div></section><div id="recallDetail" style="margin-top:20px"></div>`;
  if (editable)
    $("#recallForm").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/api/recall", Object.fromEntries(new FormData(e.target)));
        render();
        toast("Recall recorded. Batch supply blocked.");
      } catch (error) {
        $("#recallError").textContent = error.message;
      }
    };
}
function traceBatch(identifier) {
  const p = state.products.find((p) => p.id === identifier);
  if (!p) return;
  const docs = state.documents.filter((d) =>
    d.lines.some((l) => l.product === identifier),
  );
  $("#recallDetail").innerHTML =
    `<section class="card panel"><h2>${esc(p.name)} · ${esc(p.batch)}</h2><p>On shelf: ${p.stock} loose units · quarantined: ${p.quarantine} · ${activeRecall(identifier) ? "Supply blocked by recall" : "No active recall"}</p><div class="tablewrap"><table><thead><tr><th>Document</th><th>Date</th><th>Party</th><th>Loose units</th><th>Reference</th></tr></thead><tbody>${docs.map((d) => `<tr><td>${esc(d.number)}</td><td>${esc(d.date)}</td><td>${esc(d.party)}</td><td>${d.lines.find((l) => l.product === identifier).qty}</td><td>${d.reference || "—"}</td></tr>`).join("") || '<tr><td colspan="5">No available transaction records.</td></tr>'}</tbody></table></div><p class="muted">History follows this exact batch. Contact details are available in the party directory. Patient details remain in the restricted prescription register.</p></section>`;
}
function reviewRecallClose(id) {
  $("#recallDetail").innerHTML =
    `<section class="card panel"><h2>Review recall closure</h2><p>Closing lifts the supply block. Confirm manufacturer/regulator instructions and physical stock disposition first. Expiry and prescription checks continue to apply.</p><form id="recallCloseForm" class="formgrid"><label class="wide">Closure findings<input name="closure" maxlength="500" required></label><div class="wide"><button class="btn">Close recall & lift supply block</button></div><p id="recallCloseError" role="alert"></p></form></section>`;
  $("#recallCloseForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/api/recall-close", {
        id,
        ...Object.fromEntries(new FormData(e.target)),
      });
      render();
      toast("Recall closure recorded.");
    } catch (error) {
      $("#recallCloseError").textContent = error.message;
    }
  };
}
const beforeWorkflowRender = render;
render = function () {
  if (page === "recalls") recallPage();
  else beforeWorkflowRender();
  if (page === "billing") {
    $("#productSelect")
      .querySelectorAll("option")
      .forEach((o) => {
        if (activeRecall(o.value)) {
          o.disabled = true;
          o.textContent += " · RECALLED";
        }
      });
    document
      .querySelector(".billgrid > div")
      .insertAdjacentHTML(
        "beforeend",
        `<section class="card panel" style="margin-top:20px"><h2>Hold counter bill</h2><p class="muted">Held bills survive restart and do not reserve stock. Prices and supply controls are checked again when posting.</p><div class="formrow"><label>Bill label<input id="holdLabel" maxlength="120" placeholder="Customer or counter reference"></label>${btn("Hold bill", "holdCurrentBill()")}</div><div class="tablewrap"><table><thead><tr><th>Label</th><th>Customer</th><th>Batches</th><th>Actions</th></tr></thead><tbody>${(state.held_bills || []).map((h) => `<tr><td>${esc(h.label)}</td><td>${esc(h.payload.party)}</td><td>${h.payload.lines.length}</td><td><button class="btn secondary" onclick="resumeHeldBill('${h.id}')">Resume</button> <button class="btn secondary" onclick="deleteHeldBill('${h.id}')">Delete</button></td></tr>`).join("") || '<tr><td colspan="4">No held bills.</td></tr>'}</tbody></table></div></section>`,
      );
  }
};
const recallNav = document.createElement("button");
recallNav.dataset.page = "recalls";
recallNav.innerHTML = "<span></span> Batch recalls";
recallNav.onclick = () => go("recalls");
document.querySelector("nav").append(recallNav);

let stockCart = [],
  stockAttempt = null,
  stockSubmitting = false;
const singleReceiptOperations = operations;
operations = function () {
  stockCart = [];
  singleReceiptOperations();
  document.querySelector("#content > section").innerHTML =
    `<div class="formgrid"><label>Transaction<select id="kind"><option value="purchase">Purchase receipt</option><option value="return">Customer return</option><option value="purchase_return">Supplier return</option></select></label><label>Date<input id="stockDate" type="date" value="${localDay()}" required></label><label>Supplier / customer<input id="party" required placeholder="Party name"></label><label>Supplier invoice number<input id="supplierInvoice" maxlength="120" placeholder="Printed supplier invoice reference"></label><label>Original document<select id="reference"></select></label></div><hr><div class="formrow"><label>Product / batch<select id="receiptProduct">${state.products.map((p) => `<option value="${p.id}">${esc(p.name)} · ${esc(p.batch)}</option>`).join("")}</select></label><label>Quantity<input type="number" min="1" step="1" value="1" id="receiptQty"></label><label>Unit<select id="receiptUnit"><option value="loose">Loose units</option><option value="pack">Packs</option></select></label><label>Cost per loose unit, before tax (₹)<input type="number" min="0" step="0.01" id="cost" value="0"></label>${btn("Add batch", "addStockLine()", true)}</div><div id="stockCart" style="margin-top:20px"></div><div class="panelhead" style="margin-top:16px"><p id="stockQuote" role="status"></p>${btn("Post transaction", "postReceipt()")}</div>`;
  $("#kind").onchange = () => {
    stockCart = [];
    toggleReturn();
    $("#supplierInvoice").disabled = $("#kind").value !== "purchase";
    drawStockCart();
  };
  $("#reference").onchange = () => {
    stockCart = [];
    drawStockCart();
  };
  toggleReturn();
  drawStockCart();
};
function localDay() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function addStockLine() {
  const p = state.products.find((p) => p.id === $("#receiptProduct").value),
    entered = Number($("#receiptQty").value);
  if (!p || !Number.isSafeInteger(entered) || entered < 1)
    return toast("Select a batch and enter a whole quantity.");
  const qty = entered * ($("#receiptUnit").value === "pack" ? p.pack_size : 1),
    price = $("#cost").value;
  if (!Number.isSafeInteger(qty)) return toast("Quantity is too large.");
  if (stockCart.some((l) => l.product === p.id))
    return toast(
      "This batch is already on the receipt. Remove it to change the quantity.",
    );
  if ($("#kind").value !== "purchase") {
    const source = state.documents.find(
      (d) => String(d.id) === $("#reference").value,
    );
    if (!source || !source.lines.some((l) => l.product === p.id))
      return toast("Select the original invoice and a batch from it.");
  }
  stockCart.push({ product: p.id, qty, price });
  drawStockCart();
}
function removeStockLine(index) {
  stockCart.splice(index, 1);
  drawStockCart();
}
function drawStockCart() {
  $("#stockCart").innerHTML =
    `<div class="tablewrap"><table><thead><tr><th>Medicine / batch</th><th>Loose units</th><th>Entered purchase unit cost</th><th></th></tr></thead><tbody>${
      stockCart
        .map((l, i) => {
          const p = state.products.find((p) => p.id === l.product);
          return `<tr><td>${esc(p.name)} · ${esc(p.batch)}</td><td>${l.qty}</td><td>${$("#kind").value === "purchase" ? money(Number(l.price)) : "Original invoice allocation"}</td><td><button class="btn secondary" onclick="removeStockLine(${i})">Remove</button></td></tr>`;
        })
        .join("") ||
      '<tr><td colspan="4">Add the batches on this invoice.</td></tr>'
    }</tbody></table></div>`;
  $("#stockQuote").textContent =
    stockCart.length +
    " batches ready. Posting validates stock, original quantities and totals.";
}
postReceipt = async function () {
  if (stockSubmitting) return;
  if (!stockCart.length) return toast("Add at least one batch.");
  const kind = $("#kind").value;
  if (kind === "purchase" && !$("#supplierInvoice").value.trim())
    return toast("Enter the supplier invoice number.");
  const payload = {
    kind,
    party: $("#party").value,
    date: $("#stockDate").value,
    supplier_invoice: $("#supplierInvoice").value,
    reference: Number($("#reference").value),
    lines: stockCart,
  };
  const fingerprint = JSON.stringify(payload);
  if (!stockAttempt || stockAttempt.fingerprint !== fingerprint)
    stockAttempt = { fingerprint, key: crypto.randomUUID() };
  stockSubmitting = true;
  try {
    await api("/api/documents", { ...payload, request_key: stockAttempt.key });
    stockCart = [];
    stockAttempt = null;
    render();
    toast("Transaction posted. Stock and accounts updated.");
  } catch (e) {
    toast(e.message);
  } finally {
    stockSubmitting = false;
  }
};
