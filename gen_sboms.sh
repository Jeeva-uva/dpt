#!/usr/bin/env bash
# Generate one CycloneDX SBOM per demo project, named <dept>-<project>.cdx.json
# so setup_and_upload.py can find them. Clones the demo repos into ./src.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/src"
OUT="$HERE/sboms"
mkdir -p "$SRC" "$OUT"

CDXGEN=ghcr.io/cyclonedx/cdxgen:latest
docker pull "$CDXGEN"

clone() { # <git-url> <dir-name>
  [ -d "$SRC/$2/.git" ] || git clone --depth 1 "$1" "$SRC/$2"
}

gen() { # <dept> <project> <cdxgen-type>
  echo ">> generating $1-$2 ($3)"
  docker run --rm \
    -v "$SRC/$2":/src \
    -v "$OUT":/out \
    "$CDXGEN" -t "$3" -o "/out/$1-$2.cdx.json" /src \
    || echo "   WARNING: cdxgen had issues for $1-$2 — inspect $OUT/$1-$2.cdx.json"
}

# acme — Node.js
clone https://github.com/expressjs/express.git            express
clone https://github.com/juice-shop/juice-shop.git        juice-shop
gen acme express    js
gen acme juice-shop js

# beta — Python
clone https://github.com/fastapi/fastapi.git              fastapi
clone https://github.com/pallets/flask.git                flask
gen beta fastapi python
gen beta flask   python

# gamma — Java
clone https://github.com/google/guava.git                 guava
clone https://github.com/spring-projects/spring-petclinic.git spring-petclinic
gen gamma guava            java
gen gamma spring-petclinic java

echo
echo "SBOMs written to $OUT:"
ls -lh "$OUT"
