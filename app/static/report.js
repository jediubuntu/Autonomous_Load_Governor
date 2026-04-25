const SERIES = {
  latency: {
    title: "P95 latency (ms)",
    lines: [{ key: "latency", label: "P95 latency", color: "#60a5fa" }],
  },
  users: {
    title: "Users",
    lines: [{ key: "users", label: "Users", color: "#a78bfa" }],
  },
  rps: {
    title: "Requests per second",
    lines: [{ key: "rps", label: "RPS", color: "#22c55e" }],
  },
  cpu: {
    title: "CPU utilization (%)",
    lines: [
      { key: "systemCpu", label: "System CPU", color: "#f59e0b" },
      { key: "processCpu", label: "App process CPU", color: "#f472b6" },
    ],
  },
  errors: {
    title: "Error rate (%)",
    lines: [{ key: "errors", label: "Error rate", color: "#ef4444" }],
  },
};

function formatValue(seriesKey, value) {
  if (seriesKey === "latency") return `${value.toFixed(1)} ms`;
  if (seriesKey === "users") return `${value.toFixed(0)} users`;
  if (seriesKey === "rps") return `${value.toFixed(1)} rps`;
  return `${value.toFixed(2)}%`;
}

function renderAlgChart(data, seriesKey) {
  const config = SERIES[seriesKey];
  const svg = document.getElementById("trendChart");
  const legend = document.getElementById("chartLegend");
  const width = 920;
  const height = 360;
  const pad = { top: 24, right: 24, bottom: 54, left: 56 };
  const plotWidth = width - pad.left - pad.right;
  const plotHeight = height - pad.top - pad.bottom;
  const points = data.length
    ? data
    : [{ interval: 1, latency: 0, users: 0, rps: 0, systemCpu: 0, processCpu: 0, errors: 0 }];
  const xStep = points.length > 1 ? plotWidth / (points.length - 1) : plotWidth / 2;
  const allValues = config.lines.flatMap((line) => points.map((item) => Number(item[line.key] || 0)));
  const maxValue = Math.max(...allValues, 1);
  const niceMax = maxValue <= 10 ? Math.ceil(maxValue + 1) : Math.ceil(maxValue * 1.1);
  const ticks = 5;
  const y = (value) => pad.top + plotHeight - (value / niceMax) * plotHeight;
  const x = (index) => pad.left + (points.length > 1 ? index * xStep : plotWidth / 2);

  let markup = `
    <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="rgba(255,255,255,0.72)"></rect>
    <text x="${pad.left}" y="18" fill="#5f7188" font-size="12" font-family="Inter, Segoe UI, Arial">${config.title}</text>
  `;

  for (let i = 0; i <= ticks; i++) {
    const tickValue = (niceMax / ticks) * i;
    const yPos = y(tickValue);
    markup += `
      <line x1="${pad.left}" y1="${yPos}" x2="${width - pad.right}" y2="${yPos}" stroke="rgba(148,163,184,0.18)" stroke-width="1"></line>
      <text x="${pad.left - 10}" y="${yPos + 4}" text-anchor="end" fill="#6f86a8" font-size="11">${tickValue.toFixed(0)}</text>
    `;
  }

  points.forEach((point, index) => {
    const xPos = x(index);
    markup += `
      <line x1="${xPos}" y1="${pad.top}" x2="${xPos}" y2="${height - pad.bottom}" stroke="rgba(148,163,184,0.10)" stroke-width="1"></line>
      <text x="${xPos}" y="${height - pad.bottom + 24}" text-anchor="middle" fill="#6f86a8" font-size="11">#${point.interval}</text>
    `;
  });

  config.lines.forEach((line) => {
    const polyline = points.map((point, index) => `${x(index)},${y(Number(point[line.key] || 0))}`).join(" ");
    markup += `
      <polyline fill="none" stroke="${line.color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" points="${polyline}"></polyline>
    `;
    points.forEach((point, index) => {
      const value = Number(point[line.key] || 0);
      const cx = x(index);
      const cy = y(value);
      markup += `
        <circle cx="${cx}" cy="${cy}" r="5.5" fill="${line.color}"></circle>
        <title>${line.label} · interval ${point.interval} · ${formatValue(seriesKey, value)}</title>
      `;
    });
  });

  svg.innerHTML = markup;
  legend.innerHTML = config.lines
    .map((line) => `<span><i style="background:${line.color}"></i>${line.label}</span>`)
    .join("");
}

function initAlgReport(data) {
  document.querySelectorAll(".tab-btn").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      renderAlgChart(data, button.dataset.series);
    });
  });

  renderAlgChart(data, "latency");
}
