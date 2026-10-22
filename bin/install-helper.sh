#!/bin/bash
# Run only in a visible terminal for explicit administrator authentication.
set -u
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1
printf 'Install / update the root-owned ClamAV control helper, polkit policy and checksum ledger using sudo.\nNo services or ClamAV configuration will be changed.\n'
sudo bash "$repo/scripts/install-helper.sh"
result=$?
if [[ $result == 0 ]]; then
  printf '\nControl helper installation completed.\n'
else
  printf '\nControl helper installation failed; review the errors above.\n'
fi
printf 'Helper installer exit code: %s. Press Enter to close.\n' "$result"
read -r _ || true
exit "$result"
