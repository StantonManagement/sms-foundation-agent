# Infrastructure and Deployment

## Infrastructure as Code
- Tool: Terraform 1.7.x
- Location: `infrastructure/terraform`
- Approach: Module-per-environment; Cloud Run service + secret bindings; output service URL for Twilio webhooks.

## Deployment Strategy
- Strategy: Build container → push to registry → deploy to Cloud Run with min instances=1 (reduce cold starts).
- CI/CD Platform: GitHub Actions
- Pipeline Configuration: `.github/workflows/deploy.yaml` (build, test, push, deploy; env-specific variables)

## Environments
- Development: Dev testing and integration with Twilio dev number; permissive CORS; verbose logging.
- Staging: Pre-prod tests with real callbacks; load tests; masked logs.
- Production: Hardened config; IP allowlist or WAF on webhook if feasible; min instances scaled per traffic.

## Promotion Flow
PR → CI tests → merge to main → deploy to staging → automated smoke → manual approval → deploy to prod.

## Rollback Strategy
- Primary Method: Cloud Run revision rollback (pin to previous image); retain N previous images.
- Triggers: Elevated error rates, failed smoke tests, alert thresholds.
- RTO: < 15 minutes.
