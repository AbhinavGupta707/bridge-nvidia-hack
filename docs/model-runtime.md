# Model Runtime Notes

Agent A owns hardware, infra, model readiness, and runtime/deployment notes.
Do not debug runtime symptoms until the feature is actually registered,
discoverable, installed, and activated through its official path.

## Layer-Order Diagnosis

Use this order for every missing model, feature, or integration:

1. Registration/discovery/install state:
   - Is the binary/container/API endpoint present?
   - Is the model listed locally?
   - Is the configured env var selecting that provider/model?
2. Official activation flow:
   - Ollama: `ollama serve`, `ollama pull`, `ollama list`.
   - NIM: NGC access, model license acceptance, image pull, container start,
     then `/v1/models`.
   - ElevenLabs: sponsor/enterprise confirmation of `on_device` versus cloud
     API access before any privacy or performance claim.
3. Runtime, permissions, drivers, performance:
   - Only after the model or integration is registered and selected.

## Target Hardware Assumption

Target device class is NVIDIA DGX Spark / HP ZGX Nano G1n AI Station: GB10
Grace Blackwell, DGX OS / Ubuntu 24.04 class Linux, local NVIDIA GPU stack,
Docker, and enough unified memory to keep several model contexts resident.

Current official reference points checked on 2026-06-06:

