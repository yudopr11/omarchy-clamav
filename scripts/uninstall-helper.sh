#!/usr/bin/env bash
set -euo pipefail
[[ $EUID == 0 ]] || { printf 'Run sudo ./scripts/uninstall-helper.sh\n' >&2; exit 1; }
[[ $# == 0 ]] || exit 1
ledger=/usr/local/share/omarchy-clamav-control.sha256
targets=(/usr/local/bin/omarchy-clamav-control /usr/share/polkit-1/actions/io.github.yudopr11.omarchy-clamav-control.policy)
[[ -f $ledger && ! -L $ledger && $(stat -c %u "$ledger") == 0 && $(stat -c %a "$ledger") == 644 ]] || { echo 'Missing/unsafe ledger; nothing removed' >&2; exit 1; }
for target in "${targets[@]}"; do
  expected="$(awk -v target="$target" '$2 == target {print $1}' "$ledger")"
  [[ $expected =~ ^[a-f0-9]{64}$ && -f $target && ! -L $target && $(sha256sum "$target" | cut -d' ' -f1) == "$expected" ]] || { printf 'Modified/unmanaged target: %s; nothing removed\n' "$target" >&2; exit 1; }
done
rm -- "${targets[@]}" "$ledger"
printf 'Removed helper and policy only. Services, configs, backups, databases and quarantine were left untouched.\n'
