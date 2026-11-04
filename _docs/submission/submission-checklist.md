# Submission checklist

Compared against the [current course criteria](https://github.com/DataTalksClub/ai-dev-tools-zoomcamp/blob/main/project/README.md), which list 12 criteria and 24 points. This is an evidence map, not an awarded score; the reviewer determines the grade.

| Criterion | Evidence and open questions |
| --- | --- |
| Problem description | [README](../../README.md) describes the problem, functionality and expected behaviour. |
| Product specification | [Product plan](../plan.md) and [public issues](https://github.com/ShaneGore/BenchScope/issues) record requirements and work. |
| Agent team | [Process](../process.md) and [role instructions](../team/) describe PM, engineering and QA responsibilities. |
| Context management | [AGENTS.md](../../AGENTS.md) links modular project documentation. |
| Application | Frontend, FastAPI and PostgreSQL are present; see README for setup. Full clean-start execution should be verified. |
| Testing | Unit and integration tests exist; the PostgreSQL-dependent tests require a disposable database. A single-command all-tests workflow has not been established here. |
| Containerization | Compose defines frontend, API and PostgreSQL plus observability. First-time environment and secret setup are required. |
| Deployment | README links the deployed frontend and API; check both are reachable during review. |
| CI/CD | GitHub Actions workflows define checks and staging deployment; manual production deployment evidence is not established here. |
| Observability | Local OpenTelemetry, Prometheus, Grafana, Loki and Tempo setup and incident evidence are documented. Hosted correlation has not been verified here. |
| Alerting on user impact | Alert rules and local incident exercise are documented under [incidents](../incidents/). |
| On-call agent | Supervised recovery exists; evidence of an autonomous agent waking on an alert and fixing an issue is not established here. |

- [ ] Complete **three peer reviews** in the course platform; this is required to pass.
- [ ] Confirm current deployment and complete the submission form on the course platform.
