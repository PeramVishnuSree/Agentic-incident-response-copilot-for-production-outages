"""Read-only RCA agent (Patrini).

Diagnoses likely root causes using read-only tools and must cite evidence for
each candidate. This package has NO write path to the cluster by design: the
restricted executor service is the only component that can mutate state.
"""
