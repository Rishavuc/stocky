#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
./node_modules/.bin/vite build --config extension.config.ts
cd ..
cp extension/manifest.json extension/detect.js extension/dist/
