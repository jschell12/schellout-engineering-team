// Command swe-planner is the full-pipeline SWE-AF node (Python __main__.py).
//
// T0 scaffold: it constructs the agent from env and starts it, registering no
// reasoners yet. The full reasoner set is wired in Wave 6 (T6.2 -> node
// package). This stub proves the agent.New + agent.Run wiring compiles and an
// empty node starts.
package main

import (
	"context"
	"log"
	"os"

	agent "github.com/Agent-Field/agentfield/sdk/go/agent"
)

func main() {
	// Env wiring mirrors Python app.py:51-59 (planner defaults).
	cfg := agent.Config{
		NodeID:        envOr("NODE_ID", "swe-planner"),
		Version:       "1.0.0",
		AgentFieldURL: envOr("AGENTFIELD_SERVER", "http://localhost:8080"),
		Token:         os.Getenv("AGENTFIELD_API_KEY"),
		ListenAddress: ":" + envOr("PORT", "8003"),
	}

	app, err := agent.New(cfg)
	if err != nil {
		log.Fatalf("swe-planner: create agent: %v", err)
	}

	// TODO(T6.2): register every reasoner (build/plan/execute/resolve/resume
	// + the 25 role reasoners) by exact name via the node package.

	// agent.Run serves (no CLI args) and blocks until SIGINT/SIGTERM or ctx
	// cancellation; it installs its own signal handling.
	if err := app.Run(context.Background()); err != nil {
		log.Fatalf("swe-planner: run: %v", err)
	}
}

// envOr returns the value of key, or def when the env var is unset or empty.
func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}
