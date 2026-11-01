function partyLedgers() {
  return (state.ledgers || []).filter((l) =>
    ["customer", "supplier", "party"].includes(l.category),
  );
}
function partiesPage() {
  document
    .querySelectorAll("nav button")
    .forEach((b) => b.classList.toggle("active", b.dataset.page === "parties"));
  $("#crumb").textContent = "Customers & suppliers";
  const editable = state.operator?.role !== "cashier";
  $("#content").innerHTML =
    heading(
      "PARTY LEDGERS",
      "Customers & suppliers",
      "Invoices, returns and settlements retain a stable ledger identity.",
    ) +
    `<section class="card panel"><h2>Party directory</h2><div class="tablewrap"><table><thead><tr><th>Name</th><th>Classification</th><th>Phone</th><th>GSTIN</th><th>Linked invoices</th><th></th></tr></thead><tbody>${partyLedgers()
      .map(
        (l) =>
          `<tr><td><b>${esc(l.name)}</b><br><span class="muted">${esc(l.address)}</span></td><td>${l.category === "party" ? "Customer & supplier" : esc(l.category)}</td><td>${esc(l.phone || "—")}</td><td>${esc(l.gstin || "—")}</td><td>${state.documents.filter((d) => d.party_ledger === l.id && ["sale", "purchase"].includes(d.kind)).length}</td><td><button class="link" onclick="showPartyStatement(${l.id})">Statement</button></td></tr>`,
      )
      .join(
        "",
      )}</tbody></table></div></section>${editable ? `<section class="card panel" style="margin-top:20px"><h2>Create party ledger</h2><form id="partyForm" class="formgrid"><label>Name<input name="name" maxlength="120" required></label><label>Classification<select name="category"><option value="customer">Customer</option><option value="supplier">Supplier</option><option value="party">Customer & supplier</option></select></label><label>Phone<input name="phone" maxlength="30"></label><label>GSTIN<input name="gstin" maxlength="15"></label><label class="wide">Address<input name="address" maxlength="500"></label><div class="wide"><button class="btn">Create party ledger</button></div><p id="partyError" role="alert"></p></form></section>` : ""}`;
  if (editable)
    $("#partyForm").onsubmit = async (e) => {
      e.preventDefault();
      try {
        await api("/api/parties", Object.fromEntries(new FormData(e.target)));
        render();
        toast("Party ledger created.");
      } catch (error) {
        $("#partyError").textContent = error.message;
      }
    };
}
function partySuggestions(input, kind) {
  if (!input) return;
  const id = "suggest-" + input.id;
  input.setAttribute("list", id);
  input.insertAdjacentHTML(
    "afterend",
    `<datalist id="${id}">${partyLedgers()
      .filter((l) => l.category === "party" || l.category === kind)
      .map((l) => `<option value="${esc(l.name)}"></option>`)
      .join("")}</datalist>`,
  );
}
const beforePartiesRender = render;
render = function () {
  if (page === "parties") partiesPage();
  else beforePartiesRender();
  if (page === "billing") partySuggestions($("#customer"), "customer");
  if (page === "operations") {
    partySuggestions($("#party"), "supplier");
    const sync = () => {
      const returning = $("#kind").value !== "purchase";
      const original = state.documents.find(
        (d) => String(d.id) === $("#reference").value,
      );
      $("#party").readOnly = returning;
      if (returning) $("#party").value = original?.party || "";
    };
    $("#reference").addEventListener("change", sync);
    $("#kind").addEventListener("change", sync);
    sync();
  }
};
const partyNav = document.createElement("button");
partyNav.dataset.page = "parties";
partyNav.innerHTML = "<span>◯</span> Customers & suppliers";
partyNav.onclick = () => go("parties");
document.querySelector("nav").append(partyNav);

function showPartyStatement(identifier) {
  document.querySelector("#partyStatement")?.remove();
  const ledger = partyLedgers().find((l) => l.id === identifier);
  if (!ledger) return;
  const account = `Party ledger: ${ledger.id}: ${ledger.name}`;
  const opening = (state.openings || []).find((l) => l.ledger === identifier);
  const journal = (state.journal || [])
    .filter((j) => j.account === account)
    .sort((a, b) => a.date.localeCompare(b.date) || a.id - b.id);
  let balance = (opening?.debit || 0) - (opening?.credit || 0);
  const invoices = (state.outstanding || []).filter(
    (d) => d.party_ledger === identifier,
  );
  const financial = ["admin", "accountant"].includes(state.operator?.role);
  $("#content").insertAdjacentHTML(
    "beforeend",
    `<section id="partyStatement" class="card panel" style="margin-top:20px"><h2>${esc(ledger.name)} · ${financial ? "Ledger statement" : "Invoice balances"}</h2>${
      financial
        ? `<p class="muted">Opening: ${money(Math.abs(balance) / 100)} ${balance < 0 ? "Cr" : "Dr"}. Positive running balances are debit; negative balances are credit.</p><div class="tablewrap"><table><thead><tr><th>Date</th><th>Document</th><th>Debit</th><th>Credit</th><th>Running balance</th></tr></thead><tbody>${journal
            .map((j) => {
              balance += j.debit - j.credit;
              return `<tr><td>${esc(j.date)}</td><td>${esc(j.kind.toUpperCase())}-${String(j.document).padStart(5, "0")}</td><td>${money(j.debit / 100)}</td><td>${money(j.credit / 100)}</td><td>${money(Math.abs(balance) / 100)} ${balance < 0 ? "Cr" : "Dr"}</td></tr>`;
            })
            .join("")}</tbody></table></div>`
        : ""
    }<h3 style="margin-top:20px">Invoice balances</h3><div class="tablewrap"><table><thead><tr><th>Invoice</th><th>Invoice date</th><th>Original total</th><th>Outstanding</th></tr></thead><tbody>${invoices.map((d) => `<tr><td>${esc(d.number)}</td><td>${esc(d.date)}</td><td>${money(d.total_paise / 100)}</td><td>${money(d.balance_paise / 100)}</td></tr>`).join("")}</tbody></table></div><p class="muted">Only records linked to this ledger are included. Unlinked historical documents require reconciliation.</p></section>`,
  );
  $("#partyStatement").scrollIntoView({ behavior: "smooth" });
}
