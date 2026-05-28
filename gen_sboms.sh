#!/usr/bin/env bash
# Generate one CycloneDX SBOM per demo project using Syft, named <dept>-<project>.cdx.json
# so setup_and_upload.py can find them. Clones the demo repos into ./src.
#
# Spec is pinned to CycloneDX 1.5 because Dependency-Track rejects 1.7 (what cdxgen emits).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/src"
OUT="$HERE/sboms"
mkdir -p "$SRC" "$OUT"

SYFT=anchore/syft:latest
docker pull "$SYFT"

clone() { # <git-url> <dir-name>
  [ -d "$SRC/$2/.git" ] || git clone --depth 1 "$1" "$SRC/$2"
}

gen() { # <dept> <project>
  echo ">> generating $1-$2"
  docker run --rm \
    -v "$SRC/$2":/src \
    -v "$OUT":/out \
    "$SYFT" dir:/src -o "cyclonedx-json@1.5=/out/$1-$2.cdx.json" \
    || echo "   WARNING: syft had issues for $1-$2 — inspect $OUT/$1-$2.cdx.json"
}

# acme — Node.js
clone https://github.com/expressjs/express.git            express
clone https://github.com/juice-shop/juice-shop.git        juice-shop
gen acme express
gen acme juice-shop

# beta — Python
clone https://github.com/fastapi/fastapi.git              fastapi
clone https://github.com/pallets/flask.git                flask
gen beta fastapi
gen beta flask

# gamma — Java
clone https://github.com/google/guava.git                 guava
clone https://github.com/spring-projects/spring-petclinic.git spring-petclinic
gen gamma guava
gen gamma spring-petclinic

echo
echo "SBOMs written to $OUT:"
ls -lh "$OUT"
