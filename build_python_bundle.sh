#!/bin/bash

# Create a temporary directory for building
mkdir -p python_build
cd python_build

# Create a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages from requirements.txt
pip install -r ../python/requirements.txt

# Create a directory for app files
mkdir -p app
cp ../python/my_app.py app/

# Copy necessary packages to the app directory
pip install -t app/ -r ../python/requirements.txt

# Create a zip file
cd app
zip -r ../../app/app.zip ./*

# Clean up
cd ../..
rm -rf python_build

echo "Python bundle created at app/app.zip"
