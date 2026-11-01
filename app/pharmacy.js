function prescriptionPayload() {
  const root = $("#prescriptionFields");
  return root
    ? Object.fromEntries(
        [...root.querySelectorAll("[name]")].map((e) => [e.name, e.value]),
      )
    : null;
}
function renderPrescriptionRows() {
  const query = ($("#rxSearch")?.value || "").toLowerCase(),
    schedule = $("#rxSchedule")?.value || "";
  return (state.prescription_register || []).filter(
    (r) =>
      (!schedule || r.schedule === schedule) &&
      [r.patient, r.prescriber, r.name, r.reference]
        .join(" ")
        .toLowerCase()
        .includes(query),
  );
}
function drawPrescriptionRows() {
  $("#rxRows").innerHTML =
    renderPrescriptionRows()
      .map(
        (r) =>
          `<tr><td>${r.date}<br>SALE-${String(r.document).padStart(5, "0")}</td><td>${esc(r.patient)}<br><span class="muted">${esc(r.patient_address)}</span></td><td>${esc(r.prescriber)}<br><span class="muted">${esc(r.prescriber_address)}</span></td><td>${esc(r.name)}<br>${esc(r.batch)} · ${esc(r.schedule)}</td><td>${r.quantity}</td><td>${esc(r.reference)}<br>${r.prescription_date}</td><td>${esc(r.pharmacist)}<br>${esc(r.registration)}</td></tr>`,
      )
      .join("") ||
    '<tr><td colspan="7" class="empty">No matching supply records.</td></tr>';
}
function exportPrescriptionCsv() {
  const columns = [
    "date",
    "document",
    "patient",
    "patient_address",
    "prescriber",
    "prescriber_address",
    "name",
    "batch",
    "schedule",
    "quantity",
    "manufacturer",
    "expiry",
    "reference",
    "prescription_date",
    "pharmacist",
    "registration",
  ];
  const safe = (value) => {
    let s = String(value ?? "");
    if (/^[\t\r\n=+@-]/.test(s)) s = "'" + s;
    return '"' + s.replaceAll('"', '""') + '"';
  };
  const csv = [
    columns,
    ...renderPrescriptionRows().map((r) => columns.map((k) => r[k])),
  ]
    .map((row) => row.map(safe).join(","))
    .join("\r\n");
  const link = document.createElement("a");
  link.href = URL.createObjectURL(
    new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }),
  );
  link.download = "prescription-supply-register.csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
function prescriptionPage() {
  $("#crumb").textContent = "Prescription supply register";
  $("#content").innerHTML =
    heading(
      "DISPENSING RECORDS",
      "Prescription supply register",
      "Recorded at the time of scheduled retail supply. Returns do not erase the original supply record.",
      btn("Export CSV", "exportPrescriptionCsv()", true),
    ) +
    `<section class="card panel"><div class="toolbar"><input id="rxSearch" placeholder="Search patient, prescriber, medicine or reference" oninput="drawPrescriptionRows()"><select id="rxSchedule" onchange="drawPrescriptionRows()"><option value="">H and H1</option><option>H</option><option>H1</option></select></div><div class="tablewrap"><table><thead><tr><th>Supply</th><th>Patient</th><th>Prescriber</th><th>Medicine / batch</th><th>Loose units</th><th>Prescription</th><th>Pharmacist</th></tr></thead><tbody id="rxRows"></tbody></table></div></section>`;
  drawPrescriptionRows();
}
function scanBarcode(event) {
  if (event.key !== "Enter") return;
  event.preventDefault();
  const barcode = event.target.value.trim();
  const now = new Date(),
    month =
      now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  const matches = state.products
    .filter(
      (p) =>
        p.barcode === barcode &&
        !activeRecall(p.id) &&
        p.stock > 0 &&
        (!p.expiry || p.expiry >= month),
    )
    .sort(
      (a, b) =>
        (a.expiry || "9999-12").localeCompare(b.expiry || "9999-12") ||
        a.batch.localeCompare(b.batch),
    );
  if (!matches.length)
    return toast("No saleable batch found for this barcode.");
  $("#productSelect").value = matches[0].id;
  $("#productSelect").dispatchEvent(new Event("change"));
  $("#addQty").focus();
  toast(
    "Selected batch " + matches[0].batch + ". Check quantity before adding.",
  );
}
const beforePharmacyRender = render;
render = function () {
  if (page === "prescriptions") prescriptionPage();
  else beforePharmacyRender();
  if (page === "inventory") {
    $("#productForm .wide").insertAdjacentHTML(
      "beforebegin",
      `<label>Generic name<input name="generic_name" maxlength="160"></label><label>Strength<input name="strength" maxlength="160"></label><label>Manufacturer<input name="manufacturer" maxlength="160"></label><label>HSN<input name="hsn" maxlength="160"></label><label>Barcode<input name="barcode" maxlength="160"></label><label>Schedule (operator classification)<select name="schedule"><option>OTC</option><option>H</option><option>H1</option></select></label>`,
    );
  }
  if (page === "billing") {
    const row = document.querySelector(".billgrid .formrow");
    row.insertAdjacentHTML(
      "afterbegin",
      `<label>Scan barcode<input id="barcodeSearch" autocomplete="off" placeholder="Scan and press Enter"></label><label>Sale type<select id="trade"><option value="retail">Retail</option><option value="wholesale">Wholesale</option></select></label>`,
    );
    $("#barcodeSearch").onkeydown = scanBarcode;
    document
      .querySelector(".billgrid > div")
      .insertAdjacentHTML(
        "beforeend",
        `<section class="card panel" id="prescriptionFields" style="margin-top:20px"><h2>Prescription details</h2><p class="muted">Required for H/H1 retail sales. A registered pharmacist must be signed in to post. Wholesale scheduled supplies require recorded business and customer drug licences. Schedule X is not supported.</p><div class="formgrid"><label>Prescription reference<input name="reference" maxlength="500"></label><label>Prescription date<input type="date" name="prescription_date"></label><label>Patient name<input name="patient" maxlength="500"></label><label>Patient address<input name="patient_address" maxlength="500"></label><label>Prescriber name<input name="prescriber" maxlength="500"></label><label>Prescriber address<input name="prescriber_address" maxlength="500"></label></div></section>`,
      );
  }
  if (page === "parties" && $("#partyForm"))
    $("#partyForm .wide").insertAdjacentHTML(
      "beforebegin",
      '<label>Drug licence number<input name="drug_licence" maxlength="160"></label>',
    );
};
const prescriptionNav = document.createElement("button");
prescriptionNav.dataset.page = "prescriptions";
prescriptionNav.innerHTML = "<span>▤</span> Prescription register";
prescriptionNav.onclick = () => go("prescriptions");
document.querySelector("nav").append(prescriptionNav);
