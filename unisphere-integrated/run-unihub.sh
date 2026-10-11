#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
export FRONTEND_DIR="$PWD/public/unihub"
export ADMIN_TOKEN="${ADMIN_TOKEN:-admin123}"

echo "Installing UniHub backend dependencies..."
python3 -m pip install -r "$PWD/unihub/backend/requirements.txt"

echo "Starting UniSphere with the integrated UniHub module..."
echo "Vite will open the UniSphere portal at the actual available Local URL."
npm run dev -- --open
