let state = { products: [], sales: [], documents: [], movements: [] };
let page = "overview",
  cart = [];
let renderCart, completeSale;
const $ = (s) => document.querySelector(s),
  money = (n) =>
    "₹" +
    Number(n || 0).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  esc = (s) =>
    String(s ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
function toast(s) {
  $("#toast").textContent = s;
  $("#toast").style.display = "block";
  setTimeout(() => ($("#toast").style.display = "none"), 2600);
}
function go(p) {
  if (
    page === "billing" &&
    p !== "billing" &&
    typeof counterRead === "function"
  )
    counterRead();
  page = p;
  document
    .querySelectorAll("nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  render();
}
function heading(k, t, d, button = "") {
  return `<div class="pagehead"><div><div class="eyebrow">${k}</div><h1>${t}</h1><p class="muted">${d}</p></div>${button}</div>`;
}
const btn = (label, action, secondary = false) =>
  `<button class="btn ${secondary ? "secondary" : ""}" onclick="${action}">${label}</button>`;
function stat(label, value, note, icon) {
  return `<div class="card stat"><div class="statlabel">${label}<span>${icon}</span></div><div class="statvalue">${value}</div><small>${note}</small></div>`;
}
function due(p) {
  if (!p.expiry) return false;
  let end = new Date(p.expiry + "-01T00:00:00");
  end.setMonth(end.getMonth() + 1);
  return end <= new Date(Date.now() + 90 * 86400000);
}
function overview() {
  let today = new Date().toLocaleDateString("en-CA"),
    sales = state.sales.filter((s) => s.date === today),
    total = sales.reduce((a, s) => a + s.total, 0),
    low = state.products.filter((p) => p.stock <= 10),
    exp = state.products.filter(due);
  return (
    heading(
      "YOUR BUSINESS AT A GLANCE",
      "Counter overview",
      "Sales, stock and expiry status.",
      btn("+ New sale", "go('billing')"),
    ) +
    `<div class="stats">${stat("Sales today", money(total), `${sales.length} completed sales`, "↗")}${stat("Products", state.products.length, "Across your inventory", "◫")}${stat("Low stock", low.length, "Items need attention", "◒")}${stat("Expiring soon", exp.length, "Within the next 90 days", "◷")}</div><div class="grid"><section class="card panel"><div class="panelhead"><div><h2>Counter tasks</h2><p class="muted">Sales entry, stock receipt and transaction review.</p></div><span class="tag">QUICK ACTIONS</span></div><div class="quick"><button onclick="go('billing')"><span class="icon">＋</span><b>Create a sale</b><small>Start a new invoice</small></button><button onclick="go('inventory');setTimeout(()=>$('#newProduct').scrollIntoView({behavior:'smooth'}),30)"><span class="icon">▦</span><b>Add a product</b><small>Update your catalogue</small></button><button onclick="go('activity')"><span class="icon">↗</span><b>View sales</b><small>See recent activity</small></button></div></section><section class="card panel"><div class="panelhead"><div><h2>Needs your attention</h2><p class="muted">Stock requiring review.</p></div></div><div class="notice"><span class="dot">◷</span><div><b>Expiring batches</b><p>Review stock approaching expiry</p></div><strong>${exp.length}</strong></div><div class="notice"><span class="dot">◫</span><div><b>Low-stock items</b><p>Products with 10 or fewer units</p></div><strong>${low.length}</strong></div></section></div><section class="card panel" style="margin-top:18px"><div class="panelhead"><div><h2>Recent sales</h2><p class="muted">A closer look at your latest transactions.</p></div><button class="link" onclick="go('activity')">View all →</button></div>${salesTable(state.sales.slice().reverse().slice(0, 5))}</section>`
  );
}
function salesTable(sales) {
  return sales.length
    ? `<div class="tablewrap"><table><thead><tr><th>Invoice</th><th>Customer</th><th>Date</th><th>Items</th><th>Total</th><th>Status</th></tr></thead><tbody>${sales.map((s) => `<tr><td><b>${esc(s.number)}</b></td><td>${esc(s.customer)}</td><td>${esc(s.date)}</td><td>${s.lines.reduce((a, l) => a + l.qty, 0)}</td><td><b>${money(s.total)}</b></td><td><span class="badge">Completed</span></td></tr>`).join("")}</tbody></table></div>`
    : '<div class="empty">No sales yet. Your completed invoices will appear here.</div>';
}
function inventory() {
  return (
    heading(
      "YOUR PRODUCTS",
      "Inventory",
      "Track products, batches and stock in one place.",
      btn(
        "+ Add product",
        "document.getElementById('newProduct').scrollIntoView({behavior:'smooth'})",
      ),
    ) +
    `<div class="card panel"><div class="panelhead"><div><h2>Product catalogue</h2><p class="muted">Search by product or batch number.</p></div><span class="tag">${state.products.length} PRODUCTS</span></div><div class="toolbar"><input id="search" placeholder="⌕  Search products or batches" oninput="filterProducts()"></div><div class="tablewrap"><table><thead><tr><th>Product</th><th>Batch</th><th>Expiry</th><th>Stock</th><th>Price</th><th>GST</th><th>Status</th></tr></thead><tbody id="productRows"></tbody></table></div></div><section class="card panel" id="newProduct" style="margin-top:18px"><div class="panelhead"><div><h2>Add a product batch</h2><p class="muted">Each batch has its own stock and expiry date.</p></div></div><form id="productForm" class="formgrid"><label>Product name<input name="name" required maxlength="100" placeholder="e.g. Vitamin C tablets"></label><label>Batch number<input name="batch" required maxlength="40" placeholder="e.g. VIT-109"></label><label>Expiry month<input type="month" name="expiry"></label><label>Quantity<input type="number" name="stock" min="0" step="1" required placeholder="0"></label><label>Price per unit (₹)<input type="number" name="price" min="0" step="0.01" required placeholder="0.00"></label><label>GST rate (%)<input type="number" name="tax" min="0" max="100" step="0.01" required value="12"></label><div class="wide">${btn("Save product", "", false)}</div></form></section>`
  );
}
function filterProducts() {
  let q = ($("#search")?.value || "").toLowerCase();
  $("#productRows").innerHTML =
    state.products
      .filter((p) =>
        [p.name, p.batch, p.generic_name, p.strength, p.manufacturer, p.barcode]
          .join(" ")
          .toLowerCase()
          .includes(q),
      )
      .map(
        (p) =>
          `<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.batch)}</td><td>${esc(p.expiry || "—")}</td><td>${p.stock} units</td><td>${money(p.price)}</td><td>${p.tax}%</td><td><span class="badge ${p.stock <= 10 || due(p) ? "warn" : ""}">${p.stock <= 10 ? "Low stock" : due(p) ? "Check expiry" : "In stock"}</span></td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="7" class="empty">No matching products.</td></tr>';
}
function billing() {
  return (
    heading(
      "POINT OF SALE",
      "Create a sale",
      "Build an invoice and keep stock in sync.",
      btn("Sales history", "go('activity')", true),
    ) +
    `<div class="billgrid"><div><section class="card panel"><div class="panelhead"><div><h2>Sale details</h2><p class="muted">Select a batch and add it to the invoice.</p></div></div><div class="formrow"><label>Customer<input id="customer" placeholder="Walk-in customer"></label><label>Product / batch<select id="productSelect">${state.products.map((p) => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.batch)} (${p.stock} available)</option>`).join("")}</select></label><label style="min-width:80px;flex:0.4">Quantity<input id="addQty" type="number" min="1" step="1" value="1"></label>${btn("Add item", "addItem()")}</div></section><section class="card panel" style="margin-top:18px"><div class="panelhead"><div><h2>Invoice items</h2><p class="muted">Prices use each batch's configured tax basis.</p></div></div><div id="cart"></div></section></div><section class="card panel" style="height:max-content"><div class="panelhead"><div><h2>Summary</h2><p class="muted">Review before completing the sale.</p></div></div><div id="summary"></div><button class="btn" style="width:100%;margin-top:18px" onclick="completeSale()">Complete sale →</button><p class="muted" style="font-size:11px;line-height:1.6;margin:13px 0 0">Saved invoices update the local database and stock ledger.</p></section></div>`
  );
}
function addItem() {
  let p = state.products.find((x) => x.id === $("#productSelect").value),
    qty = Number($("#addQty").value);
  if (!p || !Number.isSafeInteger(qty) || qty <= 0)
    return toast("Enter a valid whole quantity.");
  let existing = cart.find((x) => x.id === p.id);
  if (qty + (existing?.qty || 0) > p.stock)
    return toast("Quantity exceeds available stock.");
  if (existing) existing.qty += qty;
  else cart.push({ ...p, qty });
  renderCart();
  toast("Item added to the invoice.");
}
function removeItem(i) {
  cart.splice(i, 1);
  renderCart();
}
function render() {
  document
    .querySelectorAll("nav button")
    .forEach((x) => x.classList.toggle("active", x.dataset.page === page));
  $("#crumb").textContent = {
    overview: "Overview",
    billing: "Billing",
    inventory: "Inventory",
    activity: "Sales history",
  }[page];
  $("#content").innerHTML =
    page === "overview"
      ? overview()
      : page === "inventory"
        ? inventory()
        : page === "billing"
          ? billing()
          : heading(
              "YOUR TRANSACTIONS",
              "Sales history",
              "Review completed sales.",
              btn("+ New sale", "go('billing')"),
            ) +
            `<section class="card panel"><div class="panelhead"><div><h2>All sales</h2><p class="muted">Your completed transactions, newest first.</p></div></div>${salesTable(state.sales.slice().reverse())}</section>`;
  if (page === "inventory") {
    filterProducts();
  }
  if (page === "billing") renderCart();
}
document
  .querySelectorAll("nav button")
  .forEach((b) => (b.onclick = () => go(b.dataset.page)));
render();
