// Package schemas holds the Go ports of every Pydantic data/result model used
// by SWE-AF, with JSON tags matching the exact snake_case field names emitted
// by Pydantic's model_dump() (no omitempty anywhere — Python emits every key).
//
// Non-zero Pydantic defaults are reproduced via defaultXxx() constructors plus
// UnmarshalJSON methods (see defaults.go): Go's json.Unmarshal leaves absent
// keys at the Go zero value, whereas Pydantic fills the declared default, so a
// missing key must be seeded to match Python output.
package schemas

// AdvisorAction is what the Issue Advisor decided to do after a coding loop
// failure. Ported verbatim from execution/schemas.py::AdvisorAction.
type AdvisorAction string

const (
	AdvisorActionRetryModified    AdvisorAction = "retry_modified"     // Relax ACs, retry coding loop
	AdvisorActionRetryApproach    AdvisorAction = "retry_approach"     // Keep ACs, different strategy
	AdvisorActionSplit            AdvisorAction = "split"              // Break into sub-issues
	AdvisorActionAcceptWithDebt   AdvisorAction = "accept_with_debt"   // Close enough, record gaps
	AdvisorActionEscalateToReplan AdvisorAction = "escalate_to_replan" // Flag for outer loop
)

// IssueOutcome is the outcome of executing a single issue. Ported verbatim from
// execution/schemas.py::IssueOutcome.
type IssueOutcome string

const (
	IssueOutcomeCompleted           IssueOutcome = "completed"
	IssueOutcomeCompletedWithDebt   IssueOutcome = "completed_with_debt" // Accepted via ACCEPT_WITH_DEBT
	IssueOutcomeFailedRetryable     IssueOutcome = "failed_retryable"
	IssueOutcomeFailedUnrecoverable IssueOutcome = "failed_unrecoverable"
	IssueOutcomeFailedNeedsSplit    IssueOutcome = "failed_needs_split" // Advisor wants to split
	IssueOutcomeFailedEscalated     IssueOutcome = "failed_escalated"   // Advisor escalated to replanner
	IssueOutcomeSkipped             IssueOutcome = "skipped"
)

// ReplanAction is what the replanner decided to do. Ported verbatim from
// execution/schemas.py::ReplanAction.
type ReplanAction string

const (
	ReplanActionContinue    ReplanAction = "continue"     // proceed unchanged
	ReplanActionModifyDAG   ReplanAction = "modify_dag"   // restructured
	ReplanActionReduceScope ReplanAction = "reduce_scope" // dropped non-essential issues
	ReplanActionAbort       ReplanAction = "abort"        // cannot recover
)

// QASynthesisAction is the decision from the feedback synthesizer. Ported
// verbatim from execution/schemas.py::QASynthesisAction.
type QASynthesisAction string

const (
	QASynthesisActionFix     QASynthesisAction = "fix"
	QASynthesisActionApprove QASynthesisAction = "approve"
	QASynthesisActionBlock   QASynthesisAction = "block"
)
