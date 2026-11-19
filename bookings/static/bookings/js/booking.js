// Keeps the booking summary and day buttons in step with what the client picks.
(function () {
  const form = document.getElementById("booking-form") || document.getElementById("reschedule-form");
  if (!form) return;

  const set = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  form.addEventListener("change", (event) => {
    const input = event.target;
    if (input.name === "service") {
      const d = input.dataset;
      set("sum-service", d.name);
      set("sum-price", d.price);
      set("sum-deposit", d.deposit);
      set("sum-duration", d.duration);
      set("sum-time", "Not chosen");
      const note = document.getElementById("patch-note");
      if (note) note.hidden = d.patch !== "1";
    }
    if (input.name === "start") {
      set("sum-time", input.dataset.label);
    }
  });

  // show which day is selected
  form.addEventListener("click", (event) => {
    const day = event.target.closest(".day");
    if (!day || day.disabled) return;
    form.querySelectorAll(".day").forEach((b) => b.setAttribute("aria-pressed", "false"));
    day.setAttribute("aria-pressed", "true");
    set("sum-time", "Not chosen");
  });
})();
