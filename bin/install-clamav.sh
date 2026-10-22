#!/bin/bash
# Run only in a visible terminal so Omarchy can request authentication.
set -u
omarchy pkg add clamav
result=$?
printf '\nInstaller exit code: %s. Press Enter to close.\n' "$result"
read -r _ || true
exit "$result"
