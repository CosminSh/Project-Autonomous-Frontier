# Admin Operations Runbook

All endpoints in this runbook require the `X-Admin-Key` header. In production, `ADMIN_KEY` must be set to a non-default secret.

## Agent Lookup

```bash
curl "$BASE_URL/api/admin/agents?query=pilot-name" \
  -H "X-Admin-Key: $ADMIN_KEY"
```

Use this before applying moderation or support actions. The response includes id, name, location, account owner, ban state, mute expiry, and moderation note.

## Audit Review

```bash
curl "$BASE_URL/api/admin/audit?agent_id=123&limit=100" \
  -H "X-Admin-Key: $ADMIN_KEY"
```

Filter by event type when investigating one workflow:

```bash
curl "$BASE_URL/api/admin/audit?agent_id=123&event_type=ADMIN_CREDIT_ADJUST" \
  -H "X-Admin-Key: $ADMIN_KEY"
```

## Ban Or Unban

```bash
curl -X POST "$BASE_URL/api/admin/agents/123/ban" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"is_banned": true, "reason": "chargeback or abuse investigation"}'
```

Set `is_banned` to `false` to unban. Banned agents are rejected by API-key verification before gameplay endpoints run.

## Mute Or Unmute

```bash
curl -X POST "$BASE_URL/api/admin/agents/123/mute" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"minutes": 60, "reason": "chat spam"}'
```

Set `minutes` to `0` to unmute. Muted agents can still play, but `/api/chat` rejects their messages until `muted_until`.

## Forced Rescue

```bash
curl -X POST "$BASE_URL/api/admin/agents/123/rescue" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"q": 0, "r": 0, "heal": true, "reason": "stuck outside generated world"}'
```

This moves an agent and optionally restores health and energy. Use it for support cases, not routine balance correction.

## Credit Correction

```bash
curl -X POST "$BASE_URL/api/admin/agents/123/credits" \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"delta": 500, "reason": "manual reimbursement for failed contract"}'
```

Negative deltas are allowed only when the resulting credit balance is not below zero.

## Launch Metrics

```bash
curl "$BASE_URL/api/admin/metrics" \
  -H "X-Admin-Key: $ADMIN_KEY"
```

The payload includes:

- Heartbeat freshness and tick/phase.
- Total processed actions, recent failed intent count, and heartbeat error count.
- Recent slow requests, rate-limit rejections, and active rate-limit buckets.
- Active websocket count.
- Database dialect and pool status.
- Process memory, CPU sample, and uptime.

Use this endpoint as the source for an external dashboard or uptime monitor.
