let selectedInvoice = null;
function openInvoice(identifier) {
  selectedInvoice = identifier;
  go("invoice");
}
const baseSalesTable = salesTable;
salesTable = function (rows) {
  let html = baseSalesTable(rows);
  if (!rows.length) return html;
  html = html.replace("<th>Status</th>", "<th>Status</th><th>Document</th>");
  let index = 0;
  return html.replace(/<\/tr>/g, (tag, offset) => {
    if (offset < html.indexOf("</thead>")) return tag;
    const row = rows[index++];
    return row
      ? `<td><button class="link" onclick="openInvoice(${row.id})">View / print</button></td></tr>`
      : tag;
  });
};
function invoicePage() {
  const doc = state.documents.find((d) => d.id === selectedInvoice);
  if (!doc) {
    $("#content").textContent =
      "Invoice not found in this operator’s available records.";
    return;
  }
  const company = doc.company_snapshot || state.company || {};
  $("#crumb").textContent = doc.number;
  const taxableKnown = doc.lines.every(
    (l) => l.taxable !== null && l.taxable !== undefined,
  );
  const taxable = doc.lines.reduce((sum, l) => sum + (l.taxable || 0), 0);
  $("#content").innerHTML =
    `<div class="print-actions pagehead"><div><h1>Saved invoice</h1><p class="muted">${esc(doc.number)}</p></div><div><button class="btn secondary" onclick="go('activity')">Back to sales</button> <button class="btn" onclick="window.print()">Print invoice</button></div></div><article id="invoiceDocument" class="card panel"><div class="panelhead"><div><h1>${esc(company.name || "Business details unavailable")}</h1><p>${esc(company.address || "")}</p><p>GSTIN: ${esc(company.gstin || "Not recorded")} · Drug licence: ${esc(company.drug_licence || "Not recorded")}</p></div><div><h2>${esc(doc.number)}</h2><p>Date: ${esc(doc.date)}</p></div></div><p><b>Customer:</b> ${esc(doc.party)}</p><div class="tablewrap"><table><thead><tr><th>Product</th><th>Batch</th><th>Loose units</th><th>GST rate</th><th>Taxable value</th><th>Line total</th></tr></thead><tbody>${doc.lines.map((l) => `<tr><td>${esc(l.name)}</td><td>${esc(l.batch)}</td><td>${l.qty}</td><td>${l.tax}%</td><td>${l.taxable == null ? "Unavailable" : money(l.taxable / 100)}</td><td>${money(l.total)}</td></tr>`).join("")}</tbody></table></div>${taxableKnown ? `<div class="totals"><span>Taxable total</span><b>${money(taxable / 100)}</b></div><div class="totals"><span>Tax amount — jurisdiction unclassified</span><b>${money(doc.total - taxable / 100)}</b></div>` : ""}<div class="totals grand"><span>Invoice total</span><span>${money(doc.total)}</span></div>${!doc.company_snapshot ? "<p>Historical business details were not captured for this record. Current business details are shown.</p>" : ""}<p class="muted">Invoice record. GST jurisdiction classification and statutory invoice formatting are pending.</p></article>`;
}
const beforeInvoiceRender = render;
render = function () {
  if (page === "invoice") invoicePage();
  else beforeInvoiceRender();
};
