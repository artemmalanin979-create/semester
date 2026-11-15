(() => {
  const root = document.documentElement;
  const THEME_KEY = "semester-theme";

  function currentSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    if (theme === "dark" || theme === "light") {
      root.setAttribute("data-theme", theme);
    } else {
      root.removeAttribute("data-theme");
    }
  }

  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") {
      applyTheme(saved);
    }
  } catch {
    /* Storage blocked in strict privacy mode */
  }

  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const active = root.getAttribute("data-theme") || currentSystemTheme();
      const next = active === "dark" ? "light" : "dark";
      applyTheme(next);
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        /* Ignore */
      }
    });
  });

  /* Password visibility toggle on /login */
  const toggle = document.querySelector("[data-password-toggle]");
  const password = document.getElementById("password");
  if (toggle && password) {
    toggle.hidden = false;
    const eyeOpen = toggle.querySelector(".eye-open");
    const eyeClosed = toggle.querySelector(".eye-closed");
    toggle.addEventListener("click", () => {
      const reveal = password.type === "password";
      password.type = reveal ? "text" : "password";
      toggle.setAttribute("aria-label", reveal ? "Скрыть пароль" : "Показать пароль");
      if (eyeOpen && eyeClosed) {
        eyeOpen.hidden = reveal;
        eyeClosed.hidden = !reveal;
      }
    });
  }

  /* 1-click demo account switcher on /login */
  const emailInput = document.getElementById("email");
  const demoButtons = document.querySelectorAll("[data-demo-email]");
  if (emailInput && password && demoButtons.length) {
    demoButtons.forEach((btn) => {
      btn.addEventListener("click", () => {
        emailInput.value = btn.dataset.demoEmail || "";
        password.value = btn.dataset.demoPassword || "";
        demoButtons.forEach((b) => b.classList.toggle("is-picked", b === btn));
        const submit = document.querySelector('#login-form button[type="submit"]');
        if (submit) submit.focus();
      });
    });
  }

  /* Print trigger on /requests/<id>/document */
  const printButton = document.querySelector("[data-print]");
  if (printButton && typeof window.print === "function") {
    printButton.hidden = false;
    printButton.addEventListener("click", () => window.print());
  }

  /* Copy request ID button */
  document.querySelectorAll("[data-copy-text]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = btn.dataset.copyText || "";
      if (!value || !navigator.clipboard) return;
      try {
        await navigator.clipboard.writeText(value);
        btn.setAttribute("title", "Скопировано: #" + value);
      } catch {
        /* Ignore clipboard permission errors */
      }
    });
  });

  /* Live MM:SS countdown + auto-reload when request finishes processing */
  const refresh = document.querySelector("[data-refresh-seconds]");
  const countdownBox = document.querySelector("[data-countdown]");
  const countdownOut = document.querySelector("[data-countdown-value]");
  if (refresh) {
    let remaining = Math.max(1, Number(refresh.dataset.refreshSeconds || 0));
    if (countdownBox && countdownOut) {
      const tick = window.setInterval(() => {
        remaining = Math.max(0, remaining - 1);
        const mins = String(Math.floor(remaining / 60)).padStart(2, "0");
        const secs = String(remaining % 60).padStart(2, "0");
        countdownOut.textContent = `${mins}:${secs}`;
        if (remaining <= 0) {
          window.clearInterval(tick);
        }
      }, 1000);
    }
    window.setTimeout(() => window.location.reload(), (remaining + 1) * 1000);
  }

  /* Discipline filters on /grades */
  const gradeFilterBar = document.querySelector("[data-grade-filters]");
  if (gradeFilterBar) {
    const buttons = gradeFilterBar.querySelectorAll("[data-grade-filter]");
    const rows = document.querySelectorAll("[data-grade-state]");
    gradeFilterBar.hidden = false;
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.gradeFilter;
        buttons.forEach((b) => b.classList.toggle("active", b === btn));
        rows.forEach((row) => {
          row.hidden = mode !== "all" && row.dataset.gradeState !== mode;
        });
      });
    });
  }

  /* Notification category filters on /notifications */
  const noticeFilterBar = document.querySelector("[data-notice-filters]");
  if (noticeFilterBar) {
    const buttons = noticeFilterBar.querySelectorAll("[data-notice-filter]");
    const rows = document.querySelectorAll(".notice-row[data-notice-kind]");
    noticeFilterBar.hidden = false;
    buttons.forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.dataset.noticeFilter;
        buttons.forEach((b) => b.classList.toggle("active", b === btn));
        rows.forEach((row) => {
          if (mode === "all") {
            row.hidden = false;
          } else if (mode === "unread") {
            row.hidden = !row.hasAttribute("data-unread");
          } else {
            row.hidden = row.dataset.noticeKind !== mode;
          }
        });
      });
    });
  }

  /* Native <dialog> helpers: Command Palette (Cmd+K) & Campus Pass QR */
  const cmdDialog = document.getElementById("cmd-palette");
  const cmdInput = document.getElementById("cmd-input");
  const cmdEmpty = document.getElementById("cmd-empty");
  const cmdItems = document.querySelectorAll("[data-cmd-item]");
  const passDialog = document.getElementById("pass-modal");

  function openDialog(dlg) {
    if (!dlg || typeof dlg.showModal !== "function" || dlg.open) return;
    dlg.showModal();
  }

  document.querySelectorAll("[data-open-cmd]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openDialog(cmdDialog);
      if (cmdInput) {
        cmdInput.value = "";
        cmdItems.forEach((el) => { el.hidden = false; });
        if (cmdEmpty) cmdEmpty.hidden = true;
        cmdInput.focus();
      }
    });
  });

  document.querySelectorAll("[data-open-pass]").forEach((btn) => {
    btn.addEventListener("click", () => openDialog(passDialog));
  });

  document.querySelectorAll("[data-close-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const dlg = btn.closest("dialog");
      if (dlg && dlg.open) dlg.close();
    });
  });

  [cmdDialog, passDialog].forEach((dlg) => {
    if (!dlg) return;
    dlg.addEventListener("click", (event) => {
      if (event.target === dlg) dlg.close();
    });
  });

  if (cmdDialog && cmdInput) {
    cmdInput.addEventListener("input", () => {
      const q = cmdInput.value.trim().toLowerCase();
      let visible = 0;
      cmdItems.forEach((item) => {
        const hay = item.dataset.search || "";
        const match = !q || hay.includes(q);
        item.hidden = !match;
        if (match) visible += 1;
      });
      if (cmdEmpty) cmdEmpty.hidden = visible > 0;
    });

    cmdItems.forEach((item) => {
      item.addEventListener("click", () => {
        if (cmdDialog.open) cmdDialog.close();
      });
    });

    document.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (cmdDialog.open) {
          cmdDialog.close();
        } else {
          openDialog(cmdDialog);
          cmdInput.focus();
        }
      }
    });
  }
})();
