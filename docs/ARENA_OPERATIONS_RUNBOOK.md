# Arena Operations Runbook

This runbook covers the Scrap Pit season reset for Terminal Frontier.

## Schedule

The backend scheduler attempts to run the arena season reset every Sunday shortly after 00:00 UTC. The reset is guarded by a UTC ISO week season key, so repeated scheduler or admin calls in the same season are skipped unless `force=true` is used.

## What The Reset Does

- Destroys all `chassis_parts` owned by pit fighter agents.
- Resets pit fighter stats to zero because arena stats come only from donated gear.
- Soft-resets Elo halfway back toward 1200.
- Clears arena wins, losses, and daily opponents.
- Writes one global `ARENA_SEASON_RESET` audit log.
- Writes one `ARENA_SEASON_RESET_AGENT` audit log per pit fighter.

## Manual Reset

Use this only when the scheduler did not run or after verifying a partial reset needs a retry.

```bash
curl -X POST "$BASE_URL/api/admin/arena/reset_season" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

Expected response:

```json
{
  "status": "ok",
  "season_key": "2026-W23",
  "fighters_reset": 12,
  "parts_destroyed": 31,
  "source": "admin",
  "reset_at": "2026-06-07T00:05:00+00:00"
}
```

If the reset already ran for that week, the endpoint returns:

```json
{
  "status": "skipped",
  "reason": "already_reset",
  "season_key": "2026-W23",
  "fighters_reset": 0,
  "parts_destroyed": 0,
  "source": "admin"
}
```

## Force Reset

Use `force=true` only after checking the audit logs and confirming the prior reset record is wrong or incomplete.

```bash
curl -X POST "$BASE_URL/api/admin/arena/reset_season" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"force": true}'
```

## Audit Verification

Check for the global reset record:

```sql
SELECT time, details
FROM audit_logs
WHERE event_type = 'ARENA_SEASON_RESET'
ORDER BY time DESC
LIMIT 5;
```

Check individual fighter reset records:

```sql
SELECT agent_id, details
FROM audit_logs
WHERE event_type = 'ARENA_SEASON_RESET_AGENT'
ORDER BY time DESC
LIMIT 20;
```

After a successful reset, pit fighters with no donated gear should have `max_health = 0`, `damage = 0`, no owned `chassis_parts`, and an arena profile with wins/losses reset to zero.
