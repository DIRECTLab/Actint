.PHONY: help install setup clean run run-mcp run-llm test health docs

help:
	@echo "AIS Vessel Intelligence MCP System"
	@echo "===================================="
	@echo ""
	@echo "Available targets:"
	@echo "  install      - Install dependencies"
	@echo "  setup        - Setup configuration (.env)"
	@echo "  run          - Run both servers (requires tmux)"
	@echo "  run-mcp      - Run only MCP server"
	@echo "  run-llm      - Run only LLM server"
	@echo "  test         - Run example client tests"
	@echo "  health       - Check system health"
	@echo "  docs         - Open documentation"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-run   - Run with Docker Compose"
	@echo "  clean        - Remove temporary files"
	@echo "  help         - Show this help message"

install:
	pip install -r requirements.txt
	@echo "✓ Dependencies installed"

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file (edit as needed)"; \
	else \
		echo "✓ .env already exists"; \
	fi

run: setup
	@command -v tmux >/dev/null 2>&1 || { echo "Error: tmux not installed"; exit 1; }
	tmux new-session -d -s ais-mcp bash start_mcp_server.sh
	sleep 3
	tmux new-window -t ais-mcp bash start_llm_server.sh
	@echo "✓ Both servers started in tmux session 'ais-mcp'"
	@echo "  View logs: tmux attach -t ais-mcp"
	@echo "  Stop:      tmux kill-session -t ais-mcp"

run-mcp: setup
	bash start_mcp_server.sh

run-llm: setup
	bash start_llm_server.sh

test: setup
	python example_client.py

health:
	@curl -s http://localhost:8000/health | python -m json.tool
	@echo ""

docs:
	@echo "Documentation:"
	@echo "  README.md       - Full documentation"
	@echo "  QUICKSTART.md   - 5-minute setup guide"
	@echo "  API_REFERENCE.md - API endpoints and tools"

docker-build:
	docker build -t ais-vessel-intelligence:latest .

docker-run: setup
	docker-compose up

docker-stop:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf .pytest_cache .coverage
	@echo "✓ Cleaned up temporary files"

.DEFAULT_GOAL := help
