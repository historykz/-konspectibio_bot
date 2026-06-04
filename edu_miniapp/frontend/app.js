/* Образовательный центр — мини-приложение Telegram */

const tg = window.Telegram?.WebApp;
const ROLE_NAMES = {
  user: "Новичок",
  student: "Ученик",
  curator: "Куратор",
  admin: "Админ",
};

let STATE = { profile: null, menu: [] };

/* --- API: каждый запрос отправляет initData для проверки на сервере --- */
async function api(path, { method = "GET", body = null } = {}) {
  const res = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Init-Data": tg?.initData || "",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

/* --- Утилиты рендера --- */
const $ = (sel) => document.querySelector(sel);

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.entries(props).forEach(([k, v]) => {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  });
  (Array.isArray(children) ? children : [children]).forEach((c) => {
    if (c == null) return;
    node.append(c.nodeType ? c : document.createTextNode(c));
  });
  return node;
}

/* --- Экраны --- */
function renderHome() {
  hideBack();
  const content = $("#content");
  content.innerHTML = "";

  if (STATE.menu.length === 0) {
    content.append(
      el("div", { class: "notice", html:
        "<strong>Доступ ещё не открыт</strong>" +
        "Обратитесь к куратору или администратору, чтобы получить доступ к материалам.",
      })
    );
    return;
  }

  // Группируем пункты меню по полю group
  const groups = {};
  STATE.menu.forEach((m) => (groups[m.group] ??= []).push(m));

  Object.entries(groups).forEach(([groupName, items]) => {
    content.append(el("div", { class: "group-label" }, groupName));
    const tiles = el("div", { class: "tiles" });
    items.forEach((item) => {
      tiles.append(
        el("button", { class: "tile", onclick: () => openScreen(item.key) }, [
          el("span", { class: "icon" }, item.icon),
          el("span", {}, item.title),
        ])
      );
    });
    content.append(tiles);
  });
}

function showBack() {
  if (tg?.BackButton) {
    tg.BackButton.show();
    tg.BackButton.onClick(renderHome);
  }
}
function hideBack() {
  if (tg?.BackButton) tg.BackButton.hide();
}

async function openScreen(key) {
  showBack();
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("div", { class: "loader", html: '<div class="spinner"></div>' }));

  try {
    if (key === "profile") return renderProfile();
    if (key === "worksheets") return renderMaterials("/api/worksheets", "Рабочие тетради", true);
    if (key === "checklists") return renderMaterials("/api/checklists", "Чек-листы", false);
    if (key === "my_grades") return renderMyGrades();
    if (key === "journal") return renderCuratorJournals();
    if (key === "my_groups") return renderMyGroups();

    // Остальные экраны — заглушки каркаса (реализуются на следующих этапах)
    content.innerHTML = "";
    content.append(
      el("div", { class: "notice", html:
        `<strong>${labelFor(key)}</strong>Раздел в разработке — каркас готов, логику добавим на следующем шаге.`,
      })
    );
  } catch (e) {
    content.innerHTML = "";
    content.append(el("div", { class: "empty" }, `Ошибка: ${e.message}`));
  }
}

function labelFor(key) {
  const item = STATE.menu.find((m) => m.key === key);
  return item ? item.title : key;
}

async function renderMaterials(endpoint, title, sendable) {
  const { items } = await api(endpoint);
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("div", { class: "group-label" }, title));

  if (!items.length) {
    content.append(el("div", { class: "empty" }, "Пока ничего нет."));
    return;
  }

  const card = el("div", { class: "list-card" });
  items.forEach((it, i) => {
    const row = el("div", { class: "list-row" }, [
      el("span", { class: "num" }, String(i + 1)),
      el("span", { class: "title" }, it.title),
      el("span", { class: "ext" }, it.file_type || ""),
    ]);
    if (sendable) {
      row.addEventListener("click", async () => {
        try {
          await api(`/api/worksheets/${it.id}/send`, { method: "POST" });
          tg?.showPopup?.({ message: "Файл отправлен в чат 📄" });
        } catch (e) {
          tg?.showAlert?.(`Не удалось: ${e.message}`);
        }
      });
    }
    card.append(row);
  });
  content.append(card);
}

