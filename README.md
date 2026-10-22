# ClamAV Control for Omarchy

Native Omarchy bar panel: monitor recent detections and database age, control ClamAV's running/boot states, and edit on-access include/exclude directories, maximum file size and freshclam checks per day.

Repository: https://github.com/yudopr11/omarchy-clamav

## Requirements

Omarchy with third-party QML plugins, its existing `qs.Commons`/`qs.Ui` components and terminal launcher; Bash, coreutils, jq, Python 3, systemd and polkit with a working authentication agent. ClamAV supplies `clamconf`. No new third-party libraries are required. The expected system units are `clamav-daemon.service`, `clamav-daemon.socket`, `clamav-clamonacc.service` and `clamav-freshclam.service`.

## Install (explicit steps; nothing auto-enables protection)

```sh
omarchy plugin add https://github.com/yudopr11/omarchy-clamav.git --enable
```

If ClamAV is missing, open the panel and press **Install ClamAV (Omarchy installer)**. This launches `omarchy-launch-terminal bash <plugin-directory>/bin/install-clamav.sh`, which runs `omarchy pkg add clamav` in a visible terminal and preserves its exit status. Package detection uses `omarchy-pkg-present clamav` independently of the control helper, so the button remains usable before helper installation. Detection refreshes every five seconds even if the launcher exits before its terminal. This plugin does not start or enable services as part of package installation; package-manager hooks remain the package's responsibility.

After installing ClamAV, review the bundled helper and installer, then press **Install / update control helper** in the panel. This explicitly launches `omarchy-launch-terminal bash <plugin-directory>/bin/install-helper.sh`; the wrapper resolves its plugin directory and runs `sudo bash <plugin-directory>/scripts/install-helper.sh` using an absolute script path. The visible terminal explains the safety scope, shows success/failure and the exit code, and waits for Enter. The button is available even when helper status is missing or stale and supports the panel's arrow-key/Enter navigation. Status refreshes when the terminal launcher exits and every five seconds while the panel is open (including launchers that return before the terminal closes).

**This setup update changes the installed helper. Use Overview → Install / update control helper before using the new Settings setup action.** Updating plugin files alone does not update the root-owned helper.

Complete first-time setup entirely in the panel:

1. **Overview:** install ClamAV, then install/update the helper using the visible terminal buttons.
2. **Settings:** enter watched directories in Include paths (for example `["/home"]`), review exclusions and size, then **Apply scanner setup / settings (authenticate)**. Apply resolves the single configured daemon `User`, or the platform account `clamav` when absent. If neither existing `OnAccessExcludeUname` nor `OnAccessExcludeUID` covers that daemon, it appends the daemon name to `OnAccessExcludeUname`, preserving all existing exclusions. A root-only exclusion does not cover a non-root daemon. The account must exist, have UID 1–999 and a safe account name; root, login accounts, missing accounts and ambiguous User directives are refused. If User is absent, Apply also sets `User clamav`, rather than assuming clamd drops privileges automatically. Existing user/root exclusions are displayed and retained, with only the missing daemon exclusion appended; they are not a coverage guarantee. No arbitrary user-exclusion editor is exposed.
3. **Settings:** apply updater settings too if its package configuration still contains an active `Example` directive. Explicit authenticated Apply removes that directive from the selected file, validates the candidate and retains a backup; status polling never changes configuration.
4. **Services:** start the updater and allow the initial signature download to complete, then start daemon/scanner after reading and confirming the existing policy warning. If already running, stop scanner + daemon before starting them with changed settings. Enable-at-boot is a separate optional action. Setup/Apply never starts scanning.

Start commands report **request accepted, not healthy**. The panel refreshes actual states and displays bounded systemd `Result` / `ExecMainStatus` diagnostics for scanner, daemon and updater, including immediate exits. These are service diagnostics, not journal contents or a protection verdict. A missing database, permissions, fanotify/kernel limitations or an administrator's incompatible existing policy can still prevent startup. Existing exclusion policies are retained; unsafe or ambiguous daemon identities are refused rather than silently weakened.

Alternatively, review and install manually from the plugin directory; this does not require a working helper:

```sh
cd ~/.config/omarchy/plugins/io.github.yudopr11.omarchy-clamav-control
less scripts/omarchy-clamav-control polkit/io.github.yudopr11.omarchy-clamav-control.policy scripts/install-helper.sh
sudo bash scripts/install-helper.sh
```

This installs only `/usr/local/bin/omarchy-clamav-control` (root-owned, 0755), its polkit action (0644), and `/usr/local/share/omarchy-clamav-control.sha256` (ownership/checksum ledger). It does not alter ClamAV configuration, services, quarantine or databases. Re-running the installer updates only unchanged managed artifacts; modified/unmanaged destinations are refused. Failed installs attempt to restore previous artifacts. Review and re-run it (or use the panel button) when updating the bundled helper.

For a local checkout, copy only the plugin files, not `.git` or Python caches:

