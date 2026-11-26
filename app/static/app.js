const exprEl = document.getElementById("expr");
const valueEl = document.getElementById("value");
const listEl = document.getElementById("historyList");
const toastEl = document.getElementById("toast");

let current = "";
let justEvaluated = false;

function render() {
  valueEl.textContent = current || "0";
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toastEl.classList.remove("show"), 2800);
}

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "Error");
  return data;
}

function press(val) {
  const isOp = "+-×÷%".includes(val);
  if (justEvaluated && !isOp) current = "";
  justEvaluated = false;
  current += val;
  render();
}

async function equals() {
  if (!current) return;
  try {
    const entry = await api("/api/calculate", {
      method: "POST",
      body: JSON.stringify({ expression: current }),
    });
    exprEl.textContent = entry.expression + " =";
    current = String(entry.result);
    justEvaluated = true;
    render();
    loadHistory();
  } catch (e) {
    exprEl.textContent = e.message;
  }
}

function renderHistory(items) {
  listEl.innerHTML = "";
  if (!items.length) {
    listEl.innerHTML = '<li class="empty" style="cursor:default">Sin cálculos aún</li>';
    return;
  }
  [...items].reverse().forEach((it) => {
    const li = document.createElement("li");
    const time = new Date(it.timestamp).toLocaleString("es-CL");
    li.innerHTML = `<div class="h-expr"></div><div class="h-res"></div><div class="h-time"></div>`;
    li.querySelector(".h-expr").textContent = it.expression + " =";
    li.querySelector(".h-res").textContent = it.result;
    li.querySelector(".h-time").textContent = time;
    li.title = "Usar este resultado";
    li.onclick = () => { current = String(it.result); justEvaluated = true; render(); };
    listEl.appendChild(li);
  });
}

async function loadHistory() {
  const data = await api("/api/history");
  renderHistory(data.history);
}

document.querySelectorAll("[data-val]").forEach((b) =>
  b.addEventListener("click", () => press(b.dataset.val))
);
document.querySelector('[data-action="clear"]').onclick = () => {
  current = ""; exprEl.textContent = ""; render();
};
document.querySelector('[data-action="back"]').onclick = () => {
  current = current.slice(0, -1); render();
};
document.querySelector('[data-action="equals"]').onclick = equals;

document.addEventListener("keydown", (e) => {
  const map = { "*": "×", "/": "÷" };
  if (/^[0-9.+\-%()]$/.test(e.key)) press(e.key);
  else if (map[e.key]) press(map[e.key]);
  else if (e.key === "Enter" || e.key === "=") { e.preventDefault(); equals(); }
  else if (e.key === "Backspace") { current = current.slice(0, -1); render(); }
  else if (e.key === "Escape") { current = ""; exprEl.textContent = ""; render(); }
});

document.getElementById("saveBtn").onclick = async () => {
  try {
    const r = await api("/api/save", { method: "POST" });
    toast(`Guardado ${r.total} cálculo(s) en ${r.file}`);
  } catch (e) { toast(e.message); }
};

document.getElementById("clearBtn").onclick = async () => {
  if (!confirm("¿Borrar el historial?")) return;
  await api("/api/history", { method: "DELETE" });
  loadHistory();
};

render();
loadHistory();
