# Windows pointer input

The desktop resident implements `move`, `drag` and `scroll` through target-local
Win32 `SendInput`. They require approved control scope and a live retained
owner. The common CLI translates `input.move`, `input.drag` and `input.scroll`
to these native operations for Windows.

```sh
bin/machine-control --target windows --claim CLAIM desktop input move 600 300
bin/machine-control --target windows --claim CLAIM desktop input drag 600 300 800 400
bin/machine-control --target windows --claim CLAIM desktop input scroll 0 -120
```

Use a retained control stream or SDK owner for several related operations.
Raw owner requests can select a left or right drag button and `durationMs`:

```json
{"operation":"drag","x":600,"y":300,"x2":800,"y2":400,"button":"left","durationMs":500}
```

Coordinates are physical pixels in the Windows virtual screen, including
negative display origins. Endpoints and sampled drag steps must lie on active
displays. A drag follows a straight line, defaults to 300 ms and accepts
durations from 50 to 5000 ms. Slow authority checks skip elapsed intermediate
steps instead of extending the hold by a full sequence of late checks; native
discovery and dispatch still add latency. Display changes interrupt the path.
A button already held before the drag is refused.
The resident serializes its pointer operations and checks authority and operator
control geometry before each drag step. Crossing protected operator controls
is refused even when both endpoints are outside them.

Scrolling uses the current guest pointer and ordinary Windows input routing.
`deltaX` and `deltaY` are signed Windows wheel units, each bounded to
`-12000..12000`; at least one must be nonzero. One detent is 120 units. Positive
X means right and positive Y means up. Results explicitly report these units;
they are not a portable pixel distance. The macOS implementation currently
uses CoreGraphics pixel scroll events. Application settings and native message
handling determine the resulting content movement.

Pause, Stop, owner loss and cancellation interrupt a drag without replay. After
an attempted press, private cleanup sends only the matching release, without
another pointer movement. Cleanup refuses a changed console/input desktop
rather than targeting the new login/session; such a result has unknown delivery
and requires observation before retry. Pointer request cancellation waits for
cleanup before completing. No arbitrary button-hold API is exposed.

The optional UAC helper includes these operations for elevated apps on the
unlocked Default desktop. Generic pointer input during secure UAC consent
remains refused; approval and cancellation use `uac.respond`.

A successful result confirms API delivery, not application effect. Use a
semantic readback, independent fixture state or capture as the postcondition.
Focused x64 VM evidence and remaining gates live in
[Tactical 104](../docs/tactical/104-windows-pointer-gestures.md).

Native behavior is defined by Microsoft's
[MOUSEINPUT](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput)
and [SendInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput)
documentation.
