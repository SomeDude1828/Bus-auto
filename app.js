const ROUTES = [
  { line: "27", dest: "Konzorcij", preferred: true },
  { line: "11", dest: "Drama", preferred: false },
  { line: "25", dest: "Bavarski dvor", preferred: false }
];

const WAKE_BEFORE = 20;
const HOME_TO_STOP = 8;
const BACKUP_BEFORE_WAKE = 15;
const OPTIONS_PER_ROUTE = 3;

const $ = id => document.getElementById(id);

let schedule = null;


// ---------------------------------------------------------
// Date / time helpers
// ---------------------------------------------------------

function tomorrowKey() {
  const d = new Date();

  d.setDate(d.getDate() + 1);

  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");

  return `${y}${m}${day}`;
}


function dateLabel(key) {
  const formatted =
    `${key.slice(0, 4)}-${key.slice(4, 6)}-${key.slice(6, 8)}`;

  return new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short"
  }).format(
    new Date(formatted + "T12:00:00")
  );
}


function toMin(s) {
  const [h, m] = s.split(":").map(Number);
  return h * 60 + m;
}


function fromMin(n) {
  n = ((n % 1440) + 1440) % 1440;

  return (
    String(Math.floor(n / 60)).padStart(2, "0") +
    ":" +
    String(n % 60).padStart(2, "0")
  );
}


function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}


// ---------------------------------------------------------
// Load timetable
// ---------------------------------------------------------

async function load() {

  try {

    const r = await fetch(
      `data.json?${Date.now()}`,
      {
        cache: "no-store"
      }
    );

    if (!r.ok) {
      throw new Error(`data.json ${r.status}`);
    }

    schedule = await r.json();

    const count =
      Object.values(
        schedule.days || {}
      ).reduce(
        (total, day) =>
          total +
          Object.values(day).reduce(
            (sum, trips) =>
              sum + trips.length,
            0
          ),
        0
      );

    $("status").textContent =
      `Timetable updated ${
        schedule.generated_at
          ? new Date(
              schedule.generated_at
            ).toLocaleString()
          : ""
      } · ${count} trips loaded`;

  } catch (e) {

    console.error(e);

    $("status").textContent =
      "Could not load timetable data.";
  }

  find();
}


// ---------------------------------------------------------
// Find buses
// ---------------------------------------------------------

