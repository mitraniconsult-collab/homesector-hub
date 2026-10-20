# Render build change

Existing Render service srv-dare9jojo6nc73fkceig currently ignores patches/worker. After reviewing PR #6 and verifying staging, change **Build Command** in the existing Render service to:

```bash
bash scripts/render-worker-build.sh
```

Keep the existing Start Command. The script unpacks the bundled source, applies patches/worker, syntax-checks Python, checks that the Feed Manager router is importable, and installs dependencies. Do not change production until the feed endpoints are tested in staging. A code commit alone cannot change the existing service's Build Command.

Do not use `render.yaml` to overwrite or recreate the existing production service. The worker requires its existing environment configuration.
