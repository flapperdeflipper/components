# vmproxy

Serves the VictoriaMetrics add-on's web UI (vmui) at the Home Assistant
origin root, so it works with regular HA authentication and without the
broken ingress path.

- `/vmui/` — the vmui dashboard
- `/api/v1/*` — the Prometheus-compatible query API

## Why this exists

vmui hardcodes root-absolute URLs (`/api/v1/...` for queries, `/vmui/...`
for links). Under the HA ingress prefix `/api/hassio_ingress/<token>/` those
requests escape the prefix and hit Home Assistant's own router, which is why
the add-on's ingress entry shows a dead page after the basic-auth prompt.
VictoriaMetrics has no base-URL flag (`-http.pathPrefix` changes what the
server *accepts*, not what the browser *sends*, and ingress strips its prefix
before the add-on sees the request anyway).

Claiming the paths at the origin root is the only fix that requires no URL
rewriting: one proxy hop (HA → add-on), auth is your HA login, and the
add-on's `-httpAuth` credentials are attached server-side from `secrets.yaml`.

## Configuration

Package file `configuration/vmproxy.yaml`:

```yaml
vmproxy:
  host: 8f49de54-victoria-metrics   # add-on container hostname on the hassio network
  port: 8428
  username: !secret victoria_metrics_username
  password: !secret victoria_metrics_password
```

`username`/`password` are only needed while the add-on runs with
`enableHTTPAuth: true`; they are forwarded as basic auth to VictoriaMetrics
and never sent to the browser.

## Notes and limits

- Requires a Home Assistant **restart** to load (custom integration code has
  no reload).
- `/api/v1/*` and `/vmui` were verified unclaimed on HA 2026.8.3. If a future
  integration registers them first, setup fails loudly with a duplicate-route
  error in the log.
- The vmalert pages inside vmui (`/vmalert/...`) are not proxied - the
  add-on runs single-node vmalert-less anyway.
- Direct access via the exposed host port 8428 keeps working unchanged.
- The ingress entry on the add-on can be ignored (or the add-on fork can drop
  it later).
