"""Correlation engine (Patrini).

Groups related signals into one incident using time windows and the service
dependency graph, then ranks candidate root causes deterministically -- before
any LLM is involved -- so a result is always available even if the model is
down (NFR: resilience). Implemented in S2 (grouping) and S3 (ranking v1).
"""