function find() {

  const key = tomorrowKey();

  $("dateText").textContent =
    `Checking ${dateLabel(key)} · tomorrow`;

  const target =
    toMin(
      $("arrival").value ||
      "07:00"
    );

  const day =
    schedule?.days?.[key];

  // -------------------------------------------------------
  // No timetable for tomorrow
  // -------------------------------------------------------

  if (!day) {

    $("results").innerHTML = `
      <div class="card">
        No timetable data is available for tomorrow
        (${dateLabel(key)}).
      </div>
    `;

    return;
  }


  const results = [];


  // -------------------------------------------------------
  // Process each route separately
  // -------------------------------------------------------

  for (const route of ROUTES) {

    const trips =
      [...(
        day[route.line] || []
      )];


    if (!trips.length) {
      continue;
    }


    // -----------------------------------------------------
    // Split buses into:
    //
    // 1. At/after target
    // 2. Before target
    //
    // This makes the "next bus" the primary choice.
    // -----------------------------------------------------

    const after = trips
      .filter(
        x => toMin(x.arr) >= target
      )
      .sort(
        (a, b) =>
          toMin(a.arr) -
          toMin(b.arr)
      );


    const before = trips
      .filter(
        x => toMin(x.arr) < target
      )
      .sort(
        (a, b) =>
          toMin(b.arr) -
          toMin(a.arr)
      );


    // -----------------------------------------------------
    // Desired ordering:
    //
    // First: closest bus AT/AFTER target
    // Then: closest bus BEFORE target
    //
    // This means:
    //
    // Target 07:00
    //
    // 07:04  ← first
    // 06:47  ← second
    // 07:18  ← third
    //
    // rather than simply sorting everything by distance.
    // -----------------------------------------------------

    const selected = [
      ...after.slice(0, OPTIONS_PER_ROUTE),
      ...before.slice(
        0,
        Math.max(
          0,
          OPTIONS_PER_ROUTE - after.length
        )
      )
    ];


    // If there are already 3 future buses,
    // use the closest previous bus as a backup
    // only if we want the route to show both sides.
    //
    // For now, keep exactly 3 per route.
    let routeOptions =
      selected.slice(
        0,
        OPTIONS_PER_ROUTE
      );


    // If there aren't enough buses after target,
    // fill remaining slots with previous buses.
    if (
      routeOptions.length <
      OPTIONS_PER_ROUTE
    ) {

      for (
        const bus of before
      ) {

        if (
          routeOptions.length >=
          OPTIONS_PER_ROUTE
        ) {
          break;
        }

        if (
          !routeOptions.includes(bus)
        ) {
          routeOptions.push(bus);
        }
      }
    }


    // -----------------------------------------------------
    // Convert into display objects
    // -----------------------------------------------------

    for (
      const bus of routeOptions
    ) {

      const arrival =
        toMin(bus.arr);

      const difference =
        arrival - target;

      results.push({
        ...route,
        ...bus,

        difference,

        distance:
          Math.abs(difference)
      });
    }
  }


  // -------------------------------------------------------
  // Overall ordering
  //
  // Preferred route 27 wins ties.
  // Otherwise closest to target wins.
  // -------------------------------------------------------

  results.sort(
    (a, b) => {

      // Exact target always wins.
      if (
        a.distance !==
        b.distance
      ) {
        return (
          a.distance -
          b.distance
        );
      }

      // Prefer route 27 if equally close.
      if (
        a.preferred !==
        b.preferred
      ) {
        return a.preferred
          ? -1
          : 1;
      }

      // If still tied, earlier departure.
      return (
        toMin(a.dep) -
        toMin(b.dep)
      );
    }
  );


  // -------------------------------------------------------
  // Nothing found
  // -------------------------------------------------------

  if (!results.length) {

    $("results").innerHTML = `
      <div class="card">
        No scheduled buses were found
        for tomorrow.
      </div>
    `;

    return;
  }


  // -------------------------------------------------------
  // Render
  // -------------------------------------------------------

  $("results").innerHTML =
    results
      .map(r => {

        const dep =
          toMin(r.dep);

        const wake =
          dep - WAKE_BEFORE;

        const backup =
          wake -
          BACKUP_BEFORE_WAKE;

        const leave =
          dep -
          HOME_TO_STOP;


        let relation;

        if (
          r.difference === 0
        ) {

          relation =
            "exactly at target";

        } else if (
          r.difference > 0
        ) {

          relation =
            `${r.difference} min after target`;

        } else {

          relation =
            `${Math.abs(
              r.difference
            )} min before target`;
        }


        return `
          <article
            class="result ${
              r.preferred
                ? "best"
                : ""
            }"
          >

            <div class="resultTop">

              <div class="route">
                🚌 ${esc(r.line)}
                → ${esc(r.dest)}
              </div>

              ${
                r.preferred
                  ? '<div class="tag">PREFERRED</div>'
                  : ""
              }

            </div>


            <div class="dest">

              Arrives at
              ${esc(r.dest)}
              at
              <b>${esc(r.arr)}</b>

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
      })
      .join("");
}


// ---------------------------------------------------------
// UI events
// ---------------------------------------------------------

$("findBtn")
  .addEventListener(
    "click",
    find
  );


$("arrival")
  .addEventListener(
    "change",
    find
  );


$("themeBtn")
  .addEventListener(
    "click",
    () => {

      document.documentElement
        .classList
        .toggle("light");

      localStorage.setItem(
        "theme",
        document.documentElement
          .classList
          .contains("light")
          ? "light"
          : "dark"
      );
    }
  );


// ---------------------------------------------------------
// Restore theme
// ---------------------------------------------------------

if (
  localStorage.getItem(
    "theme"
  ) === "light"
) {

  document.documentElement
    .classList
    .add("light");
}


// ---------------------------------------------------------
// Start
// ---------------------------------------------------------

load();
