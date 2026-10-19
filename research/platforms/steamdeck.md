# Steam Deck Control Research

Status: physical SteamOS Devkit administration and panel control are adopted;
native Steam custom-screensaver selection, idle activation, and keyboard
dismissal are live-tested.

## Panel power and idle presentation

**Current — adopted:** the [platform CLI](../../platforms/steamdeck/README.md)
uses the target's Gamescope `drm_sleep_internal_screen` command for internal
panel sleep without suspending SteamOS. A target-local non-grabbing button
watcher restores the panel. The Linux DRM connector's `enabled` state and a
separate SSH round trip distinguish panel disablement from system sleep.

**Current — source-reviewed:** Steam's installed Gaming Mode power UI exposes
separate dim, screensaver, and sleep timers for AC and battery. No general
panel-off-only idle timer was found. Valve's
[display-off downloads](https://store.steampowered.com/news/app/1675200/view/771930569635267984)
complete pending downloads before sleep and do not establish indefinite
reachability. KDE Desktop Mode has its own
[independent screen-off timer](https://docs.kde.org/stable_kf6/en/powerdevil/kcontrol/powerdevil/);
it is not the Gaming Mode idle policy.

**Current — upstream-documented and installed-source-reviewed:** Valve's
[October 13, 2026 release notes](https://www.steamdeck.com/en/news) describe
automatic screensavers, user-created screensaver folders, and an in-game
screensaver toggle. Steam's shipped bouncing-logo HTML/JavaScript confirms
ordinary local web assets. Valve's Steam client is proprietary; the
[Gamescope compositor](https://github.com/ValveSoftware/gamescope) declares
BSD-2-Clause. The owned screensaver is original code; no Valve artwork or
screensaver source is redistributed.

**Current — built and browser-tested:** the owned Quiet Ball implementation
offers black and dim moving-ball modes, size/gray/speed configuration, and a
local preview. Screenshot pixel checks independently verify black output and
the ball's footprint and maximum channel value; geometry checks cover motion,
reflection after large time steps, and resize. A missing or invalid config
fails to black. This does not establish Steam's idle/dismissal behavior or
physical luminance, power savings, or long-term OLED wear.

**Current — live-tested:** the custom folder appeared in Steam's native
Customization selector. Selecting it and using Steam's Preview rendered the
owned dim ball. Two target-local Gamescope compositor captures independently
showed its movement, a black background, and a maximum RGB channel of 26 for
the 10% setting. Steam's UI scaling changes physical pixel diameter relative
to the configured CSS diameter. A temporary one-minute AC idle timer activated
the screensaver without another preview or launch command; SSH remained
available. Target-local Escape dismissed it to the native power settings,
where the one-minute value was independently visible. X11 window capture alone
did not represent the full compositor output reliably, so Gamescope capture
was used.

**Open:** qualify physical controller dismissal, restart-persisted selection,
and behavior across client updates. Keep actual panel-off operation available
independently of this presentation.
