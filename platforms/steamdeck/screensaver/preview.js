const form = document.querySelector("form");
const preview = document.querySelector("iframe");

function update() {
  const values = Object.fromEntries(["mode", "size", "brightness", "speed"].map(key => [key, form.elements[key].value]));
  for (const [key, unit] of [["size", " px"], ["brightness", "%"], ["speed", " px/s"]]) {
    document.getElementById(`${key}-value`).textContent = values[key] + unit;
    form.elements[key].disabled = values.mode === "black";
  }
  preview.src = `index.html?${new URLSearchParams(values)}`;
  document.getElementById("command").textContent = "bin/machine-control --target steamdeck testbed -- screensaver configure" +
    Object.entries(values).map(([key, value]) => ` --${key} ${value}`).join("");
}

form.addEventListener("input", update);
form.addEventListener("submit", event => event.preventDefault());
update();