async function renderMyGrades() {
  const { journals } = await api("/api/my-grades");
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("div", { class: "group-label" }, "Мои баллы"));

  if (!journals.length) {
    content.append(el("div", { class: "empty" }, "Пока нет ни одного журнала."));
    return;
  }

  journals.forEach((j) => {
    const medal = j.rank === 1 ? "🥇" : j.rank === 2 ? "🥈" : j.rank === 3 ? "🥉" : "🏅";

    const head = el("div", { class: "j-head" }, [
      el("div", {}, [
        el("div", { class: "j-title" }, j.journal),
        el("div", { class: "j-sub" }, j.group),
      ]),
      el("div", { class: "j-rank" }, `${medal} ${j.rank ?? "—"}/${j.group_size}`),
    ]);

    // Итоговая сводка: набрано / максимум / процент
    const summary = el("div", { class: "j-summary" }, [
      metric("Набрано", j.total),
      metric("Максимум", j.max_total),
      metric("Процент", j.percent + "%"),
    ]);

    // Список уроков
    const rows = el("div", { class: "list-card" });
    j.lessons.forEach((l) => {
      const got = l.score == null ? "—" : l.score;
      rows.append(
        el("div", { class: "list-row" }, [
          el("span", { class: "title" }, l.topic),
          el("span", { class: "score" }, `${got} / ${l.max_score}`),
        ])
      );
    });

    const card = el("div", { class: "j-card" }, [head, summary, rows]);
    content.append(card);
  });
}

function metric(label, value) {
  return el("div", { class: "metric" }, [
    el("div", { class: "m-label" }, label),
    el("div", { class: "m-value" }, String(value)),
  ]);
}

async function renderCuratorJournals() {
  const { items } = await api("/api/curator/journals");
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("div", { class: "group-label" }, "Журнал оценок"));

  if (!items.length) {
    content.append(
      el("div", { class: "notice", html:
        "<strong>Журналов пока нет</strong>Создайте журнал для группы, затем " +
        "отправьте боту выгрузку из Google Sheets (.xlsx или .csv) — бот сам распознает оценки.",
      })
    );
    return;
  }

  const card = el("div", { class: "list-card" });
  items.forEach((j) => {
    const row = el("div", { class: "list-row" }, [
      el("span", { class: "title" }, [
        j.title,
        el("div", { class: "j-sub" }, j.group_name),
      ]),
      el("i", { class: "chev" }, "›"),
    ]);
    row.addEventListener("click", () => renderJournalGrid(j));
    card.append(row);
  });
  content.append(card);

  content.append(
    el("div", { class: "hint-box" },
      "💡 Чтобы загрузить оценки — отправьте боту файл Google-таблицы (.xlsx/.csv). " +
      "Первая строка — темы уроков, вторая — максимальные баллы, дальше ученики.")
  );
}

async function renderJournalGrid(j) {
  const content = $("#content");
  content.innerHTML = "";
  const back = j.group_id !== undefined && j._from === "group"
    ? () => openGroup({ id: j.group_id, name: j.group_name })
    : () => renderCuratorJournals();
  content.append(el("button", { class: "back", onclick: back }, "‹ Назад"));
  content.append(el("div", { class: "group-label" }, `${j.group_name} · ${j.title}`));

  // Форма добавления урока (столбца)
  const topicInp = el("input", { class: "inp", placeholder: "Тема урока" });
  const maxInp = el("input", { class: "inp inp-num", type: "number", placeholder: "Макс", min: "0" });
  const addBtn = el("button", { class: "btn-primary" }, "+ Урок");
  addBtn.addEventListener("click", async () => {
    const topic = topicInp.value.trim();
    const max_score = maxInp.value.trim();
    if (!topic || !max_score) return tg?.showAlert?.("Введите тему и максимальный балл");
    try {
      await api(`/api/curator/journals/${j.id}/lessons`, { method: "POST", body: { topic, max_score } });
      renderJournalGrid(j);
    } catch (e) { tg?.showAlert?.(e.message); }
  });
  content.append(el("div", { class: "form-row" }, [topicInp, maxInp, addBtn]));

  const grid = await api(`/api/curator/journals/${j.id}/grid?group_id=${j.group_id}`);
  if (!grid.lessons.length) {
    content.append(el("div", { class: "empty" }, "Добавьте первый урок выше или импортируйте таблицу через бота."));
    return;
  }

  const wrap = el("div", { class: "grid-scroll" });
  const table = el("table", { class: "gtable" });

  const thead = el("tr", {}, [el("th", { class: "sticky" }, "Ученик")]);
  grid.lessons.forEach((l) => thead.append(el("th", { title: `${l.topic} (макс ${l.max_score})` }, l.topic)));
  thead.append(el("th", {}, "Σ"));
  table.append(thead);

  grid.rows.forEach((r) => {
    const tr = el("tr", {}, [el("td", { class: "sticky" }, r.name)]);
    r.cells.forEach((c, i) => {
      const lesson = grid.lessons[i];
      const td = el("td", { class: "cell-edit" }, c == null ? "·" : String(c));
      td.addEventListener("click", () => editCell(td, lesson, r.student_id));
      tr.append(td);
    });
    tr.append(el("td", { class: "sum" }, String(r.total)));
    table.append(tr);
  });

  wrap.append(table);
  content.append(wrap);
  content.append(el("div", { class: "hint-box" }, "Нажмите на ячейку, чтобы поставить или изменить балл."));
}