```sh
plugin="$HOME/.config/omarchy/plugins/io.github.yudopr11.omarchy-clamav-control"
mkdir -p "$plugin"
cp -a LICENSE README.md Panel.qml manifest.json bin polkit scripts systemd "$plugin/"
omarchy plugin validate "$plugin"
omarchy plugin enable io.github.yudopr11.omarchy-clamav-control right
```

## Controls and safety

The panel has three pages: **Overview** for status, package/helper setup and recent history; **Services** for running/boot controls and the existing-policy warning; **Settings** for scanner/updater fields and reload. Click a tab or use Left/Right outside text editing to switch pages; switching cancels any pending policy confirmation, resets scrolling and returns keyboard focus to the panel. Unsaved field edits are retained across pages. Helper installation remains available on Overview even with missing/stale status.

- Running and boot controls are separate: **enable** never implies `--now`. Starting the scanner includes daemon/socket dependencies. Stopping the daemon also stops the scanner and socket, preventing immediate socket reactivation. Disabling daemon boot also disables scanner/socket boot; disabling boot does not stop currently running processes.
- Each service control depends on its relevant known unit states, not unrelated services. A failed multi-unit command may partially succeed: read the error and refreshed actual state.
- **Existing policy is preserved.** Exploration of this machine found `--move=/root/quarantine` in the scanner's service command. The panel displays the current command and asks for confirmation before starting/enabling protection. Starting existing protection can move or remove files according to administrator policy. There are no quarantine, delete, restore or manual-scan actions.
- Include/exclude fields use JSON arrays of existing absolute directories, for example `["/home", "/srv"]`. Includes cannot be empty; control characters, directive injection, duplicates, noncanonical paths and identical include/exclude entries are rejected. Size accepts integer bytes or K/M/G, from 1 byte through 4G; freshclam checks accepts integers 1–50. Existing settings outside these limits remain visible, but cannot be re-applied unchanged without correction.
- Applying saves configuration only. It preserves unrelated directives/comments, validates candidates with `clamconf`, creates a 0600 adjacent `.omarchy-<timestamp>.bak`, and atomically replaces the file while retaining owner/group/mode. Reload discards unsaved field edits. After scanner changes, stop scanner + daemon, then start daemon and scanner. Restart the updater with stop/start after changing checks.
- Revisions prevent applying an old form. The live file is checked again **after** replacement-file fsync, immediately before rename. This is best-effort conflict detection: external writers must coordinate for a strict no-lost-update guarantee; a remaining read/rename race cannot be eliminated without a shared lock protocol. ACLs/xattrs are not copied. Backups are retained for administrator recovery, not automatically pruned or restored.
- The installed helper accepts only fixed service actions and the two narrow configuration edits. Mutations require `pkexec` administrator authentication against the installed root-owned helper, never a writable checkout command or arbitrary shell. Read-only status is unprivileged: unreadable configuration is reported as unavailable, not read with hidden elevation. Unsafe owners, writable config directories/files, symlinks, special files and oversized configuration inputs are refused.
- Unknown/failed/stale status is not displayed as healthy protection. The icon dims when on-access protection is inactive or unknown, and turns urgent for fresh detections whose paths are still visible. Updater health is shown separately; a running scanner does not prove complete scan coverage or a healthy database.

The background-refresh preference is stored in Omarchy widget settings (10–600 seconds, default 60); the open panel refreshes every five seconds. Up/Down skip disabled/hidden controls on the active page and scroll the cursor into view; Enter activates buttons/confirmation, Escape leaves text editing, and Tab follows the host's panel-switching convention. Mouse interaction is also supported.

## Monitor and optional history collector

The monitor retains upstream's last-ten-detection history at `~/.local/state/omarchy/clamav-detections.log` and checks both `/var/lib/clamav/daily.cld` and `daily.cvd`. Database modification time is **not** proof that freshclam completed successfully. An absent/inaccessible detection path may have been moved, removed or simply be inaccessible to this user; it is not a quarantine verdict. Oversized/malformed records are ignored; history parsing reads a bounded 64 KiB tail window before selecting records. Total count is a streaming line count, not a malware inventory.

If the existing history collector is already running, keep it; do not run two collectors for the same log. Otherwise, the optional user unit below records **new** `FOUND` lines from `/var/log/clamav/clamonacc.log`. It requires that log to be readable by the user; ask the administrator for narrowly scoped access rather than weakening system-wide log permissions. It does not backfill old detections or configure ClamAV logging:

```sh
cd ~/.config/omarchy/plugins/io.github.yudopr11.omarchy-clamav-control
mkdir -p ~/.config/systemd/user
install -m644 systemd/omarchy-clamav-control-detections.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now omarchy-clamav-control-detections.service
```

The unit uses the canonical installed plugin path. Its user-owned history log has no automatic retention policy; arrange rotation if needed. Missing/unreadable history is explicitly reported. The panel offers opening the log in Omarchy's editor.

## Disable / uninstall

