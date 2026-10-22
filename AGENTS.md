# Agent instructions

## Project

ClamAV Control is a native Omarchy/Quickshell bar plugin. Read `README.md` before changing behavior; `docs/EXPLORATION.md` records the original investigation, not an implementation specification.

- Plugin ID: `io.github.yudopr11.omarchy-clamav-control`.
- Remote: `https://github.com/yudopr11/omarchy-clamav.git`.
- `Panel.qml`: native host UI, status polling, package-install launcher and authenticated actions.
- `manifest.json`: plugin metadata and widget preferences.
- `scripts/omarchy-clamav-control`: installed Python helper; fixed service actions and narrow configuration edits.
- `scripts/install-helper.sh`, `scripts/uninstall-helper.sh`, `polkit/`: explicit privileged-helper lifecycle.
- `bin/`: monitoring, detection collection and interactive ClamAV package installation.
- `systemd/`: optional user detection collector.
- `tests/`: fixtures and unprivileged automated checks.

## Conventions

Use existing Omarchy `qs.Commons`/`qs.Ui` components and existing dependencies. Keep changes small; add regression tests for nontrivial behavior.

Follow the sibling Acer WMI plugin's native UI and narrow authenticated-helper pattern, and the remote-desktop plugin's actual-state polling and bar appearance: plain/non-accented icon, opacity 1.0 when active and 0.45 when inactive/unknown. Do not require sibling repositories to run this project.

Keep widget enablement, current service activity and enable-at-boot state separate. Disabling/removing the widget must not stop protection or delete configuration, databases, logs or quarantine. Unknown/stale status must never imply healthy protection. Detection history and file existence are not a clean-system or remediation verdict.

## Safety boundaries

- Do not install packages, install the helper, modify `/etc`, change live services, or alter desktop configuration during development without explicit user authorization. Never edit packaged Omarchy files under `/usr/share/omarchy/`.
- The panel stays unprivileged. Mutations use `pkexec` with the installed root-owned helper, never user-writable plugin code as an authorized privileged entry point.
- Preserve fixed file/directive/service/action allowlists, input validation, ownership checks, backups, atomic replacement, conflict checks and visible errors. Never add blanket passwordless privileges or arbitrary privileged command execution.
- Preserve unrelated ClamAV directives and the administrator's existing quarantine policy. Starting protection can move files under that policy; retain the warning/confirmation.
- Account for clamd socket activation and dependencies. Starting/stopping and enabling/disabling boot are distinct operations.
- Package installation uses `omarchy pkg add clamav` in a visible terminal. Detect package availability independently of helper availability. Do not automatically enable protection afterward.
- Keep helper installation explicit and checksum-managed. Update documentation when installed-helper changes require reinstallation.
- Retain upstream MIT attribution when changing reused monitor code.

## Mandatory TDD and coverage

For every behavior change or bug fix, follow red → green → refactor:

1. Write or update a focused test first. For bugs, reproduce the failure with a regression test.
2. Run it and confirm it fails for the intended reason before changing production code.
3. Make the smallest implementation change that passes.
4. Refactor only with passing tests, then run the full suite and coverage checks.

Do not implement behavior first and add tests afterward. Documentation-only changes need no new tests. If a live-system or QML behavior cannot be tested safely, state the gap and request guidance rather than claiming TDD compliance.

Measure Python line and branch coverage with `coverage.py` when changing executable Python code:

```sh
uv tool run --from coverage coverage run --branch --source=scripts,bin -m unittest discover -s tests -v
uv tool run --from coverage coverage report -m --fail-under=91
uv tool run --from coverage coverage json -o coverage.json
python3 tests/check_coverage.py coverage.json
```

Actual line and branch coverage must each be strictly greater than 90% for both the measured total and the extensionless helper, and must not regress from the pre-change baseline. The JSON gate checks raw counts separately; the combined/rounded coverage report alone is not sufficient. Use ephemeral coverage tooling via uv; no system package installation is needed. New or changed executable Python lines must be covered; explicitly test security validation, error paths and configuration preservation. Verify the report actually includes the extensionless helper `scripts/omarchy-clamav-control`; an omitted helper or empty report is not a pass. Do not exclude production code or add coverage suppressions merely to meet the threshold.

Python coverage does not measure Bash, QML or the embedded Python in `bin/status.sh`. For changes there, require focused mocked/integration tests or an explicitly documented manual verification plan and coverage gap. Never present Python coverage as whole-plugin coverage. If coverage tooling is unavailable or the baseline fails the gate, report the blocker; do not silently skip it, install tools without authorization, or claim verification passed.

## Verification

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
bash -n bin/*.sh scripts/*.sh
omarchy plugin validate .
```

Tests must use temporary fixtures and mocked commands, not live configuration or service mutations. The optional real `clamconf` fixture check must remain unprivileged. Add tests for validation, failure paths and preservation of unrelated settings when modifying the helper.

Use available QML/LSP checks, but do not treat unresolved host-runtime imports or unsupported diagnostics as proof the UI works. Report whether live rendering, authentication, package installation and service/config mutations were tested; do not exercise those without authorization.

Do not commit or push unless requested.
