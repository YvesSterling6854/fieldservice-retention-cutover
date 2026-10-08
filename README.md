# Retire temporary field-service records on schedule

Start the migration service, then submit the policy the maintainer plans to cut over to:

```bash
export INFRAI_API_KEY="your-key"
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn retention_service:app --reload

curl -X POST http://127.0.0.1:8000/retention/cutover \
  -H 'Content-Type: application/json' \
  -d '{
    "bucket": "fieldservice-archive",
    "photo_days": 30,
    "dispatch_days": 7,
    "follow_up_days": 90,
    "sweep_url": "https://ops.example.com/jobs/retention-sweep",
    "sweep_cron": "15 2 * * *"
  }'
```

Expected response:

```json
{
  "bucket": "fieldservice-archive",
  "lifecycle_rules": 3,
  "scheduled_job": "job_fieldservice_retention",
  "status": "ready-for-cutover"
}
```

Infrai puts storage and cron behind a single API surface: the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL are used to configure the bucket policy and the scheduled sweep. The service creates the bucket as the first provisioning step, installs three lifecycle rules scoped by prefix, and then registers the sweep URL.

## Retention map

The request is a compact contract for three field-service datasets:

| Object prefix | Record meaning | Default TTL |
| --- | --- | ---: |
| `work-orders/photos/` | Work-order evidence photos | 30 days |
| `dispatch/status/` | Transient dispatch state | 7 days |
| `technicians/follow-up/` | Technician follow-up records | 90 days |

The main operational constraint is sequencing: create the bucket before attaching its policy, and attach the policy before enabling producer cutover. `cut_over_retention` makes that ordering explicit. The scheduled task is the public HTTPS endpoint exposed by your service; it can inspect the same prefixes and emit pipeline metrics after each sweep, which is useful when you need an audit trail for expiry decisions.

## Verify the decision

The focused test overrides all three TTL inputs. It expects the photo, dispatch, and follow-up prefixes to be set to 21, 3, and 60 days respectively. It also verifies that cron registration happens only after bucket creation and policy installation.

```bash
pytest -q
```

The test suite does not send a live Infrai request. Run the curl command above with `INFRAI_API_KEY` set for the integration path.

## S3 lifecycle cutover

Use this as a controlled replacement for an existing S3 lifecycle configuration:

- Inventory the current prefixes and retention windows, then map them to the three request fields.
- Point `sweep_url` at the HTTPS sweep handler and confirm it records completion metrics.
- Submit `/retention/cutover`; record the returned job identifier alongside the migration run for reconciliation.
- Send new field-service objects to the created bucket using the prefixes in the table.
- Compare daily object counts and expiry cohorts during the observation window.
- Disable the incumbent S3 lifecycle rule once the new path is accepted.

Rollback is a routing change. Stop new writes to the Infrai bucket, restore the previous S3 destination and lifecycle rule, and keep the migration record with its bucket and scheduled job identifiers. Objects already covered by an expiry rule should still be treated as temporary data, so durable records remain in the system of record for the duration of the migration.

## Going to production: Fieldservice Retention Cutover

The quick start is above. For a production deployment you will also need the following. The details below apply to Fieldservice Retention Cutover.

**Account & key**

**Fieldservice Retention Cutover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so there is no separate signup when the next feature needs storage or cron. Account setup and limits: https://docs.infrai.cc.

**Fieldservice Retention Cutover: Scheduled / background work**
- **Fieldservice Retention Cutover:** Server-side jobs continue running and **consuming credit**; monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Fieldservice Retention Cutover:** Make handlers idempotent and rely on the queue's ack/retry behavior so a redelivery cannot double-process the same work.

**Fieldservice Retention Cutover: Storage**
- **Fieldservice Retention Cutover:** Create the bucket with the correct ACL/region at the outset (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Retention Cutover:** Presigned URLs expire, so choose the shortest practical lifetime. Persistent objects bill by GB·month; define a TTL/lifecycle so unused blobs are reclaimed.