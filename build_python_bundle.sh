#!/bin/bash

# Create a temporary directory for building
mkdir -p python_build
cd python_build

# Create a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Print diagnostic information
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Determine if we're on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Detected macOS, installing platform-specific libraries"
    # Install macOS-specific packages with pip and collect output
    echo "Installing pyobjc packages..."
    pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz
    
    # Verify installations
    echo "Verifying macOS dependencies..."
    python -c "import objc; print('objc module version:', objc.__version__)"
    python -c "import AppKit; print('AppKit available')"
    python -c "import Quartz; print('Quartz available')"
fi

# Install required packages from requirements.txt
echo "Installing packages from requirements.txt..."
pip install -r ../python/requirements.txt

# Create a directory for app files
mkdir -p app
cp ../python/my_app.py app/

# Copy necessary packages to the app directory
echo "Copying packages to app directory..."
pip install -t app/ -r ../python/requirements.txt

# On macOS, ensure PyObjC libraries are included and properly installed
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Ensuring macOS libraries are included in the bundle..."
    pip install -t app/ pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz
    
    # Fix potential __pycache__ issues in the objc module
    echo "Cleaning up __pycache__ directories..."
    find app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    
    # Create empty __init__.py files where needed
    echo "Ensuring __init__.py files exist..."
    find app -type d -exec touch {}/__init__.py \; 2>/dev/null || true
fi

# Create a zip file
cd app
echo "Creating zip archive..."
zip -r ../../app/app.zip ./*

# Clean up
cd ../..
rm -rf python_build

echo "Python bundle created at app/app.zip"
