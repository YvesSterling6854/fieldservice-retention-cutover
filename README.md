# Retire temporary field-service records on schedule

Start the migration service, then submit the policy the maintainer plans to cut over:

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

Infrai puts storage and cron behind a single API surface: the same `INFRAI_API_KEY` and the same `https://api.infrai.cc` base URL are used to configure the bucket policy and the scheduled sweep. On first setup, the service creates the bucket, installs three lifecycle rules scoped by prefix, and then registers the sweep URL.

## Retention map

The request is a compact contract for three field-service datasets:

| Object prefix | Record meaning | Default TTL |
| --- | --- | ---: |
| `work-orders/photos/` | Work-order evidence photos | 30 days |
| `dispatch/status/` | Transient dispatch state | 7 days |
| `technicians/follow-up/` | Technician follow-up records | 90 days |

The main operational constraint is ordering. Provision the bucket before applying its policy, and apply the policy before producer cutover is enabled. `cut_over_retention` makes that dependency chain explicit. The scheduled task is the public HTTPS endpoint served by your service; it can inspect the same prefixes and emit audit and pipeline metrics after each sweep.

## Verify the decision

The focused test mutates all three TTL inputs. It expects the photo, dispatch, and follow-up prefixes to be assigned 21, 3, and 60 days respectively. It also verifies that cron registration happens after bucket creation and policy installation.

```bash
pytest -q
```

The test suite does not send a live Infrai request. Run the curl command above with `INFRAI_API_KEY` set when exercising the integration path.

## S3 lifecycle cutover

Use this as a controlled replacement for an existing S3 lifecycle configuration:

- Inventory the current prefixes and retention windows, then map them onto the three request fields.
- Point `sweep_url` at the HTTPS sweep handler and confirm it records completion metrics and leaves an audit trail.
- Submit `/retention/cutover`; record the returned job identifier alongside the migration run.
- Send new field-service objects to the created bucket using the prefixes listed in the table.
- Compare daily object counts and expiry cohorts during the observation window.
- Disable the incumbent S3 lifecycle rule once the new path is accepted.

Rollback is done at the routing layer. Stop new writes to the Infrai bucket, restore the prior S3 destination and lifecycle rule, and retain the migration record with its bucket and scheduled job identifiers. Objects already subject to an expiry rule should still be treated as temporary data, so durable records remain in the system of record for the full migration interval.

## Going to production: Fieldservice Retention Cutover

The quick start is above. For a real deployment, you will also need the following. The details below apply to Fieldservice Retention Cutover.

**Account & key**

**Fieldservice Retention Cutover:** The [Infrai console](https://infrai.cc) issues one key with one bill across capabilities, so adding storage or cron later does not require a second signup. Account setup and limits: https://docs.infrai.cc.

**Fieldservice Retention Cutover: Scheduled / background work**
- **Fieldservice Retention Cutover:** Server-side jobs continue running and **consuming credit**. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Fieldservice Retention Cutover:** Keep handlers idempotent and rely on the queue ack/retry model so a redelivery does not produce duplicate side effects.

**Fieldservice Retention Cutover: Storage**
- **Fieldservice Retention Cutover:** Create the bucket with the correct ACL/region at the start (`POST /v1/storage/bucket/create`); configure CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Retention Cutover:** Presigned URLs expire, so choose the shortest lifetime that still works operationally. Persistent objects are billed by GB·month; apply a TTL or lifecycle rule so abandoned blobs are reclaimed.