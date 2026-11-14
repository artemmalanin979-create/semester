const passwordToggle = document.querySelector("[data-password-toggle]");
if (passwordToggle) {
  const input = document.getElementById(passwordToggle.getAttribute("aria-controls"));
  passwordToggle.hidden = false;
  passwordToggle.addEventListener("click", () => {
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    passwordToggle.textContent = reveal ? "Скрыть" : "Показать";
  });
}

const printButton = document.querySelector("[data-print]");
if (printButton) {
  printButton.hidden = false;
  printButton.addEventListener("click", () => window.print());
}
