/* Local descriptive filtering of a pinned aggregate snapshot; no ranking. */
(() => {
  "use strict";
  const form = document.getElementById("benchmark-filters");
  const status = document.getElementById("benchmark-filter-status");
  const query = document.getElementById("benchmark-query");
  const agent = document.getElementById("benchmark-agent");
  const success = document.getElementById("benchmark-success");
  const cost = document.getElementById("benchmark-cost");
  const share = document.getElementById("benchmark-share");
  const table = document.getElementById("external-results");
  const rows = Array.from(table.tBodies[0].rows);
  const fields = {q: query, agent, min: success, max: cost};

  // Decimal comparisons use integral 10^-8 dollars. No binary floating-point
  // rounding or comparison of the two-decimal presentation column.
  function dollars(value) {
    if (typeof value !== "string" || !/^(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,8})?$/.test(value)) return null;
    const [whole, fraction = ""] = value.split(".");
    const units = BigInt(whole) * 100000000n + BigInt(fraction.padEnd(8, "0"));
    return units <= 100000000000000000n ? units : null;
  }

  function settings() {
    if (!form.checkValidity()) return null;
    const minimum = success.value === "" ? 0 : Number(success.value);
    const maximum = cost.value === "" ? null : dollars(cost.value);
    if (!Number.isInteger(minimum) || minimum < 0 || minimum > 100 ||
        (cost.value !== "" && maximum === null)) return null;
    return {query: query.value.trim().toLowerCase(), agent: agent.value, minimum, maximum};
  }

  async function initialize() {
    const response = await fetch("data/terminal-bench-4-1.json", {credentials: "omit"});
    if (!response.ok) throw Error("snapshot unavailable");
    const snapshot = await response.json();
    if (snapshot.schema_version !== 1 ||
        snapshot.source_commit !== "ad4c7aae7b6f1fd80e514dc85768e46d02661bef" ||
        snapshot.eligible_for_ranking !== false || !Array.isArray(snapshot.rows) ||
        snapshot.rows.length !== rows.length) throw Error("unexpected snapshot identity");
    const byPath = new Map(snapshot.rows.map(row => [row.source_path, row]));
    if (byPath.size !== rows.length || rows.some(row => !byPath.has(row.dataset.sourcePath))) {
      throw Error("table and snapshot differ");
    }
    const data = rows.map(element => {
      const item = byPath.get(element.dataset.sourcePath);
      const n = item.n_trials, accepted = item.reported_successes;
      if (!Number.isSafeInteger(n) || n <= 0 || !Number.isSafeInteger(accepted) ||
          accepted < 0 || accepted > n) throw Error("invalid aggregate count");
      const amount = dollars(item.reported_inference_cost_usd);
      const ratioAvailable = item.reported_inference_cost_per_success_usd !== null &&
        item.state === "reported_aggregate_only" && amount !== null && amount > 0n && accepted > 0;
      return {element, n, accepted, amount, ratioAvailable,
        agent: item.agent || "", route: (item.model || "Route not declared").toLowerCase()};
    });
    for (const name of [...new Set(data.map(row => row.agent).filter(Boolean))].sort()) {
      agent.add(new Option(name, name));
    }

    function apply() {
      const current = settings();
      if (current === null) {
        status.textContent = "Enter a whole percentage from 0 to 100 and a nonnegative dollar limit with at most two decimal places. Filters not applied.";
        rows.forEach(row => {row.hidden = false;});
        share.disabled = true;
        return;
      }
      let count = 0;
      for (const row of data) {
        const matches = (!current.query || row.route.includes(current.query)) &&
          (!current.agent || row.agent === current.agent) &&
          BigInt(row.accepted) * 100n >= BigInt(current.minimum) * BigInt(row.n) &&
          (current.maximum === null || (row.ratioAvailable &&
            row.amount <= current.maximum * BigInt(row.accepted)));
        row.element.hidden = !matches;
        count += Number(matches);
      }
      status.textContent = count + " of " + rows.length + " records shown. " +
        "Original order retained; cost coverage and paired task support remain unverified." +
        (current.maximum === null ? "" : " Undefined or unavailable ratios excluded by the cost limit.");
      share.disabled = false;
    }

    const params = new URL(window.location.href).searchParams;
    for (const [key, input] of Object.entries(fields)) {
      if (params.has(key)) input.value = params.get(key).slice(0, 100);
    }
    // Invalid or unknown share-link parameters fall back to the full table.
    if (settings() === null) form.reset();
    form.hidden = false;
    status.hidden = false;
    form.addEventListener("submit", event => event.preventDefault());
    form.addEventListener("input", apply);
    form.addEventListener("change", apply);
    form.addEventListener("reset", () => queueMicrotask(apply));
    share.addEventListener("click", async () => {
      if (!settings()) return;
      const url = new URL(window.location.href);
      for (const [key, input] of Object.entries(fields)) {
        url.searchParams.delete(key);
        if (input.value && !(key === "min" && input.value === "0")) {
          url.searchParams.set(key, input.value);
        }
      }
      // The address bar is a copyable fallback even on insecure local origins
      // or when clipboard permission is denied.
      window.history.replaceState(null, "", url);
      try {
        await navigator.clipboard.writeText(url.href);
        status.textContent = "Filtered link copied. No ranking or cost-completeness claim.";
      } catch {
        status.textContent = "Filtered link is in your address bar. Copy it to share.";
      }
    });
    apply();
  }

  initialize().catch(() => {
    rows.forEach(row => {row.hidden = false;});
    form.hidden = true;
    status.hidden = false;
    status.textContent = "Filters unavailable. All original pinned records are displayed below.";
  });
})();
