// Steam owns idle detection and dismisses the screensaver on input.
// This page draws only black and, optionally, one moving gray circle.
const ball = document.getElementById("ball");
let config;
let frame;
let started;
let lastFrame = -Infinity;
let size;
const phase = [Math.random(), Math.random()];

function validate(value) {
  if (!value || !["ball", "black"].includes(value.mode)) throw Error("Invalid mode");
  for (const [key, min, max] of [["size", 1, 512], ["brightness", 0, 100], ["speed", 1, 200]]) {
    if (typeof value[key] !== "number" || !Number.isFinite(value[key]) || value[key] < min || value[key] > max) {
      throw Error(`Invalid ${key}`);
    }
  }
  return value;
}

// A triangle wave reflects at the edges, even after a long frame or resize.
function position(distance, extent) {
  if (extent <= 0) return 0;
  const step = distance % (extent * 2);
  return step <= extent ? step : extent * 2 - step;
}

function resize() {
  size = Math.min(config.size, innerWidth / 2, innerHeight / 2);
  ball.style.width = `${size}px`;
  ball.style.height = `${size}px`;
}

function draw(now) {
  frame = undefined;
  if (document.hidden) return;
  frame = requestAnimationFrame(draw);
  if (now - lastFrame < 1000 / 30) return;
  lastFrame = now;
  started ??= now;
  const seconds = (now - started) / 1000;
  const width = Math.max(0, innerWidth - size);
  const height = Math.max(0, innerHeight - size);
  const x = position(phase[0] * width * 2 + seconds * config.speed, width);
  const y = position(phase[1] * height * 2 + seconds * config.speed * Math.SQRT1_2, height);
  ball.style.transform = `translate3d(${x}px, ${y}px, 0)`;
}

async function init() {
  try {
    const response = await fetch("config.json", { cache: "no-store" });
    if (!response.ok) throw Error("Missing config");
    const value = await response.json();
    // Query parameters are for the standalone preview; saved settings live in config.json.
    for (const [key, raw] of new URLSearchParams(location.search)) {
      if (["mode", "size", "brightness", "speed"].includes(key)) value[key] = key === "mode" ? raw : Number(raw);
    }
    config = validate(value);
    if (config.mode === "black" || config.brightness === 0) return;
    const gray = Math.round(255 * config.brightness / 100);
    ball.style.backgroundColor = `rgb(${gray}, ${gray}, ${gray})`;
    resize();
    addEventListener("resize", resize);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        cancelAnimationFrame(frame);
        frame = undefined;
      } else if (frame === undefined) {
        lastFrame = -Infinity;
        frame = requestAnimationFrame(draw);
      }
    });
    // Position before revealing the circle to avoid a stationary flash at the origin.
    draw(performance.now());
    ball.hidden = false;
  } catch {
    // Missing or malformed configuration fails to an entirely black page.
    ball.hidden = true;
  }
}

init();
