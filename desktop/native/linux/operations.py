"""Native desktop operation inventory; shared Node owns authorization."""
OBSERVE = {"applications", "windows", "snapshot", "capture"}
CONTROL = {"action", "focus", "set_value", "application.launch", "application.activate",
           "application.terminate", "input.move", "input.click", "input.key", "input.text",
           "input.scroll", "input.drag"}
BROWSER = {"browser.tabs", "browser.snapshot", "browser.click", "browser.type", "browser.key",
           "browser.navigate", "browser.wait", "browser.capture", "browser.release",
           "browser.cdp", "browser.eval", "browser.endpoint"}
# Operations an owner may name in `control.open` for each requested surface.
SURFACE_OPERATIONS = {"desktop": OBSERVE | CONTROL, "browser": BROWSER}
