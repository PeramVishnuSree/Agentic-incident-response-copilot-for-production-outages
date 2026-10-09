# executor (Peram — built in S4)

**The only component with a write path to the cluster.** Executes only
allowlisted actions in allowlisted namespaces (E9), after a recorded approval
from the approval-service. Supports dry-run, rate limiting, and undo. Out-of-policy
requests are rejected and logged.
