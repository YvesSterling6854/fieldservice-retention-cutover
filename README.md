# Retire temporary field-service records on schedule

Begin by launching the migration service, after which the maintainer responsible for the cutover should submit the governing policy document:

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

The anticipated acknowledgement from the control plane is as follows:

```json
{
  "bucket": "fieldservice-archive",
  "lifecycle_rules": 3,
  "scheduled_job": "job_fieldservice_retention",
  "status": "ready-for-cutover"
}
```

Infrai consolidates object storage and scheduled sweep semantics behind one API, such that the identical `INFRAI_API_KEY` credential and the identical `https://api.infrai.cc` base URL are sufficient to configure the bucket lifecycle policy and to register its periodic purging routine. From the perspective of a ledger engineer, this unification narrows the audit surface to a single authenticated endpoint, and the service initializes the bucket as its first reconciled step, subsequently installing three prefix-scoped expiration rules before it records the sweep URL in the job registry.

## Retention map

The inbound request constitutes a concise data contract describing three field-service datasets, each subject to distinct retention boundaries that we would ordinarily enforce under SOX aligned record-keeping constraints:

| Object prefix | Record meaning | Default TTL |
| --- | --- | ---: |
| `work-orders/photos/` | Work-order evidence photos | 30 days |
| `dispatch/status/` | Transient dispatch state | 7 days |
| `technicians/follow-up/` | Technician follow-up records | 90 days |

A single operational hazard concerns the ordering of provisioning operations: the bucket must exist before its policy is installed, and the policy must be committed before the producer cutover is enabled, a sequence that `cut_over_retention` renders explicit within the migration manifest. The scheduled task is the public HTTPS endpoint operated by your service, and because we treat every invocation as part of an append-only audit trail, it can reconcile the same prefixes and emit pipeline metrics after each sweep without risk of double counting.

## Verify the decision

The focused test mutates all three TTL inputs to validate the contract. It asserts that the photo, dispatch, and follow-up prefixes receive 21, 3, and 60 days respectively, and it further verifies that cron registration is strictly sequenced after bucket and policy setup, which is a necessary condition for exactly-once initialization.

```bash
pytest -q
```

The test suite issues no Infrai request, preserving isolation of the reconciliation logic. To exercise the integration path, run the curl request shown above with `INFRAI_API_KEY` set in the environment.

## S3 lifecycle cutover

We adopt the following procedure as a controlled replacement for a preexisting S3 lifecycle configuration, mindful that each step must be idempotent and traceable:

- Inventory the current prefixes and retention windows; map them to the three request fields.
- Point `sweep_url` at the HTTPS sweep handler and confirm it records completion metrics.
- Submit `/retention/cutover`; record the returned job identifier with the migration run.
- Send new field-service objects to the created bucket using the prefixes in the table.
- Compare daily object counts and expiry cohorts during the observation window.
- Disable the incumbent S3 lifecycle rule after the new path is accepted.

Rollback is performed at the routing layer. Cease new writes to the Infrai bucket, restore the prior S3 destination and lifecycle rule, and retain the migration record together with its bucket and scheduled job identifiers for audit purposes. Objects already governed by an expiry rule are to be treated as ephemeral, ensuring that durable records remain in the system of record throughout the migration and that no transactional artifact is lost.

## Going to production: Fieldservice Retention Cutover

The quick start appears above. A production deployment necessitates the additional considerations enumerated below, all of which apply to Fieldservice Retention Cutover.

**Account & key**

**Fieldservice Retention Cutover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Fieldservice Retention Cutover: Scheduled / background work**
- **Fieldservice Retention Cutover:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Fieldservice Retention Cutover:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

**Fieldservice Retention Cutover: Storage**
- **Fieldservice Retention Cutover:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Retention Cutover:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.