#!/bin/bash
# Script to manually package Python application with Flask for macOS

# Set up directories
APP_DIR="app"
TEMP_DIR="python_temp"
PACKAGE_DIR="$TEMP_DIR/package"

# Create necessary directories
mkdir -p "$APP_DIR"
mkdir -p "$PACKAGE_DIR"

echo "===== Creating Python package with Flask dependencies ====="

# Copy Python application
cp python/my_app.py "$PACKAGE_DIR"
echo "Copied Python application"

# Install Flask and dependencies into the package directory
python3 -m pip install --target="$PACKAGE_DIR" flask==2.0.1 werkzeug==2.0.2
echo "Installed Flask and dependencies"

# Create the zip file
cd "$PACKAGE_DIR" || exit
echo "Creating zip file..."
zip -r "../../$APP_DIR/app.zip" ./*
cd ../..
echo "Created app.zip in $APP_DIR directory"

# Clean up temporary files
rm -rf "$TEMP_DIR"
echo "Cleaned up temporary files"

echo "===== Package creation complete ====="
echo "Your Python app is packaged with Flask at $APP_DIR/app.zip"
echo "Ready to run your Flutter application!"