function editCell(td, lesson, studentId) {
  const old = td.textContent === "·" ? "" : td.textContent;
  const inp = el("input", { class: "cell-input", type: "number", value: old, min: "0", max: String(lesson.max_score) });
  td.textContent = "";
  td.append(inp);
  inp.focus();
  inp.select();

  const commit = async () => {
    const val = inp.value.trim();
    try {
      await api("/api/curator/grades", {
        method: "POST",
        body: { lesson_id: lesson.id, student_id: studentId, score: val === "" ? null : val },
      });
      td.textContent = val === "" ? "·" : val;
      // обновим сумму строки
      const row = td.parentElement;
      let s = 0;
      row.querySelectorAll(".cell-edit").forEach((c) => { const n = parseFloat(c.textContent); if (!isNaN(n)) s += n; });
      row.querySelector(".sum").textContent = String(Math.round(s * 100) / 100);
    } catch (e) {
      td.textContent = old || "·";
      tg?.showAlert?.(e.message);
    }
  };
  inp.addEventListener("blur", commit);
  inp.addEventListener("keydown", (e) => { if (e.key === "Enter") inp.blur(); });
}

/* --- Мои группы (куратор) --- */
async function renderMyGroups() {
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("div", { class: "group-label" }, "Мои группы"));

  // Форма создания группы
  const nameInp = el("input", { class: "inp", placeholder: "Название группы, напр. 11-А" });
  const createBtn = el("button", { class: "btn-primary" }, "Создать");
  createBtn.addEventListener("click", async () => {
    const name = nameInp.value.trim();
    if (!name) return;
    try {
      await api("/api/curator/groups", { method: "POST", body: { name } });
      renderMyGroups();
    } catch (e) { tg?.showAlert?.(e.message); }
  });
  content.append(el("div", { class: "form-row" }, [nameInp, createBtn]));

  const { items } = await api("/api/curator/groups");
  if (!items.length) {
    content.append(el("div", { class: "empty" }, "Групп пока нет — создайте первую выше."));
    return;
  }
  const card = el("div", { class: "list-card" });
  items.forEach((g) => {
    const row = el("div", { class: "list-row" }, [
      el("span", { class: "title" }, g.name),
      el("span", { class: "ext" }, `${g.students} уч.`),
      el("i", { class: "chev" }, "›"),
    ]);
    row.addEventListener("click", () => openGroup(g));
    card.append(row);
  });
  content.append(card);
}

async function openGroup(g) {
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("button", { class: "back", onclick: () => renderMyGroups() }, "‹ К группам"));
  content.append(el("div", { class: "group-label" }, g.name));

  const data = await api(`/api/curator/groups/${g.id}/students`);

  // Журналы группы + создание журнала
  content.append(el("div", { class: "sub-label" }, "Журналы"));
  const jcard = el("div", { class: "list-card" });
  data.journals.forEach((j) => {
    const row = el("div", { class: "list-row" }, [
      el("span", { class: "title" }, j.title),
      el("i", { class: "chev" }, "›"),
    ]);
    row.addEventListener("click", () =>
      renderJournalGrid({ id: j.id, title: j.title, group_id: g.id, group_name: g.name, _from: "group" }));
    jcard.append(row);
  });
  if (data.journals.length) content.append(jcard);

  const jInp = el("input", { class: "inp", placeholder: "Новый журнал, напр. Биология" });
  const jBtn = el("button", { class: "btn-primary" }, "+");
  jBtn.addEventListener("click", async () => {
    const title = jInp.value.trim();
    if (!title) return;
    try {
      await api(`/api/curator/groups/${g.id}/journals`, { method: "POST", body: { title } });
      openGroup(g);
    } catch (e) { tg?.showAlert?.(e.message); }
  });
  content.append(el("div", { class: "form-row" }, [jInp, jBtn]));

  // Ученики
  content.append(el("div", { class: "sub-label" }, `Ученики (${data.students.length})`));
  const scard = el("div", { class: "list-card" });
  data.students.forEach((s, i) => {
    const up = el("button", { class: "mini-btn" }, "↑");
    const down = el("button", { class: "mini-btn" }, "↓");
    up.addEventListener("click", (e) => { e.stopPropagation(); moveStudent(g, data.students, i, -1); });
    down.addEventListener("click", (e) => { e.stopPropagation(); moveStudent(g, data.students, i, 1); });
    const del = el("button", { class: "mini-btn danger" }, "✕");
    del.addEventListener("click", async (e) => {
      e.stopPropagation();
      const ok = await confirmAsync(`Удалить ученика «${s.name}» из группы?`);
      if (!ok) return;
      await api(`/api/curator/groups/${g.id}/students/${s.student_id}`, { method: "DELETE" });
      openGroup(g);
    });
    const row = el("div", { class: "list-row" }, [
      el("span", { class: "num" }, String(i + 1)),
      el("span", { class: "title", onclick: () => renameStudent(g, s) }, [
        s.name,
        s.username ? el("div", { class: "j-sub" }, "@" + s.username) : null,
      ]),
      up, down, del,
    ]);
    scard.append(row);
  });
  if (data.students.length) content.append(scard);

  // Добавление ученика
  const idInp = el("input", { class: "inp", placeholder: "Telegram ID или @username" });
  const fioInp = el("input", { class: "inp", placeholder: "ФИО (для журнала)" });
  const addBtn = el("button", { class: "btn-primary" }, "Добавить");
  addBtn.addEventListener("click", async () => {
    const identifier = idInp.value.trim();
    if (!identifier) return;
    try {
      await api(`/api/curator/groups/${g.id}/students`, {
        method: "POST",
        body: { identifier, full_name: fioInp.value.trim() },
      });
      openGroup(g);
    } catch (e) { tg?.showAlert?.(e.message); }
  });
  content.append(el("div", { class: "sub-label" }, "Добавить ученика"));
  content.append(el("div", { class: "form-col" }, [idInp, fioInp, addBtn]));
}

