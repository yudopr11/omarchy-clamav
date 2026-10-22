# Omarchy ClamAV Control — exploration

## Base

Extend https://github.com/szentesg/omarchy-clamav-monitor (examined commit `cd26cd4`, MIT). Preserve its copyright/license when reusing source. Workspace was empty at exploration time.

Upstream consists of `Panel.qml`, `manifest.json`, `bin/status.sh`, `bin/watch-detections.sh`, an on-access config example and a user detection-log service. QML launches the Bash status reader and parses JSON. Refresh interval is the only exposed setting. The panel uses Omarchy's shared UI components. The existing plugin is explicitly display-only.

Use a distinct plugin ID for the control version; update manifest, QML module/IPC IDs, hardcoded script paths and detection-service paths together. Keep the original monitor usable independently, but recommend showing only one widget.

## Proposed first version

Retain status and detection history. Add:

- Separate start/stop and enable-at-boot controls for scanner and updater, reflecting actual system state after completion.
- Editable on-access include/exclude directories and maximum scan file size in clamd.conf.
- Editable update check frequency in freshclam.conf.
- Explicit Apply with authentication, visible errors, backup and config validation. Explain when scanner restart is required.

Keep widget preferences in Omarchy settings, but read actual ClamAV configuration for antivirus settings. Do not create a second authoritative copy of ClamAV settings in shell.json.

## Privilege and safety boundary

The QML UI stays unprivileged. Privileged configuration changes require a small root-owned helper installed explicitly by the user and invoked through pkexec from the GUI. Never create a passwordless arbitrary-shell policy or execute editable plugin code as a privileged helper with broad authorization.

Helper must allowlist files, directives, service units and actions; validate values and paths; avoid shell interpolation; preserve unrelated directives; handle repeated path directives correctly; serialize edits; make backups and atomic writes; and report validation/restart failures. Test using temporary files and mocked commands, not live /etc files.

On-access monitoring requires clamd. Freshclam's background updater can conflict with a manual freshclam run; defer Update now until coordinating them is implemented. Do not add delete/quarantine/restore actions in the first version.

## Local read-only findings

- ClamAV 1.5.4-1 and Quickshell 0.3.2.r7.g2b4501a-1 installed.
- clamav-daemon.service, clamav-clamonacc.service and clamav-freshclam.service inactive and disabled at inspection.
- Omarchy supports native QML bar plugins and manifest validation. Plugins run unsandboxed inside the shell.
- pkexec and clamconf available; qmllint not found on PATH.
- Local clamonacc unit already has `--move=/root/quarantine`. Starting it can therefore move detected files: show this behavior before enabling protection. Do not replace this policy silently.
- clamd unit also enables a socket and requires signature databases. Stopping the daemon alone is not a complete disable-protection operation; account for socket activation.
- Upstream status checks presence only for its last ten logged detections. Do not describe that as proof the whole machine is clean.
- Upstream database age uses daily.cvd/daily.cld modification times, not successful-update history.

## Verification before release

Validate manifest using `omarchy plugin validate <folder>`. Exercise config parsing/validation/backup/failure paths with fixtures, service actions with mocks, and the panel on a real Quickshell session. Test canceled authentication and missing databases. Keep installation separate from development: no live configuration or service changes during exploration.
