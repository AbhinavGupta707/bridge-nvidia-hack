#!/usr/bin/env sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

: "${BRIDGE_MODE:=demo}"
: "${ALLOW_CLOUD:=false}"
: "${ASR_PROVIDER:=demo}"
: "${TTS_PROVIDER:=demo}"
: "${LLM_PROVIDER:=demo}"
: "${RAG_PROVIDER:=local}"
: "${EMBEDDING_PROVIDER:=local}"
: "${ELEVENLABS_ACCESS_MODE:=unset}"

echo "Bridge offline validation"
echo "BRIDGE_MODE=$BRIDGE_MODE"
echo "ALLOW_CLOUD=$ALLOW_CLOUD"
echo "ASR_PROVIDER=$ASR_PROVIDER"
echo "TTS_PROVIDER=$TTS_PROVIDER"
echo "LLM_PROVIDER=$LLM_PROVIDER"
echo "RAG_PROVIDER=$RAG_PROVIDER"
echo "EMBEDDING_PROVIDER=$EMBEDDING_PROVIDER"
echo "ELEVENLABS_ACCESS_MODE=$ELEVENLABS_ACCESS_MODE"
echo

if [ "$ALLOW_CLOUD" != "false" ]; then
  echo "FAIL: offline validation requires ALLOW_CLOUD=false" >&2
  exit 1
fi

case "$ASR_PROVIDER:$ELEVENLABS_ACCESS_MODE" in
  elevenlabs:on_device|elevenlabs:on-prem|elevenlabs:on_prem|elevenlabs:local) ;;
  elevenlabs:*)
    echo "FAIL: ASR_PROVIDER=elevenlabs is cloud/unknown unless ELEVENLABS_ACCESS_MODE=on_device" >&2
    exit 1
    ;;
esac

case "$TTS_PROVIDER:$ELEVENLABS_ACCESS_MODE" in
  elevenlabs:on_device|elevenlabs:on-prem|elevenlabs:on_prem|elevenlabs:local) ;;
  elevenlabs:*)
    echo "FAIL: TTS_PROVIDER=elevenlabs is cloud/unknown unless ELEVENLABS_ACCESS_MODE=on_device" >&2
    exit 1
    ;;
esac

case "$LLM_PROVIDER" in
  demo|ollama|nim) ;;
  *)
    echo "FAIL: LLM_PROVIDER must be demo, ollama, or nim for offline validation" >&2
    exit 1
    ;;
esac

case "$ASR_PROVIDER" in
  demo|whisper|elevenlabs) ;;
  *)
    echo "FAIL: ASR_PROVIDER must be demo, whisper, or on-device elevenlabs for offline validation" >&2
    exit 1
    ;;
esac

case "$TTS_PROVIDER" in
  demo|piper|kokoro|elevenlabs) ;;
  *)
    echo "FAIL: TTS_PROVIDER must be demo, piper, kokoro, or on-device elevenlabs for offline validation" >&2
    exit 1
    ;;
esac

python3 scripts/smoke_models.py --require-offline --strict "$@"

echo
echo "Offline validation passed. Any demo claim that nothing leaves the box is valid only for the providers printed above."