- [NVIDIA DGX Spark User Guide](https://docs.nvidia.com/dgx/dgx-spark/index.html)
- [HP ZGX Nano G1n AI Station specifications](https://support.hp.com/us-en/document/ish_13212147-13212192-16)
- [Ollama hardware support](https://docs.ollama.com/gpu)
- [NVIDIA NIM deployment FAQ](https://docs.api.nvidia.com/nim/docs/deployment)
- [NVIDIA NIM LLM API reference](https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html)
- [ElevenLabs Scribe v2 Realtime](https://elevenlabs.io/realtime-speech-to-text)
- [ElevenLabs zero retention mode](https://elevenlabs.io/docs/developers/resources/zero-retention-mode)

## Runtime Modes

```env
BRIDGE_MODE=demo        # demo | hybrid | live
ASR_PROVIDER=demo       # demo | whisper | elevenlabs
TTS_PROVIDER=demo       # demo | piper | kokoro | elevenlabs | browser
LLM_PROVIDER=demo       # demo | ollama | nim
RAG_PROVIDER=local      # local | qdrant | disabled
EMBEDDING_PROVIDER=local # local | ollama | sentence-transformers | disabled
ALLOW_CLOUD=false
```

No mode may claim local sovereignty unless `ALLOW_CLOUD=false` and the selected
ASR, TTS, LLM, embedding, and RAG providers are all local or deterministic demo
fixtures. Browser ASR/TTS are dev fallbacks, not proof that the stack is local.

## First-Hour Commands

Run these before pulling models or debugging permissions:

```bash
git switch agent/infra-models
cp .env.example .env

uname -m
lsb_release -a || cat /etc/os-release
nvidia-smi

docker --version
docker info --format '{{json .Runtimes}}'
docker ps --format '{{.Image}} {{.Names}}'

ollama --version
ollama list
curl http://localhost:11434/api/tags

curl http://localhost:8000/v1/models

python3 scripts/smoke_models.py
./scripts/validate_offline.sh
```

Expected initial state on a fresh device can be mostly warnings. Do not treat
that as a driver bug until the relevant provider is selected and activated.

## Runtime Ladder

Use the first working rung. Do not spend demo time chasing the ideal model if a
lower rung already proves the product.

### Live Translation / Fast LLM

1. Local NIM model already registered on the Spark/ZGX.
2. Ollama Qwen 2.5/3 7B-14B instruct.
3. Ollama Llama 3.1/3.2 8B instruct.
4. Deterministic demo translation fixtures.

Recommended env:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen2.5:7b-instruct
```

Smoke:

```bash
ollama list
ollama pull qwen2.5:7b-instruct
curl http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5:7b-instruct","prompt":"Translate to English: ami aj raat thakar jayga nei.","stream":false}'
LLM_PROVIDER=ollama LLM_MODEL=qwen2.5:7b-instruct python3 scripts/smoke_models.py --strict
```

### Policy / Record Reasoning

1. Local NIM 30B-40B open model if already activated and fast enough.
2. Qwen 2.5/3 32B instruct through Ollama or NIM.
3. Llama 3.3 70B quantized if it loads and decode speed is acceptable.
4. Fast LLM plus stricter prompts and template-backed records.

NIM template:

```bash
export NGC_API_KEY=<ngc-api-key>
export NIM_BASE_URL=http://localhost:8000/v1
export NIM_MODEL=<registered-nim-model-id>

docker login nvcr.io
docker run --rm --gpus all --ipc=host --shm-size=16GB \
  -e NGC_API_KEY="$NGC_API_KEY" \
  -v "$HOME/.cache/nim:/opt/nim/.cache" \
  -p 8000:8000 \
  nvcr.io/nim/<publisher>/<model>:latest

curl "$NIM_BASE_URL/models"
curl "$NIM_BASE_URL/chat/completions" \
  -H 'Content-Type: application/json' \
  -d '{"model":"'"$NIM_MODEL"'","messages":[{"role":"user","content":"Say Bridge is local-first in one sentence."}],"max_tokens":32}'
LLM_PROVIDER=nim NIM_MODEL="$NIM_MODEL" python3 scripts/smoke_models.py --strict
```

Activation note: if `/v1/models` is empty or unreachable, stay in the NIM
registration layer. Check NGC login, license/model access, image name, and
container startup before investigating GPU permissions.

### Embeddings

1. BGE-M3 local embedding model.
2. `multilingual-e5-large`.
3. Smaller multilingual sentence-transformer.
4. Ollama embedding model such as `bge-m3`, `mxbai-embed-large`, or
   `nomic-embed-text` if those are the models already available on the box.

Recommended Ollama env:

```env
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3
OLLAMA_BASE_URL=http://localhost:11434
```

Smoke:

```bash
ollama list
ollama pull bge-m3
curl http://localhost:11434/api/embed \
  -d '{"model":"bge-m3","input":"homelessness appointment with interpreter"}'
EMBEDDING_PROVIDER=ollama EMBEDDING_MODEL=bge-m3 python3 scripts/smoke_models.py --strict
```

If `bge-m3` is not in the local registry or approved model set, do not debug
embedding dimensions yet. Register or select an available local embedding model
first.

### ASR

1. ElevenLabs on-device/on-prem Scribe v2 if sponsor access is explicitly
   granted.
2. Local `faster-whisper` / Whisper large-v3.
3. Demo transcripts.
4. Browser speech recognition only for non-offline development.

Local Whisper env:

```env
ASR_PROVIDER=whisper
WHISPER_MODEL=large-v3
ALLOW_CLOUD=false
```

Smoke:

```bash
python3 -c 'import faster_whisper; print("faster-whisper OK")'
ASR_PROVIDER=whisper python3 scripts/smoke_models.py --strict
```

If the import fails on ARM64, check install state and wheel availability before
debugging CUDA. Demo mode remains valid:

```env
ASR_PROVIDER=demo
```

### TTS

1. ElevenLabs on-device/on-prem multilingual TTS if sponsor access is
   explicitly granted.
2. Piper local voice.
3. Kokoro local model.
4. Pre-rendered/demo audio.
5. Browser speech synthesis only for non-offline development.

Piper env:

```env
TTS_PROVIDER=piper
PIPER_VOICE_PATH=/models/piper/en_GB-voice.onnx
ALLOW_CLOUD=false
```

Smoke:

```bash
command -v piper
test -f "$PIPER_VOICE_PATH"
echo 'Bridge offline speech check.' | piper --model "$PIPER_VOICE_PATH" --output_file /tmp/bridge-piper.wav
TTS_PROVIDER=piper PIPER_VOICE_PATH="$PIPER_VOICE_PATH" python3 scripts/smoke_models.py --strict --audio-smoke
```

Kokoro env:

```env
TTS_PROVIDER=kokoro
KOKORO_MODEL_PATH=/models/kokoro
ALLOW_CLOUD=false
```

Smoke:

```bash
python3 -c 'import kokoro; print("kokoro OK")'
TTS_PROVIDER=kokoro python3 scripts/smoke_models.py --strict
```

## ElevenLabs Access Modes

ElevenLabs is excellent sponsor-fit voice tech, but access mode controls the
claim.

### On-Device / On-Prem Mode

Use only after sponsor or enterprise reps confirm a local runtime/container or
endpoint for the event hardware:

```env
ALLOW_CLOUD=false
ASR_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
ELEVENLABS_ACCESS_MODE=on_device
ELEVENLABS_BASE_URL=http://localhost:<port>
```

Smoke:

```bash
curl "$ELEVENLABS_BASE_URL/health"
python3 scripts/smoke_models.py --require-offline --strict
```

If the endpoint is not known, stay in official activation flow. Do not debug
ports, certificates, or permissions before the access mode and endpoint are
confirmed.

### Cloud Sponsor Mode

Use only as a clearly labelled quality/sponsor mode:

```env
ALLOW_CLOUD=true
ASR_PROVIDER=elevenlabs
TTS_PROVIDER=elevenlabs
ELEVENLABS_ACCESS_MODE=cloud
ELEVENLABS_API_KEY=<api-key>
```

Guardrails:

- Cloud mode cannot support a "nothing leaves the box" demo claim.
- Enable zero-retention and EU residency if available for the account, but do
  not present those as equivalent to on-device processing.
- `./scripts/validate_offline.sh` intentionally fails this mode.

## Offline Validation

Deterministic demo mode should pass on any machine:

```bash
export BRIDGE_MODE=demo
export ALLOW_CLOUD=false
export ASR_PROVIDER=demo
export TTS_PROVIDER=demo
export LLM_PROVIDER=demo
export RAG_PROVIDER=local
export EMBEDDING_PROVIDER=local
./scripts/validate_offline.sh
```

Local live-ish proof with Ollama and local fallbacks:

```bash
export BRIDGE_MODE=hybrid
export ALLOW_CLOUD=false
export LLM_PROVIDER=ollama
export OLLAMA_BASE_URL=http://localhost:11434
export LLM_MODEL=qwen2.5:7b-instruct
export EMBEDDING_PROVIDER=ollama
export EMBEDDING_MODEL=bge-m3
export ASR_PROVIDER=whisper
export WHISPER_MODEL=large-v3
export TTS_PROVIDER=piper
export PIPER_VOICE_PATH=/models/piper/en_GB-voice.onnx
./scripts/validate_offline.sh --audio-smoke
```

`validate_offline.sh` checks cloud guards first, then delegates to
`scripts/smoke_models.py --require-offline --strict`.

## Fallback Recommendations

- If no live LLM is registered: keep `LLM_PROVIDER=demo` and use scripted
  translation fixtures. This preserves the core demo.
- If Ollama is installed but no model is listed: pull one small instruct model
  first; do not debug GPU utilization yet.
- If NIM is selected but `/v1/models` is empty: fix NGC/model/container
  activation before runtime debugging.
- If local embeddings are blocked: use an already installed Ollama embedding
  model or keep keyword/template retrieval for the demo.
- If local ASR is blocked: use demo transcripts. Browser speech recognition is
  not an offline proof.
- If local TTS is blocked: use Piper/Kokoro if installed; otherwise use
  pre-rendered demo audio or text-only demo output.
- If ElevenLabs is cloud-only: set `ALLOW_CLOUD=true`, visibly label sponsor
  mode, and keep `validate_offline.sh` passing with local/demo providers.

## Current Blockers To Confirm On Hardware

- Whether the event DGX Spark / ZGX Nano image already includes Ollama models,
  NIM containers, or only the base runtime.
- Which NIM model IDs are approved and already licensed through NGC.
- Whether ElevenLabs provides on-device/on-prem Scribe v2 and TTS access for the
  event hardware. Public Scribe v2 Realtime docs describe API access; treat
  on-device as unconfirmed until sponsor reps provide the activation path.
- ARM64 availability for `faster-whisper`, Piper, Kokoro, and their model
  assets on the specific device image.
- Availability of local embedding model weights before internet is disabled.
