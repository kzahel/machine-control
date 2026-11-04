"""Native desktop operation inventory; shared Node owns authorization."""
OBSERVE = {"applications", "windows", "snapshot", "capture"}
CONTROL = {"action", "focus", "set_value", "application.launch", "application.activate",
           "application.terminate", "input.move", "input.click", "input.key", "input.text",
           "input.scroll", "input.drag"}
