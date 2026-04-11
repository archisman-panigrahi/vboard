#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Vboard Setup for Ubuntu/Debian${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if running on Debian-based system
if ! command -v apt &> /dev/null; then
    echo -e "${RED}Error: This script is for Debian/Ubuntu-based systems.${NC}"
    echo -e "${RED}apt package manager not found.${NC}"
    exit 1
fi

# Step 1: Update package lists
echo -e "${YELLOW}Step 1: Updating package lists...${NC}"
sudo apt update

# Step 2: Install dependencies
echo -e "${YELLOW}Step 2: Installing dependencies...${NC}"
PACKAGES="python3-gi gir1.2-gtk-3.0 python3-uinput gir1.2-ayatanaappindicator3-0.1 meson ninja-build"

echo "Installing: $PACKAGES"
sudo apt install -y --no-install-recommends $PACKAGES

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to install dependencies.${NC}"
    exit 1
fi

echo -e "${GREEN}Dependencies installed successfully.${NC}"
echo ""

# Step 3: Setup uinput
echo -e "${YELLOW}Step 3: Setting up uinput module...${NC}"
if [ ! -f "scripts/setup-uinput.sh" ]; then
    echo -e "${RED}Error: scripts/setup-uinput.sh not found.${NC}"
    echo -e "${RED}Please run this script from the vboard project root directory.${NC}"
    exit 1
fi

sudo bash scripts/setup-uinput.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: uinput setup failed.${NC}"
    exit 1
fi

echo ""

# Step 4: Build with Meson
echo -e "${YELLOW}Step 4: Building with Meson...${NC}"
PREFIX="/usr"

echo -e "${BLUE}Installing to: $PREFIX${NC}"
echo ""

# Remove old builddir if it exists
if [ -d "builddir" ]; then
    echo "Removing old build directory..."
    rm -rf builddir
fi

mkdir builddir
cd builddir

echo "Configuring Meson..."
meson .. --prefix="$PREFIX"

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Meson configuration failed.${NC}"
    cd ..
    exit 1
fi

echo "Building..."
ninja

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Build failed.${NC}"
    cd ..
    exit 1
fi

echo -e "${GREEN}Build completed successfully.${NC}"
echo ""

# Step 5: Install
echo -e "${YELLOW}Step 5: Installing vboard to $PREFIX...${NC}"

echo "Installing to system location (requires sudo)..."
sudo ninja install

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Installation failed.${NC}"
    cd ..
    exit 1
fi

cd ..

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation completed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo -e "${BLUE}Vboard has been installed to $PREFIX${NC}"
echo ""
echo "You can now run vboard from anywhere:"
echo -e "  ${YELLOW}vboard${NC}"
echo ""
echo -e "${BLUE}For KDE/Plasma integration, the setup is automatic.${NC}"
echo -e "${BLUE}For other environments, see the README for manual setup.${NC}"
echo ""
echo -e "${YELLOW}Please log out and back in or restart your system to ensure all changes take effect.${NC}"
echo ""
