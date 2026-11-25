---
title: Incident Copilot
emoji: 🛟
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
short_description: Human-supervised LLM root-cause analysis for microservice outages
---

# Agentic Incident-Response Copilot (CMPE 295A prototype)

Real fault injections from the public RCAEval RE2-OB benchmark, replayed as live
incidents: alert → LLM investigation with cited evidence → root-cause report →
playbook remedy → human approval → dry-run execution → verification and feedback loop.

This hosted demo replays the recorded Qwen3-4B investigations (no GPU on the free tier).
Source: https://github.com/PeramVishnuSree/Agentic-incident-response-copilot-for-production-outages
