# Mac production updates

Topic: native-distribution
Status: in progress

## Objective

Release 0.3.4 with compact menu-bar Settings and Check for Updates commands,
deploy the existing update endpoint, and prove an installed signed 0.3.3 app
updates through that production route.

## Completion conditions

- Production route returns the shared server's platform-specific signed
  metadata, and 204 for current clients.
- Both Mac packages pass signed CI verification; ARM64 Tart passes native
  operator, tray navigation, Stop, and Quit acceptance before publication.
- Tagged CI publishes the complete immutable 0.3.4 release with required notes.
- Public 0.3.3 discovers, installs, and relaunches public 0.3.4 in Tart;
  permissions remain ready, access stays off, and resident generation changes.
- Original testbed application, policy, power state, and claim are restored.

## Boundaries

The shared update server owns release selection and Tauri metadata. The website
proxies the stable product endpoint without duplicating that protocol. Public
product configuration belongs here; concrete deployment belongs in private
infrastructure. No automatic installation, permission bypass, new providers,
or Windows/Linux desktop packaging is included. Intel package authenticity is
required; Intel execution and physical-host acceptance remain separate.

## Ordered work

### 1 — expose update checks and tray navigation

Register the desktop release family on the shared server, proxy only supported
Mac update paths, and expose compact Settings and Check for Updates menu items.
Keep native update lifecycle enforcement and explicit installation.

### 2 — accept the signed candidate

Run source, proxy, release, and native checks. Build both signed architectures
in CI. Authenticate exact packages, then exercise ARM64 in claimed Tart using
the resident observer and an independent fixture.

### 3 — publish and exercise the production update

Create the annotated version tag through the release script. Require successful
automatic draft verification/publication. Re-download public packages and
verify the feed and website. Install public 0.3.3, check and install through its
visible UI, and verify 0.3.4 relaunch and retained permissions. Restore the VM.

## Validation and result

Pending exact signed candidate and public-update acceptance.
