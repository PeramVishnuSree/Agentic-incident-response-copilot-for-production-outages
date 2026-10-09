# Cross-service integration / end-to-end tests

Unit tests live beside each service (`services/*/tests`, `libs/*/tests`). This
directory is for integration and end-to-end tests that span services — e.g. the
vertical-prototype flow: inject fault → collect → correlate → RCA → approve →
restricted execute → recover → score (S5).
