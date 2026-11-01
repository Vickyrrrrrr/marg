let signedIn = false;
const authenticatedRender = render;
render = function () {
  if (!signedIn) return;
  if (page === "operators") return operatorPage();
  authenticatedRender();
  paintIcons();
  const role = state.operator?.role;
  document
    .querySelectorAll(".profile small")
    .forEach(
      (e) =>
        (e.textContent = role
          ? role[0].toUpperCase() + role.slice(1)
          : "Operator"),
    );
  document
    .querySelectorAll(".topright .user,.profile .avatar")
    .forEach(
      (e) =>
        (e.textContent = (state.operator?.username || "O")[0].toUpperCase()),
    );
  document.querySelectorAll("nav button").forEach((b) => {
    const permitted =
      role === "admin" || !["setup", "operators"].includes(b.dataset.page);
    b.hidden =
      !permitted ||
      (["cashier", "pharmacist"].includes(role) &&
        ["accounts", "operations"].includes(b.dataset.page));
  });
  document
    .querySelectorAll("nav button[data-page=prescriptions]")
    .forEach((b) => (b.hidden = !["admin", "pharmacist"].includes(role)));
  document
    .querySelectorAll(".profile b")
    .forEach((e) => (e.textContent = state.operator?.username || "Operator"));
};
function showSignIn(setup) {
  signedIn = false;
  document.querySelector("nav").hidden = true;
  document.querySelector("#signout")?.remove();
  $("#content").innerHTML =
    `<section class="card panel" style="max-width:460px;margin:40px auto"><h1>${setup ? "Create administrator" : "Sign in"}</h1><p class="muted">${setup ? "Create the owner account for this local database. Passwords must have at least 12 characters." : "Sign in with your local operator account. Internet is not required."}</p><form id="loginForm" class="formgrid"><label class="wide">Operator name<input name="username" required maxlength="80" autocomplete="username"></label><label class="wide">Password<input name="password" type="password" required ${setup ? 'minlength="12"' : ""} maxlength="256" autocomplete="${setup ? "new-password" : "current-password"}"></label><p id="loginError" class="wide" role="alert"></p><div class="wide"><button class="btn">${setup ? "Create administrator" : "Sign in"}</button></div></form></section>`;
  $("#loginForm").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      const r = await fetch(setup ? "/api/bootstrap" : "/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(event.target))),
      });
      const result = await r.json();
      if (!r.ok) throw Error(result.error);
      await loadWorkspace();
    } catch (e) {
      $("#loginError").textContent = e.message;
      button.disabled = false;
    }
  };
}
async function loadWorkspace() {
  await api("/api/state");
  signedIn = true;
  document.querySelector("nav").hidden = false;
  page =
    state.company || state.operator.role !== "admin" ? "overview" : "setup";
  render();
  if (!$("#signout")) {
    const button = document.createElement("button");
    button.id = "signout";
    button.className = "btn secondary";
    button.textContent = "Sign out";
    button.onclick = async () => {
      await fetch("/api/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      cart = [];
      state = { products: [], sales: [], documents: [] };
      showSignIn(false);
    };
    document.querySelector(".topright").append(button);
  }
}
async function operatorPage() {
  const r = await fetch("/api/users");
  const result = await r.json();
  if (!r.ok) return toast(result.error);
  $("#crumb").textContent = "Operators";
  $("#content").innerHTML =
    heading(
      "ACCESS CONTROL",
      "Operators",
      "Administrator, manager, cashier and accountant roles are enforced by the backend.",
    ) +
    `<section class="card panel"><table><thead><tr><th>Operator</th><th>Role</th><th>Status</th></tr></thead><tbody>${result.users.map((u) => `<tr><td>${esc(u.username)}</td><td>${esc(u.role)}</td><td>${u.active ? "Active" : "Disabled"}</td></tr>`).join("")}</tbody></table><h2 style="margin-top:24px">Create operator</h2><form id="operatorForm" class="formgrid"><label>Name<input name="username" required maxlength="80" autocomplete="off"></label><label>Role<select name="role"><option>cashier</option><option>manager</option><option>accountant</option><option>pharmacist</option><option>admin</option></select></label><label class="wide">Password<input type="password" name="password" required minlength="12" maxlength="256" autocomplete="new-password"></label><div class="wide"><button class="btn">Create operator</button></div><p id="operatorError" role="alert"></p></form></section>`;
  $("#content").insertAdjacentHTML(
    "beforeend",
    `<section class="card panel" style="margin-top:20px"><h2>Update access</h2><p class="muted">Saving revokes this operator's sessions. Keep at least one active administrator.</p><form id="accessForm" class="formgrid"><label>Operator<select name="id">${result.users.map((u) => `<option value="${u.id}">${esc(u.username)}</option>`).join("")}</select></label><label>Role<select name="role">${["cashier", "manager", "accountant", "pharmacist", "admin"].map((r) => `<option>${r}</option>`).join("")}</select></label><label>Status<select name="active"><option value="true">Active</option><option value="false">Disabled</option></select></label><label>New password (leave blank to keep)<input name="password" type="password" minlength="12" autocomplete="new-password"></label><div class="wide"><button class="btn">Save access</button></div><p id="accessError" role="alert"></p></form></section>`,
  );
  for (const id of ["operatorForm", "accessForm"])
    document
      .querySelector("#" + id + " .wide")
      .insertAdjacentHTML(
        "beforebegin",
        '<label>Pharmacist registration (required for pharmacist role)<input name="registration" maxlength="160"></label>',
      );
  const syncAccess = () => {
    const user = result.users.find(
      (u) => String(u.id) === $("#accessForm [name=id]").value,
    );
    $("#accessForm [name=role]").value = user.role;
    $("#accessForm [name=registration]").value = user.registration || "";
    $("#accessForm [name=active]").value = String(Boolean(user.active));
  };
  $("#accessForm [name=id]").onchange = syncAccess;
  syncAccess();
  $("#accessForm").onsubmit = async (e) => {
    e.preventDefault();
    const d = Object.fromEntries(new FormData(e.target));
    d.active = d.active === "true";
    try {
      const r = await fetch("/api/users/update", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(d),
      });
      const response = await r.json();
      if (!r.ok) throw Error(response.error);
      if (Number(d.id) === state.operator.id) showSignIn(false);
      else operatorPage();
    } catch (error) {
      $("#accessError").textContent = error.message;
    }
  };
  $("#operatorForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await fetch("/api/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
      });
      const result = await r.json();
      if (!r.ok) throw Error(result.error);
      operatorPage();
    } catch (error) {
      $("#operatorError").textContent = error.message;
    }
  };
}
const operatorsNav = document.createElement("button");
operatorsNav.dataset.page = "operators";
operatorsNav.innerHTML = "<span>♙</span> Operators";
operatorsNav.onclick = () => go("operators");
document.querySelector("nav").append(operatorsNav);
fetch("/api/auth")
  .then((r) => r.json())
  .then(async (status) => {
    if (status.operator) await loadWorkspace();
    else showSignIn(status.needs_setup);
  })
  .catch(() => {
    $("#content").textContent =
      "The local database service is unavailable. Restart the desktop app.";
  });

paintIcons();
