#!/usr/bin/env bash
# Explicit system installation only; never called by the panel.
set -euo pipefail
[[ $EUID == 0 ]] || { printf 'Review this script, then run sudo ./scripts/install-helper.sh\n' >&2; exit 1; }
[[ $# == 0 ]] || exit 1
repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
helper=/usr/local/bin/omarchy-clamav-control
policy=/usr/share/polkit-1/actions/io.github.yudopr11.omarchy-clamav-control.policy
ledger=/usr/local/share/omarchy-clamav-control.sha256
sources=("$repo/scripts/omarchy-clamav-control" "$repo/polkit/io.github.yudopr11.omarchy-clamav-control.policy")
targets=("$helper" "$policy")
for command in /usr/bin/python3 /usr/bin/pkexec /usr/bin/clamconf /usr/bin/systemctl; do
  [[ -x $command ]] || { printf 'Missing prerequisite: %s\n' "$command" >&2; exit 1; }
done
if [[ -e $ledger || -L $ledger ]]; then
  [[ -f $ledger && ! -L $ledger && $(stat -c %u "$ledger") == 0 && $(stat -c %a "$ledger") == 644 ]] || { echo 'Unsafe ownership ledger' >&2; exit 1; }
  # Never interpret ledger paths as commands or arbitrary removal targets.
  for target in "${targets[@]}"; do
    expected="$(awk -v target="$target" '$2 == target {print $1}' "$ledger")"
    [[ $expected =~ ^[a-f0-9]{64}$ && -f $target && ! -L $target && $(sha256sum "$target" | cut -d' ' -f1) == "$expected" ]] || { printf 'Modified/unmanaged target: %s\n' "$target" >&2; exit 1; }
  done
else
  for target in "${targets[@]}"; do
    [[ ! -e $target && ! -L $target ]] || { printf 'Refusing unmanaged target: %s\n' "$target" >&2; exit 1; }
  done
fi
install -d -o root -g root -m755 /usr/local/share
stage="$(mktemp -d /usr/local/share/.omarchy-clamav-control.XXXXXX)"
committing=false
committed=false
cleanup() {
  result=$?
  if [[ $committing == true && $committed == false ]]; then
    for i in 0 1; do
      if [[ -f $stage/old-$i ]]; then cp -p -- "$stage/old-$i" "${targets[$i]}"; else rm -f -- "${targets[$i]}"; fi
    done
    if [[ -f $stage/old-ledger ]]; then cp -p -- "$stage/old-ledger" "$ledger"; else rm -f -- "$ledger"; fi
    echo 'Installation failed; restored previous artifacts.' >&2
  fi
  rm -rf -- "$stage"
  return "$result"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
for i in 0 1; do
  mode=644
  [[ $i == 0 ]] && mode=755
  install -o root -g root -m "$mode" "${sources[$i]}" "$stage/new-$i"
  [[ ! -f ${targets[$i]} ]] || cp -p -- "${targets[$i]}" "$stage/old-$i"
done
[[ ! -f $ledger ]] || cp -p -- "$ledger" "$stage/old-ledger"
for i in 0 1; do
  printf '%s  %s\n' "$(sha256sum "$stage/new-$i" | cut -d' ' -f1)" "${targets[$i]}"
done > "$stage/ledger"
chmod 644 "$stage/ledger"
committing=true
for i in 0 1; do
  install -D -o root -g root -m "$(stat -c %a "$stage/new-$i")" "$stage/new-$i" "${targets[$i]}"
done
mv -f -- "$stage/ledger" "$ledger"
committed=true
printf 'Installed helper and authentication policy. No services or ClamAV config changed.\n'
