#!/bin/bash
# Helper script for running the Pub/Sub system

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function print_header() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  $1${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

function print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

function print_error() {
    echo -e "${RED}✗${NC} $1"
}

function print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

case "$1" in
    install)
        print_header "Installing Dependencies"
        pip install -r requirements.txt
        print_success "Dependencies installed successfully"
        ;;

    server)
        print_header "Starting Pub/Sub Server"
        python3 main.py
        ;;

    test)
        print_header "Running Test Suite"
        print_info "Make sure the server is running on localhost:8080"
        sleep 2
        python3 test_pubsub.py
        ;;

    client)
        print_header "Starting Interactive Client"
        print_info "Make sure the server is running and 'demo' topic is created"
        python3 example_client.py
        ;;

    config)
        print_header "Current Configuration"
        python3 config.py
        ;;

    docker-build)
        print_header "Building Docker Image"
        docker build -t pubsub-system .
        print_success "Docker image 'pubsub-system' built successfully"
        ;;

    docker-run)
        print_header "Running Docker Container"
        docker run -p 8080:8080 pubsub-system
        ;;

    docker-clean)
        print_header "Cleaning Docker Resources"
        docker stop $(docker ps -q --filter ancestor=pubsub-system) 2>/dev/null || true
        docker rm $(docker ps -aq --filter ancestor=pubsub-system) 2>/dev/null || true
        print_success "Docker containers cleaned"
        ;;

    health)
        print_header "Health Check"
        curl -s http://localhost:8080/health | python3 -m json.tool
        ;;

    stats)
        print_header "System Statistics"
        curl -s http://localhost:8080/stats | python3 -m json.tool
        ;;

    topics)
        print_header "List Topics"
        curl -s http://localhost:8080/topics | python3 -m json.tool
        ;;

    create-topic)
        if [ -z "$2" ]; then
            print_error "Usage: ./run.sh create-topic <topic-name>"
            exit 1
        fi
        print_header "Creating Topic: $2"
        curl -X POST http://localhost:8080/topics \
             -H "Content-Type: application/json" \
             -d "{\"name\": \"$2\"}" | python3 -m json.tool
        ;;

    delete-topic)
        if [ -z "$2" ]; then
            print_error "Usage: ./run.sh delete-topic <topic-name>"
            exit 1
        fi
        print_header "Deleting Topic: $2"
        curl -X DELETE http://localhost:8080/topics/$2 | python3 -m json.tool
        ;;

    demo)
        print_header "Running Quick Demo"

        print_info "Step 1: Creating demo topic..."
        curl -s -X POST http://localhost:8080/topics \
             -H "Content-Type: application/json" \
             -d '{"name": "demo"}' > /dev/null
        print_success "Topic 'demo' created"

        print_info "Step 2: Checking topics..."
        curl -s http://localhost:8080/topics | python3 -m json.tool

        print_info "Step 3: Checking health..."
        curl -s http://localhost:8080/health | python3 -m json.tool

        print_success "Demo completed! You can now use the interactive client:"
        echo -e "  ${YELLOW}./run.sh client${NC}"
        ;;

    clean)
        print_header "Cleaning Python Cache"
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        find . -type f -name "*.pyo" -delete 2>/dev/null || true
        print_success "Python cache cleaned"
        ;;

    help|*)
        print_header "Pub/Sub System Helper Script"
        echo ""
        echo "Usage: ./run.sh <command> [arguments]"
        echo ""
        echo "Available commands:"
        echo ""
        echo "  ${GREEN}install${NC}              Install Python dependencies"
        echo "  ${GREEN}server${NC}               Start the Pub/Sub server"
        echo "  ${GREEN}test${NC}                 Run comprehensive test suite"
        echo "  ${GREEN}client${NC}               Start interactive example client"
        echo "  ${GREEN}config${NC}               Show current configuration"
        echo ""
        echo "  ${GREEN}docker-build${NC}         Build Docker image"
        echo "  ${GREEN}docker-run${NC}           Run Docker container"
        echo "  ${GREEN}docker-clean${NC}         Clean up Docker containers"
        echo ""
        echo "  ${GREEN}health${NC}               Check system health"
        echo "  ${GREEN}stats${NC}                Show system statistics"
        echo "  ${GREEN}topics${NC}               List all topics"
        echo "  ${GREEN}create-topic${NC} <name>  Create a new topic"
        echo "  ${GREEN}delete-topic${NC} <name>  Delete a topic"
        echo ""
        echo "  ${GREEN}demo${NC}                 Run quick demo"
        echo "  ${GREEN}clean${NC}                Clean Python cache files"
        echo "  ${GREEN}help${NC}                 Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./run.sh install"
        echo "  ./run.sh server"
        echo "  ./run.sh create-topic orders"
        echo "  ./run.sh demo"
        echo ""
        ;;
esac
