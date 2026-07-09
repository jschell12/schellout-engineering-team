# SWE-AF Go port — build/test targets. Run from the go/ directory.
# Mirrors the acceptance gate used by every port task and CI (design §10):
#   go build ./... && go vet ./... && go test ./...

.PHONY: build vet test check lint run-planner run-fast

# Compile every package in the module.
build:
	go build ./...

# Static analysis (go vet) across the module.
vet:
	go vet ./...

# Unit tests across the module.
test:
	go test ./...

# The full local gate CI runs: vet + tests.
check: vet test

# Optional lint pass; no-op with a hint when golangci-lint is not installed.
lint:
	@command -v golangci-lint >/dev/null 2>&1 && golangci-lint run || \
		echo "golangci-lint not installed; skipping (install: https://golangci-lint.run)"

# Run the full-pipeline node (swe-planner, default port 8003).
run-planner:
	go run ./cmd/swe-planner

# Run the fast-mode node (swe-fast, default port 8004).
run-fast:
	go run ./cmd/swe-fast
