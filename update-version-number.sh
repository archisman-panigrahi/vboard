#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 \"version.number\" \"changelog message\"" >&2
  exit 1
fi

version="$1"
message="$2"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
debian_changelog="${script_dir}/debian/changelog"
aur_pkgbuild="${script_dir}/AUR/PKGBUILD"
python_constants="${script_dir}/vboard/constants.py"

if [[ ! -f "${debian_changelog}" ]]; then
  echo "Error: ${debian_changelog} not found" >&2
  exit 1
fi

if [[ ! -f "${aur_pkgbuild}" ]]; then
  echo "Error: ${aur_pkgbuild} not found" >&2
  exit 1
fi

if [[ ! -f "${python_constants}" ]]; then
  echo "Error: ${python_constants} not found" >&2
  exit 1
fi

debian_version="${version}"
if [[ "${debian_version}" != *-* ]]; then
  debian_version="${debian_version}-1"
fi

maintainer_signature="$(sed -n 's/^\s*\(-- .*>\)\s\{2,\}.*$/\1/p' "${debian_changelog}" | head -n 1)"
if [[ -z "${maintainer_signature}" ]]; then
  echo "Error: could not determine maintainer signature from ${debian_changelog}" >&2
  exit 1
fi

tmp_changelog="$(mktemp)"
tmp_pkgbuild="$(mktemp)"
tmp_constants="$(mktemp)"
trap 'rm -f "${tmp_changelog}" "${tmp_pkgbuild}" "${tmp_constants}"' EXIT

{
  printf 'vboard (%s) unstable; urgency=medium\n\n' "${debian_version}"
  printf '  * %s\n\n' "${message}"
  printf ' %s  %s\n\n' "${maintainer_signature}" "$(date -R)"
  cat "${debian_changelog}"
} > "${tmp_changelog}"

mv "${tmp_changelog}" "${debian_changelog}"

sed "0,/^pkgver=.*/s//pkgver=${version}/" "${aur_pkgbuild}" > "${tmp_pkgbuild}"
mv "${tmp_pkgbuild}" "${aur_pkgbuild}"

sed "0,/^VERSION = \".*\"/s//VERSION = \"${version}\"/" "${python_constants}" > "${tmp_constants}"
mv "${tmp_constants}" "${python_constants}"

echo "Updated ${debian_changelog} to ${debian_version}"
echo "Updated ${aur_pkgbuild} to ${version}"
echo "Updated ${python_constants} to ${version}"
