// Command swe-fast is the fast-mode SWE-AF node (Python fast/__main__.py).
//
// T0 scaffold: it constructs the agent from env and starts it, registering no
// reasoners yet. Wave 6 (T6.1 fast mode + T6.2 wiring) mounts the fast build
// pipeline plus the full role/orchestrator set. This stub proves the wiring
// compiles and an empty node starts.
package main

import (
	"context"
	"log"
	"os"

	agent "github.com/Agent-Field/agentfield/sdk/go/agent"
)

func main() {
	// Env wiring mirrors Python fast/app.py:24-31 (fast defaults: node id
	// "swe-fast", port 8004).
	cfg := agent.Config{
		NodeID:        envOr("NODE_ID", "swe-fast"),
		Version:       "1.0.0",
		AgentFieldURL: envOr("AGENTFIELD_SERVER", "http://localhost:8080"),
		Token:         os.Getenv("AGENTFIELD_API_KEY"),
		ListenAddress: ":" + envOr("PORT", "8004"),
	}

	app, err := agent.New(cfg)
	if err != nil {
		log.Fatalf("swe-fast: create agent: %v", err)
	}

	// TODO(T6.1/T6.2): register the fast build pipeline, the 7 delegating
	// wrappers, and the full role/orchestrator set via the node package.

	if err := app.Run(context.Background()); err != nil {
		log.Fatalf("swe-fast: run: %v", err)
	}
}

// envOr returns the value of key, or def when the env var is unset or empty.
func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
