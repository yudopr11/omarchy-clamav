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

Review and install the narrow system helper separately, after installing ClamAV:

```sh
cd ~/.config/omarchy/plugins/io.github.yudopr11.omarchy-clamav-control
less scripts/omarchy-clamav-control polkit/io.github.yudopr11.omarchy-clamav-control.policy scripts/install-helper.sh
sudo ./scripts/install-helper.sh
```

This installs only `/usr/local/bin/omarchy-clamav-control` (root-owned, 0755), its polkit action (0644), and `/usr/local/share/omarchy-clamav-control.sha256` (ownership/checksum ledger). It does not alter ClamAV configuration, services, quarantine or databases. Re-running the installer updates only unchanged managed artifacts; modified/unmanaged destinations are refused. Failed installs attempt to restore previous artifacts. Review and re-run it when updating the bundled helper.

For a local checkout, copy only the plugin files, not `.git` or Python caches:

```sh
plugin="$HOME/.config/omarchy/plugins/io.github.yudopr11.omarchy-clamav-control"
mkdir -p "$plugin"
cp -a LICENSE README.md Panel.qml manifest.json bin polkit scripts systemd "$plugin/"
omarchy plugin validate "$plugin"
omarchy plugin enable io.github.yudopr11.omarchy-clamav-control right
```

## Controls and safety

- Running and boot controls are separate: **enable** never implies `--now`. Starting the scanner includes daemon/socket dependencies. Stopping the daemon also stops the scanner and socket, preventing immediate socket reactivation. Disabling daemon boot also disables scanner/socket boot; disabling boot does not stop currently running processes.
- Each service control depends on its relevant known unit states, not unrelated services. A failed multi-unit command may partially succeed: read the error and refreshed actual state.
- **Existing policy is preserved.** Exploration of this machine found `--move=/root/quarantine` in the scanner's service command. The panel displays the current command and asks for confirmation before starting/enabling protection. Starting existing protection can move or remove files according to administrator policy. There are no quarantine, delete, restore or manual-scan actions.
- Include/exclude fields use JSON arrays of existing absolute directories, for example `["/home", "/srv"]`. Includes cannot be empty; control characters, directive injection, duplicates, noncanonical paths and identical include/exclude entries are rejected. Size accepts integer bytes or K/M/G, from 1 byte through 4G; freshclam checks accepts integers 1–50. Existing settings outside these limits remain visible, but cannot be re-applied unchanged without correction.
- Applying saves configuration only. It preserves unrelated directives/comments, validates candidates with `clamconf`, creates a 0600 adjacent `.omarchy-<timestamp>.bak`, and atomically replaces the file while retaining owner/group/mode. Reload discards unsaved field edits. After scanner changes, stop scanner + daemon, then start daemon and scanner. Restart the updater with stop/start after changing checks.
- Revisions prevent applying an old form. The live file is checked again **after** replacement-file fsync, immediately before rename. This is best-effort conflict detection: external writers must coordinate for a strict no-lost-update guarantee; a remaining read/rename race cannot be eliminated without a shared lock protocol. ACLs/xattrs are not copied. Backups are retained for administrator recovery, not automatically pruned or restored.
- The installed helper accepts only fixed service actions and the two narrow configuration edits. Mutations require `pkexec` administrator authentication against the installed root-owned helper, never a writable checkout command or arbitrary shell. Read-only status is unprivileged: unreadable configuration is reported as unavailable, not read with hidden elevation. Unsafe owners, writable config directories/files, symlinks, special files and oversized configuration inputs are refused.
- Unknown/failed/stale status is not displayed as healthy protection. The icon dims when on-access protection is inactive or unknown, and turns urgent for fresh detections whose paths are still visible. Updater health is shown separately; a running scanner does not prove complete scan coverage or a healthy database.

The background-refresh preference is stored in Omarchy widget settings (10–600 seconds, default 60); the open panel refreshes every five seconds. Arrow keys skip disabled/hidden controls and scroll the cursor into view; Enter activates buttons/confirmation, Escape leaves text editing, and Tab follows the host's panel-switching convention. Mouse interaction is also supported.

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

Tests use fixtures/mocks for parsing, restrictions, config preservation, backups, concurrent edits, write failures, missing units, timeouts and the package installer. If `clamconf` exists, an unprivileged fixture-parser integration check also runs. No live system changes are made by these checks. Live QML rendering, polkit dialogs, service changes, package installation and writes to `/etc/clamav` require manual verification on a disposable/test setup; they were not exercised during development. Standalone qmllint cannot fully resolve Omarchy's `qs` runtime imports.

## Attribution

Based on [szentesg/omarchy-clamav-monitor](https://github.com/szentesg/omarchy-clamav-monitor), retaining/adapting its Bash monitor/history collector. MIT; upstream copyright and license are retained in [LICENSE](LICENSE).
