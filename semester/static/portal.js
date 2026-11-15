(() => {
  "use strict";

  const THEME_KEY = "semester_theme";
  const media = window.matchMedia("(prefers-color-scheme: dark)");

  function storedMode() {
    try {
      const val = localStorage.getItem(THEME_KEY);
      if (val === "light" || val === "dark") return val;
    } catch {
      /* ignore storage errors */
    }
    const attr = document.documentElement.getAttribute("data-theme");
    return attr === "light" || attr === "dark" ? attr : "system";
  }

  function resolvedTheme(mode = storedMode()) {
    return mode === "system" ? (media.matches ? "dark" : "light") : mode;
  }

  function syncThemeLabels(theme) {
    const label = theme === "dark" ? "Включить светлую тему" : "Включить тёмную тему";
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-label", label);
      btn.setAttribute("title", label);
    });
  }

  function applyTheme(theme, persistCookie = false) {
    const root = document.documentElement;
    root.setAttribute("data-theme", theme);
    if (persistCookie) {
      document.cookie = `${THEME_KEY}=${theme}; path=/; max-age=31536000; SameSite=Lax`;
    }
    syncThemeLabels(theme);
  }

  // Initial sync without flashing
  const initialMode = storedMode();
  if (initialMode !== "system") {
    applyTheme(initialMode, false);
  } else {
    syncThemeLabels(resolvedTheme("system"));
  }

  media.addEventListener("change", () => {
    if (storedMode() === "system") {
      document.documentElement.removeAttribute("data-theme");
      syncThemeLabels(resolvedTheme("system"));
    }
  });

  function toggleTheme(origin) {
    const current = resolvedTheme();
    const next = current === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      /* ignore */
    }

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced || !origin || typeof Element.prototype.animate !== "function") {
      applyTheme(next, true);
      return;
    }

    const rect = origin.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const far = Math.hypot(Math.max(cx, window.innerWidth - cx), Math.max(cy, window.innerHeight - cy));

    const svgNs = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(svgNs, "svg");
    svg.setAttribute("class", "theme-wave");
    svg.setAttribute("aria-hidden", "true");
    const circle = document.createElementNS(svgNs, "circle");
    circle.setAttribute("cx", String(cx));
    circle.setAttribute("cy", String(cy));
    circle.setAttribute("r", String(far));
    circle.setAttribute("class", current === "dark" ? "wave-from-dark" : "wave-from-light");
    svg.appendChild(circle);
    document.body.appendChild(svg);

    applyTheme(next, true);

    circle
      .animate([{ r: `${far}px` }, { r: "0px" }], {
        duration: 540,
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        fill: "forwards",
      })
      .finished.catch(() => {})
      .then(() => svg.remove());
  }

  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => toggleTheme(btn));
  });

  // Password visibility toggle on /login
  document.querySelectorAll("[data-password-toggle]").forEach((btn) => {
    const input = document.getElementById(btn.getAttribute("aria-controls") || "password");
    if (!input) return;
    btn.hidden = false;
    const openIcon = btn.querySelector(".eye-open");
    const closedIcon = btn.querySelector(".eye-closed");
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      if (openIcon) openIcon.hidden = show;
      if (closedIcon) closedIcon.hidden = !show;
      const text = show ? "Скрыть пароль" : "Показать пароль";
      btn.setAttribute("aria-label", text);
      btn.setAttribute("title", text);
    });
  });

  // One-click demo account fill on /login
  document.querySelectorAll("[data-demo-email]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const emailInput = document.getElementById("email");
      const passInput = document.getElementById("password");
      if (!emailInput || !passInput) return;
      emailInput.value = btn.getAttribute("data-demo-email") || "";
      passInput.value = btn.getAttribute("data-demo-password") || "";
      const submitBtn = document.querySelector("#login-form button[type='submit']");
      if (submitBtn) submitBtn.focus();
    });
  });

  // Segmented controls (.seg) with sliding rounded-square thumb (pure data-index, zero inline style)
  function activateSegButton(seg, btn) {
    const idx = btn.getAttribute("data-seg-idx") || "0";
    seg.setAttribute("data-index", idx);
    seg.querySelectorAll(".seg-item").forEach((el) => {
      el.classList.toggle("is-active", el === btn);
    });
  }

  // Grades filter
  const gradeSeg = document.querySelector("[data-grade-filters]");
  if (gradeSeg) {
    gradeSeg.hidden = false;
    gradeSeg.querySelectorAll("[data-grade-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateSegButton(gradeSeg, btn);
        const mode = btn.getAttribute("data-grade-filter");
        document.querySelectorAll("[data-grade-state]").forEach((row) => {
          row.hidden = mode !== "all" && row.getAttribute("data-grade-state") !== mode;
        });
      });
    });
  }

  // Notifications filter
  const noticeSeg = document.querySelector("[data-notice-filters]");
  if (noticeSeg) {
    noticeSeg.hidden = false;
    noticeSeg.querySelectorAll("[data-notice-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateSegButton(noticeSeg, btn);
        const mode = btn.getAttribute("data-notice-filter");
        document.querySelectorAll("[data-notice-kind]").forEach((row) => {
          if (mode === "all") {
            row.hidden = false;
          } else if (mode === "unread") {
            row.hidden = !row.hasAttribute("data-unread");
          } else {
            row.hidden = row.getAttribute("data-notice-kind") !== mode;
          }
        });
      });
    });
  }

  // Staff queue filter
  const staffSeg = document.querySelector("[data-staff-filters]");
  if (staffSeg) {
    staffSeg.hidden = false;
    staffSeg.querySelectorAll("[data-staff-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activateSegButton(staffSeg, btn);
        const mode = btn.getAttribute("data-staff-filter");
        document.querySelectorAll("[data-staff-state]").forEach((row) => {
          row.hidden = mode !== "all" && row.getAttribute("data-staff-state") !== mode;
        });
      });
    });
  }

  // Copy request code button
  document.querySelectorAll("[data-copy-text]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = btn.getAttribute("data-copy-text") || "";
      if (!value || !navigator.clipboard) return;
      try {
        await navigator.clipboard.writeText(value);
        btn.setAttribute("title", `Скопировано: #${value}`);
      } catch {
        /* ignore clipboard restrictions */
      }
    });
  });

  // Print button on /requests/<id>/document
  document.querySelectorAll("[data-print]").forEach((btn) => {
    btn.hidden = false;
    btn.addEventListener("click", () => window.print());
  });

  // Live countdown on pending requests
  const timerBox = document.querySelector("[data-countdown]");
  if (timerBox) {
    let remaining = parseInt(timerBox.getAttribute("data-countdown") || "0", 10);
    const out = timerBox.querySelector("[data-countdown-value]");
    if (remaining > 0 && out) {
      const id = window.setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          window.clearInterval(id);
          window.location.reload();
          return;
        }
        const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
        const ss = String(remaining % 60).padStart(2, "0");
        out.textContent = `${mm}:${ss}`;
      }, 1000);
    }
  }

  // Modals: Command Palette (⌘K / Ctrl+K) and Campus Pass QR
  const cmdDialog = document.getElementById("cmd-palette");
  const cmdInput = document.getElementById("cmd-input");
  const cmdEmpty = document.getElementById("cmd-empty");
  const passDialog = document.getElementById("pass-modal");

  function openDialog(dlg) {
    if (!dlg || typeof dlg.showModal !== "function" || dlg.open) return;
    dlg.showModal();
  }

  document.querySelectorAll("[data-open-cmd]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openDialog(cmdDialog);
      if (cmdInput) cmdInput.focus();
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
    dlg.addEventListener("click", (ev) => {
      if (ev.target === dlg) dlg.close();
    });
  });

  if (cmdDialog && cmdInput) {
    document.addEventListener("keydown", (ev) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") {
        ev.preventDefault();
        if (cmdDialog.open) {
          cmdDialog.close();
        } else {
          openDialog(cmdDialog);
          cmdInput.focus();
        }
      }
    });

    cmdInput.addEventListener("input", () => {
      const q = cmdInput.value.trim().toLowerCase();
      let visible = 0;
      cmdDialog.querySelectorAll("[data-cmd-item]").forEach((item) => {
        const hay = item.getAttribute("data-search") || "";
        const match = !q || hay.includes(q);
        item.hidden = !match;
        if (match) visible += 1;
      });
      if (cmdEmpty) cmdEmpty.hidden = visible > 0;
    });
  }
})();