async function moveStudent(g, students, i, dir) {
  const j = i + dir;
  if (j < 0 || j >= students.length) return;
  const order = students.map((s) => s.student_id);
  [order[i], order[j]] = [order[j], order[i]];
  await api(`/api/curator/groups/${g.id}/reorder`, { method: "POST", body: { order } });
  openGroup(g);
}

function renameStudent(g, s) {
  const inp = el("input", { class: "inp", value: s.name === "—" ? "" : s.name, placeholder: "ФИО" });
  const save = el("button", { class: "btn-primary" }, "OK");
  save.addEventListener("click", async () => {
    await api(`/api/curator/groups/${g.id}/students/${s.student_id}`, {
      method: "PATCH", body: { full_name: inp.value.trim() },
    });
    openGroup(g);
  });
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("button", { class: "back", onclick: () => openGroup(g) }, "‹ Отмена"));
  content.append(el("div", { class: "group-label" }, "ФИО ученика"));
  content.append(el("div", { class: "form-col" }, [inp, save]));
  inp.focus();
}

function confirmAsync(message) {
  return new Promise((resolve) => {
    if (tg?.showConfirm) tg.showConfirm(message, (ok) => resolve(ok));
    else resolve(window.confirm(message));
  });
}


function renderProfile() {
  const p = STATE.profile;
  const content = $("#content");
  content.innerHTML = "";
  content.append(el("div", { class: "group-label" }, "Мой профиль"));

  const rows = [
    ["Имя", p.first_name || "—"],
    ["Username", p.username ? "@" + p.username : "—"],
    ["Telegram ID", String(p.telegram_id)],
    ["Роль", ROLE_NAMES[p.role] || p.role],
    ["Группа", p.group_name || "—"],
    ["Куратор", p.curator_name || "—"],
    ["Доступ", p.has_access ? "✅ открыт" : "⛔️ закрыт"],
  ];
  const card = el("div", { class: "profile-card" });
  rows.forEach(([k, v]) =>
    card.append(
      el("div", { class: "profile-row" }, [
        el("span", { class: "k" }, k),
        el("span", { class: "v" }, v),
      ])
    )
  );
  content.append(card);
}

/* --- Запуск --- */
async function init() {
  tg?.ready();
  tg?.expand();

  try {
    const data = await api("/api/me", { method: "POST" });
    STATE = data;
    const p = data.profile;
    $("#hello").textContent = p.first_name ? `Привет, ${p.first_name}!` : "Привет!";
    $("#roleBadge").textContent = ROLE_NAMES[p.role] || p.role;
    renderHome();
  } catch (e) {
    $("#hello").textContent = "Ошибка входа";
    $("#content").innerHTML = "";
    $("#content").append(
      el("div", { class: "notice", html:
        `<strong>Не удалось войти</strong>${e.message}. Откройте приложение из Telegram.`,
      })
    );
  }
}

init();
