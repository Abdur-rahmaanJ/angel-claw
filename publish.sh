#!/usr/bin/env bash

set -e  # Exit on error

echo "🧹 Cleaning old builds..."
rm -rf dist/ build/ *.egg-info

echo "📦 Building package..."
python3 -m build

echo "🔍 Checking package..."
python3 -m twine check dist/*

# Prompt for token (hidden input)
echo "🔐 Enter your PyPI token:"
read -s PYPI_TOKEN
echo ""

export TWINE_USERNAME="__token__"
export TWINE_PASSWORD="$PYPI_TOKEN"

echo "🚀 Uploading to PyPI (skipping existing versions)..."
python3 -m twine upload --skip-existing dist/*

echo "✅ Done!"