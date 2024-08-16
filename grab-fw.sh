#!/bin/bash

set -euo pipefail

firmware_release=${1?}

filename=ayab-${firmware_release}.hex
filepath="src/main/resources/base/ayab/firmware/${filename}"

curl -Lo "$filepath"  "https://github.com/jonathanperret/ayab-firmware/releases/download/${firmware_release}/ayab_monolithic_uno.hex"

git add -f "$filepath"

jsonpath=src/main/resources/base/ayab/firmware/firmware.json

current_json="$(cat "$jsonpath")"

echo "$current_json" |
  jq --arg version "$firmware_release" --arg file "$filename" \
    '.controller.uno += [{version: $version, file: $file}]' \
  > "$jsonpath"

git add "$jsonpath"

git commit -m "Add firmware release ${firmware_release}"