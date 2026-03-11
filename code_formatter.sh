#!/bin/bash

# Exit immediately if a command exits with non-zero status
set -e

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}🔄${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

echo -e "${YELLOW}🚀 Starting code quality checks...${NC}"
echo ""

# Run mypy for type checking
print_status "Running mypy type checker..."
if mypy .; then
    print_success "mypy passed"
else
    print_error "mypy failed"
    exit 1
fi
echo ""

# Run ruff for linting and auto-fix
print_status "Running ruff linter with auto-fix..."
if ruff check . --fix; then
    print_success "ruff check passed"
else
    print_error "ruff check failed"
    exit 1
fi
echo ""

# Run ruff for code formatting
print_status "Running ruff formatter..."
if ruff format .; then
    print_success "ruff format completed"
else
    print_error "ruff format failed"
    exit 1
fi
echo ""

echo -e "${GREEN}🎉 All code quality checks completed successfully!${NC}"