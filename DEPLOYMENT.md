# Deployment

## GitHub Actions and Pages

GitHub Pages is the initial public host. The deployment workflow builds the
frontend against a validated snapshot artifact and publishes it only after
validation. Publishing has a concurrency group so a newer release cancels an
older pending publication.

Actions use minimum permissions, explicit timeouts, bounded retries, and manual
dispatch inputs. Crawlers are sharded deterministically and do not rely on
runner disks between jobs.

## Access and privacy

Pages is publicly accessible. No credentials, secrets, personal information,
private dealer contact data, or restricted licensed inventory may be placed in
the site or snapshots. Frontend password prompts are not security.

If family-only access becomes required, move the site to a host with
server-side authentication and document the provider, enforcement point,
session handling, and cost/limits before implementing it.

## Storage escalation

Start with GitHub Actions artifacts and the Pages release output within the
budgets in [ARCHITECTURE.md](ARCHITECTURE.md). If data exceeds those limits,
evaluate a free-tier object store only after measuring snapshot size, egress,
request volume, retention, CORS, and availability. Do not silently switch to a
provider or claim indefinite free operation.