Disabling or removing the widget **does not stop protection**, disable boot, remove packages, change config or delete quarantine/history. Stop/disable the relevant services explicitly in the panel first if that is your intention.

```sh
omarchy plugin disable io.github.yudopr11.omarchy-clamav-control
# Run from the plugin directory BEFORE removing it:
sudo ./scripts/uninstall-helper.sh
# Only if you installed this optional collector:
systemctl --user disable --now omarchy-clamav-control-detections.service
rm ~/.config/systemd/user/omarchy-clamav-control-detections.service
systemctl --user daemon-reload
omarchy plugin remove io.github.yudopr11.omarchy-clamav-control
```

The helper uninstaller checks its ledger and refuses modified/unmanaged artifacts; it removes only the helper, polkit policy and ledger. Config, backups, databases, existing quarantine policy, history and the ClamAV package remain untouched.

## Conventions followed

- `omarchy-acer-wmi-ext`: schemaVersion 1 bar-widget manifest; native `Panel`, `BarIconButton`, `KeyboardPanel`, `PanelKeyCatcher`, `Button`, `TextField` and host typography/colors; explicit root-owned helper/polkit installation; authenticated narrow actions, not arbitrary privileged commands.
- `omarchy-remote-dekstop-server`: plain/non-accented bar appearance (`active: false`, `useActiveColor: false`), opacity 1.0 for active vs 0.45 for inactive; separate unknown/setup-required state; periodic status rather than optimistic toggles; interactive terminal package installation; checksum ownership tracking and non-destructive uninstall. ClamAV deliberately retains the existing system protection when its UI is disabled/removed rather than adopting RDP's session-server teardown.
- Like both repositories, widget enablement is Omarchy-managed and is distinct from the controlled service's running/boot state. No install or uninstall hook executes when the widget loads/unloads.

## Checks / limitations

```sh
python3 -m unittest discover -s tests -v
bash -n bin/*.sh scripts/*.sh
omarchy plugin validate .
```

Reproduce the Python coverage gate (ephemeral tooling via uv, no system package installation):

```sh
uv tool run --from coverage coverage run --branch --source=scripts,bin -m unittest discover -s tests -v
uv tool run --from coverage coverage report -m --fail-under=91
uv tool run --from coverage coverage json -o coverage.json
python3 tests/check_coverage.py coverage.json
```

The JSON gate requires actual line **and** branch coverage each strictly greater than 90%, for both the total and `scripts/omarchy-clamav-control`; missing helper/empty measurements fail. The combined report alone cannot enforce both thresholds. Coverage measures the extensionless Python helper, not Bash, QML or the embedded Python in `bin/status.sh`; this is not whole-plugin coverage.

Tests use fixtures/mocks for parsing, restrictions, config preservation, backups, concurrent edits, write failures, missing units, timeouts and the package/helper terminal installers. If `clamconf` exists, an unprivileged fixture-parser integration check also runs. No live system changes are made by these checks. Live QML rendering, polkit dialogs, service changes, package installation and writes to `/etc/clamav` require manual verification on a disposable/test setup; they were not exercised during development. Standalone qmllint cannot fully resolve Omarchy's `qs` runtime imports.

Manual first-time setup verification (not performed; requires an authorized disposable system): use package defaults with no watch paths or user exclusions, install/update the helper via Overview, verify Settings previews the daemon exclusion, choose a temporary watched directory and authenticate Apply. Confirm the backup, preserved policy and no automatic starts. Start updater, allow databases to download, then explicitly start daemon/scanner after policy confirmation. Exercise authentication cancellation, an immediate scanner exit, missing databases, existing UID/Uname/root exclusions and invalid daemon identities; verify errors/actual failure states remain visible. Static UI tests cover wiring only, not live rendering or authentication.

Manual tab verification (static wiring tests do not exercise QML): check mouse and Left/Right page changes, Up/Down/Enter on each page, empty/disabled control lists, text-field Escape and host Tab switching. Scroll each page, then change pages and confirm scroll/focus reset. Start a policy confirmation, switch pages by mouse and verify it is cancelled; return to Services and confirm a fresh prompt is required. Check stale status still blocks mutations and helper setup remains usable on Overview. These rendering/focus checks remain unperformed.

Manual UI verification (not covered by Python tests): on an authorized disposable setup with a missing helper, open the panel, arrow to **Install / update control helper**, press Enter, and confirm the visible terminal explains the sudo installation. Check both authentication cancellation/failure and success, then press Enter to close. Verify errors remain visible in the terminal, the button remains usable with stale status, and successful setup recovers status within the open panel's polling interval without starting services or editing ClamAV configuration. Also check recovery if the terminal launcher returns before its window closes. This live rendering/authentication check remains unperformed; use a disposable setup before relying on the UI flow.

## Attribution

Based on [szentesg/omarchy-clamav-monitor](https://github.com/szentesg/omarchy-clamav-monitor), retaining/adapting its Bash monitor/history collector. MIT; upstream copyright and license are retained in [LICENSE](LICENSE).
