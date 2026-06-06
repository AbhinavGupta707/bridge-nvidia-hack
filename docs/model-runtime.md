# Model Runtime Notes

Follow layer-order diagnosis:

1. Check registration/discovery/install state.
2. Check official activation flows.
3. Only then debug permissions, runtime, drivers, or performance.

## First-Hour Checks On DGX Spark Or ZGX Nano

```bash
uname -m
lsb_release -a
nvidia-smi
docker --version
docker info
ollama list
```

## Runtime Modes

- `BRIDGE_MODE=demo`: deterministic fixtures; must always work offline.
- `BRIDGE_MODE=hybrid`: local RAG plus selected live providers.
- `BRIDGE_MODE=live`: full live audio path.

No mode may claim local sovereignty unless `ALLOW_CLOUD=false`.

