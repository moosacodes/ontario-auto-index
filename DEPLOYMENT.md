# Deployment

## GitHub Actions and Pages

GitHub Pages is the initial public host. The Pages workflow builds the
frontend against the committed, validated snapshot on pushes to `main` and
manual dispatches, then publishes it through the Actions deployment API.
Publishing has a concurrency group so a newer release cancels an older pending
publication. The repository Pages source must be set to **GitHub Actions**;
Pages is not configured from a branch directory.

The `Live inventory refresh` workflow runs every six hours at minute 17 and
also supports manual dispatch. It runs the permitted supported-dealer adapters,
rejects invalid records, generates a deterministic snapshot, builds the
frontend, and publishes the result directly to Pages. It does not commit
vehicle records to Git, so refreshes do not create an unbounded history or
build-and-commit loop. A failed validation or crawl fails the publication
instead of replacing the last successful Pages release.

Actions use minimum permissions, explicit timeouts, bounded retries, and manual
dispatch inputs. Crawlers are sharded deterministically and do not rely on
runner disks between jobs. The six-hour cadence applies only to currently
supported sources; newly discovered dealerships remain excluded until their
permissions and adapter have been verified.

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
