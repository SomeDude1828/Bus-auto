function find() {
  const key = tomorrowKey();
  $("dateText").textContent = `Checking ${dateLabel(key)} · tomorrow`;

  const target = toMin($("arrival").value || "07:00");
  const day = schedule?.days?.[key];

  const results = [];

  for (const r of ROUTES) {
    const trips = [...(day?.[r.line] || [])]
      .map(x => ({
        ...r,
        ...x,
        distance: Math.abs(toMin(x.arr) - target)
      }))
      .sort((a, b) =>
        a.distance - b.distance ||
        toMin(a.arr) - toMin(b.arr)
      )
      .slice(0, OPTIONS_PER_ROUTE);

    results.push(...trips);
  }

  // Closest to target arrival time first
  results.sort((a, b) =>
    a.distance - b.distance ||
    (a.preferred ? -1 : 1) ||
    toMin(a.arr) - toMin(b.arr)
  );

  if (!results.length) {
    $("results").innerHTML =
      `<div class="card">No scheduled buses were found for tomorrow.</div>`;
    return;
  }

  $("results").innerHTML = results.map(r => {
    const dep = toMin(r.dep);
    const arr = toMin(r.arr);

    const wake = dep - WAKE_BEFORE;
    const backup = wake - BACKUP_BEFORE_WAKE;
    const leave = dep - HOME_TO_STOP;

    const diff = arr - target;

    const relation =
      diff === 0
        ? "exactly at target"
        : diff > 0
          ? `${diff} min after target`
          : `${Math.abs(diff)} min before target`;

    return `
      <article class="result ${r.preferred ? "best" : ""}">
        <div class="resultTop">
          <div class="route">🚌 ${esc(r.line)} → ${esc(r.dest)}</div>
          ${r.preferred ? '<div class="tag">PREFERRED</div>' : ''}
        </div>

        <div class="dest">
          Arrives at ${esc(r.dest)} at <b>${esc(r.arr)}</b>
          · ${relation}
        </div>

        <div class="grid">
          <div class="stat">
            <small>Bus at Polje</small>
            <b>${esc(r.dep)}</b>
          </div>

          <div class="stat">
            <small>Wake up</small>
            <b>${fromMin(wake)}</b>
          </div>

          <div class="stat">
            <small>Leave home</small>
            <b>${fromMin(leave)}</b>
          </div>

          <div class="stat">
            <small>Backup alarm</small>
            <b>${fromMin(backup)}</b>
          </div>
        </div>
      </article>
    `;
  }).join("");
}
