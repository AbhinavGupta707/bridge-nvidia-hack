#!/usr/bin/env python3
"""Layered runtime discovery and smoke checks for Bridge.

The script is intentionally stdlib-only so it can run early on DGX Spark / ZGX
Nano class hardware before the application environment is fully installed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_NIM_URL = "http://localhost:8000/v1"
LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
CLOUD_PROVIDER_NAMES = {"elevenlabs"}


@dataclass
class Check:
    name: str
    status: str
    detail: str
    layer: str
    command: str | None = None
    recommendation: str | None = None


@dataclass
class Report:
    started_at: str
    config: dict[str, str]
    checks: list[Check] = field(default_factory=list)

    def add(
        self,
        name: str,
        status: str,
        detail: str,
        layer: str,
        command: str | None = None,
        recommendation: str | None = None,
    ) -> None:
        self.checks.append(Check(name, status, detail, layer, command, recommendation))

    @property
    def failed(self) -> bool:
        return any(check.status == "fail" for check in self.checks)

    @property
    def warned(self) -> bool:
        return any(check.status == "warn" for check in self.checks)


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def bool_env(name: str, default: bool = False) -> bool:
    value = env(name)
    if value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def local_url(url: str) -> bool:
    return any(marker in url for marker in LOCAL_HOST_MARKERS)


def run_command(command: list[str], timeout: int) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", f"{command[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def run_command_with_input(command: list[str], text: str, timeout: int) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            input=text,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, "", f"{command[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s"
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def request_json(
    method: str,
    url: str,
    timeout: int,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, Any, str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return response.status, None, ""
            return response.status, json.loads(raw), ""
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, None, body or str(exc)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 0, None, str(exc)


def check_command(report: Report, command: str, args: list[str], timeout: int) -> str | None:
    path = shutil.which(command)
    if not path:
        report.add(
            command,
            "warn",
            f"{command} is not installed or not on PATH",
            "registration/discovery",
            command=f"command -v {command}",
        )
        return None

    code, stdout, stderr = run_command([command, *args], timeout)
    if code == 0:
        first_line = (stdout or stderr).splitlines()[0] if (stdout or stderr) else path
        report.add(
            command,
            "pass",
            first_line[:220],
            "registration/discovery",
            command=" ".join([command, *args]),
        )
    else:
        report.add(
            command,
            "warn",
            (stderr or stdout or f"exit {code}")[:220],
            "registration/discovery",
            command=" ".join([command, *args]),
        )
    return path


def collect_config() -> dict[str, str]:
    return {
        "BRIDGE_MODE": env("BRIDGE_MODE", "demo"),
        "ALLOW_CLOUD": env("ALLOW_CLOUD", "false"),
        "LLM_PROVIDER": env("LLM_PROVIDER", "demo"),
        "LLM_MODEL": env("LLM_MODEL", env("OLLAMA_MODEL", "")),
        "OLLAMA_BASE_URL": env("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL),
        "NIM_BASE_URL": env("NIM_BASE_URL", DEFAULT_NIM_URL),
        "NIM_MODEL": env("NIM_MODEL", ""),
        "EMBEDDING_PROVIDER": env("EMBEDDING_PROVIDER", "local"),
        "EMBEDDING_MODEL": env("EMBEDDING_MODEL", env("OLLAMA_EMBED_MODEL", "bge-m3")),
        "ASR_PROVIDER": env("ASR_PROVIDER", "demo"),
        "TTS_PROVIDER": env("TTS_PROVIDER", "demo"),
        "ELEVENLABS_ACCESS_MODE": env("ELEVENLABS_ACCESS_MODE", "unset"),
        "ELEVENLABS_BASE_URL": env("ELEVENLABS_BASE_URL", ""),
        "WHISPER_MODEL": env("WHISPER_MODEL", "large-v3"),
        "PIPER_VOICE_PATH": env("PIPER_VOICE_PATH", ""),
        "KOKORO_MODEL_PATH": env("KOKORO_MODEL_PATH", ""),
    }


def check_cloud_guard(report: Report, config: dict[str, str], require_offline: bool) -> None:
    allow_cloud = bool_env("ALLOW_CLOUD")
    providers = {
        "ASR_PROVIDER": config["ASR_PROVIDER"],
        "TTS_PROVIDER": config["TTS_PROVIDER"],
        "LLM_PROVIDER": config["LLM_PROVIDER"],
        "EMBEDDING_PROVIDER": config["EMBEDDING_PROVIDER"],
    }
    cloud_selected = [
        f"{name}={value}"
        for name, value in providers.items()
        if value.lower() in CLOUD_PROVIDER_NAMES
    ]
    elevenlabs_mode = config["ELEVENLABS_ACCESS_MODE"].lower()

    if require_offline and allow_cloud:
        report.add(
            "cloud guard",
            "fail",
            "ALLOW_CLOUD must be false for offline validation",
            "registration/discovery",
            command="export ALLOW_CLOUD=false",
        )
    elif allow_cloud:
        report.add(
            "cloud guard",
            "warn",
            "ALLOW_CLOUD=true; do not claim that no data leaves the box",
            "registration/discovery",
        )
    else:
        report.add(
            "cloud guard",
            "pass",
            "ALLOW_CLOUD=false",
            "registration/discovery",
        )

    if cloud_selected and not allow_cloud:
        if elevenlabs_mode in {"on_device", "on-prem", "on_prem", "local"}:
            report.add(
                "cloud provider selection",
                "pass",
                f"{', '.join(cloud_selected)} declared as {elevenlabs_mode}",
                "official activation",
            )
        else:
            report.add(
                "cloud provider selection",
                "fail",
                f"{', '.join(cloud_selected)} selected without ALLOW_CLOUD=true or on-device access",
                "official activation",
                recommendation=(
                    "Set ASR_PROVIDER/TTS_PROVIDER to whisper/piper/kokoro/demo, or confirm "
                    "ELEVENLABS_ACCESS_MODE=on_device. Use cloud ElevenLabs only with "
                    "ALLOW_CLOUD=true and visible labeling."
                ),
            )


def check_hardware(report: Report, timeout: int) -> None:
    report.add(
        "python",
        "pass",
        f"{platform.python_version()} on {platform.machine()} ({platform.system()})",
        "registration/discovery",
        command="python3 --version",
    )
    check_command(report, "uname", ["-m"], timeout)
    check_command(report, "lsb_release", ["-a"], timeout)
    check_command(report, "nvidia-smi", [], timeout)
    check_command(report, "docker", ["--version"], timeout)
    if shutil.which("docker"):
        code, stdout, stderr = run_command(["docker", "info", "--format", "{{json .Runtimes}}"], timeout)
        detail = stdout or stderr or f"exit {code}"
        status = "pass" if code == 0 and ("nvidia" in detail.lower()) else "warn"
        recommendation = None
        if status == "warn":
            recommendation = "Install/activate NVIDIA Container Toolkit before NIM containers."
        report.add(
            "docker nvidia runtime",
            status,
            detail[:220],
            "registration/discovery",
            command='docker info --format "{{json .Runtimes}}"',
            recommendation=recommendation,
        )


def check_ollama(report: Report, config: dict[str, str], timeout: int) -> None:
    provider = config["LLM_PROVIDER"].lower()
    base_url = config["OLLAMA_BASE_URL"].rstrip("/")
    model = config["LLM_MODEL"] or env("OLLAMA_MODEL", "")
    ollama_path = check_command(report, "ollama", ["list"], timeout)

    status, payload, error = request_json("GET", f"{base_url}/api/tags", timeout)
    if status == 200 and isinstance(payload, dict):
        models = [item.get("name", "") for item in payload.get("models", [])]
        detail = ", ".join(models[:8]) if models else "Ollama API reachable; no models installed"
        report.add(
            "ollama api",
            "pass" if models else "warn",
            detail,
            "registration/discovery",
            command=f"curl {base_url}/api/tags",
            recommendation=None
            if models
            else "Run `ollama pull qwen2.5:7b-instruct` or use an already approved local model.",
        )
        if not model and models:
            model = models[0]
    else:
        report.add(
            "ollama api",
            "warn",
            error or f"HTTP {status}",
            "registration/discovery",
            command=f"curl {base_url}/api/tags",
            recommendation="Start Ollama with `ollama serve`, then run `ollama list`.",
        )

    if provider != "ollama":
        report.add(
            "ollama generate",
            "skip",
            f"LLM_PROVIDER={config['LLM_PROVIDER']}",
            "runtime smoke",
        )
        return

    if not ollama_path and status != 200:
        report.add(
            "ollama generate",
            "fail",
            "LLM_PROVIDER=ollama but Ollama is not registered or reachable",
            "official activation",
            recommendation="Install/start Ollama and pull the selected model before runtime debugging.",
        )
        return
    if not model:
        report.add(
            "ollama generate",
            "fail",
            "LLM_PROVIDER=ollama but LLM_MODEL/OLLAMA_MODEL is unset and no installed model was discovered",
            "official activation",
            command="ollama pull qwen2.5:7b-instruct",
        )
        return

    payload = {
        "model": model,
        "prompt": "Translate to English: ami aj raat thakar jayga nei.",
        "stream": False,
        "options": {"num_predict": 24, "temperature": 0},
    }
    status, response, error = request_json("POST", f"{base_url}/api/generate", timeout, payload)
    if status == 200 and isinstance(response, dict) and response.get("response"):
        report.add(
            "ollama generate",
            "pass",
            f"{model}: {response['response'][:160]}",
            "runtime smoke",
            command=f"curl {base_url}/api/generate -d '{{...}}'",
        )
    else:
        report.add(
            "ollama generate",
            "fail",
            error or f"HTTP {status}",
            "runtime smoke",
            recommendation=(
                "Layer order: confirm `ollama list` contains the model, then `ollama run "
                f"{model}` works, then check GPU/runtime performance."
            ),
        )


def check_nim(report: Report, config: dict[str, str], timeout: int) -> None:
    provider = config["LLM_PROVIDER"].lower()
    base_url = config["NIM_BASE_URL"].rstrip("/")
    model = config["NIM_MODEL"] or config["LLM_MODEL"]
    headers: dict[str, str] = {}
    api_key = env("NIM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    docker_path = shutil.which("docker")
    if docker_path:
        code, stdout, stderr = run_command(
            ["docker", "ps", "--format", "{{.Image}} {{.Names}}"], timeout
        )
        detail = stdout or stderr or "no running containers"
        has_nim = "nim" in detail.lower() or "nvcr.io" in detail.lower()
        report.add(
            "nim containers",
            "pass" if has_nim else "warn",
            detail.splitlines()[0][:220] if detail else "no running containers",
            "registration/discovery",
            command='docker ps --format "{{.Image}} {{.Names}}"',
            recommendation=None
            if has_nim
            else "Start a local NIM container from the NVIDIA NIM catalog if NIM is the selected provider.",
        )
    else:
        report.add(
            "nim containers",
            "warn",
            "Docker is not available for local NIM discovery",
            "registration/discovery",
        )

    status, payload, error = request_json("GET", f"{base_url}/models", timeout, headers=headers)
    if status == 200:
        names: list[str] = []
        if isinstance(payload, dict):
            for item in payload.get("data", []):
                names.append(item.get("id", ""))
        report.add(
            "nim models api",
            "pass" if names else "warn",
            ", ".join(names[:8]) if names else "NIM API reachable; no models returned",
            "registration/discovery",
            command=f"curl {base_url}/models",
        )
        if not model and names:
            model = names[0]
    else:
        report.add(
            "nim models api",
            "warn",
            error or f"HTTP {status}",
            "registration/discovery",
            command=f"curl {base_url}/models",
            recommendation=(
                "Follow the NIM catalog activation flow first: authenticate to NGC, pull the "
                "approved model container, start it, then retry `/v1/models`."
            ),
        )

    if provider != "nim":
        report.add("nim chat", "skip", f"LLM_PROVIDER={config['LLM_PROVIDER']}", "runtime smoke")
        return
    if not local_url(base_url) and not bool_env("ALLOW_CLOUD"):
        report.add(
            "nim chat",
            "fail",
            f"NIM_BASE_URL={base_url} is not local and ALLOW_CLOUD=false",
            "official activation",
        )
        return
    if not model:
        report.add(
            "nim chat",
            "fail",
            "LLM_PROVIDER=nim but NIM_MODEL/LLM_MODEL is unset and no model was discovered",
            "official activation",
        )
        return

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Reply with one short English sentence: local public service assistant.",
            }
        ],
        "max_tokens": 24,
        "temperature": 0,
    }
    status, response, error = request_json(
        "POST", f"{base_url}/chat/completions", timeout, payload, headers
    )
    choices = response.get("choices", []) if isinstance(response, dict) else []
    if status == 200 and choices:
        content = choices[0].get("message", {}).get("content", "")
        report.add(
            "nim chat",
            "pass",
            f"{model}: {content[:160]}",
            "runtime smoke",
            command=f"curl {base_url}/chat/completions -d '{{...}}'",
        )
    else:
        report.add(
            "nim chat",
            "fail",
            error or f"HTTP {status}",
            "runtime smoke",
            recommendation="Check model registration with `/v1/models` before debugging container logs.",
        )


def check_embeddings(report: Report, config: dict[str, str], timeout: int) -> None:
    provider = config["EMBEDDING_PROVIDER"].lower()
    model = config["EMBEDDING_MODEL"]
    if provider in {"none", "disabled"}:
        report.add("embeddings", "skip", f"EMBEDDING_PROVIDER={provider}", "runtime smoke")
        return
    if provider == "ollama":
        base_url = config["OLLAMA_BASE_URL"].rstrip("/")
        status, response, error = request_json(
            "POST",
            f"{base_url}/api/embed",
            timeout,
            {"model": model, "input": "homelessness appointment and interpreter"},
        )
        embeddings = response.get("embeddings", []) if isinstance(response, dict) else []
        if status == 200 and embeddings and isinstance(embeddings[0], list):
            report.add(
                "ollama embeddings",
                "pass",
                f"{model}: dimension {len(embeddings[0])}",
                "runtime smoke",
                command=f"curl {base_url}/api/embed -d '{{...}}'",
            )
        else:
            report.add(
                "ollama embeddings",
                "fail",
                error or f"HTTP {status}",
                "runtime smoke",
                recommendation=f"Confirm `ollama list` includes {model}, then pull/register it.",
            )
        return
    if provider in {"local", "sentence-transformers", "sentence_transformers"}:
        code, stdout, stderr = run_command(
            [
                sys.executable,
                "-c",
                "import sentence_transformers; print(sentence_transformers.__version__)",
            ],
            timeout,
        )
        if code == 0:
            report.add(
                "sentence-transformers",
                "pass",
                f"installed {stdout}",
                "registration/discovery",
                command="python3 -c 'import sentence_transformers'",
            )
            report.add(
                "local embeddings",
                "warn",
                f"Model load not attempted by default; set EMBEDDING_MODEL={model} and run app ingest smoke.",
                "runtime smoke",
            )
        else:
            report.add(
                "sentence-transformers",
                "warn",
                stderr or stdout or "not installed",
                "registration/discovery",
                recommendation=(
                    "Use Ollama embeddings if available, or install sentence-transformers "
                    "only after confirming ARM64 wheel support."
                ),
            )
        return
    report.add(
        "embeddings",
        "fail",
        f"Unknown EMBEDDING_PROVIDER={provider}",
        "registration/discovery",
    )


def check_asr(report: Report, config: dict[str, str], timeout: int) -> None:
    provider = config["ASR_PROVIDER"].lower()
    if provider == "demo":
        report.add(
            "asr fallback",
            "pass",
            "Demo transcripts are selected and offline-safe",
            "runtime smoke",
        )
        return
    if provider == "whisper":
        faster_code, faster_out, faster_err = run_command(
            [sys.executable, "-c", "import faster_whisper; print('faster-whisper')"], timeout
        )
        whisper_path = shutil.which("whisper")
        if faster_code == 0:
            detail = f"{faster_out}; WHISPER_MODEL={config['WHISPER_MODEL']}"
            report.add("local whisper", "pass", detail, "registration/discovery")
        elif whisper_path:
            report.add(
                "local whisper",
                "pass",
                f"whisper CLI at {whisper_path}; WHISPER_MODEL={config['WHISPER_MODEL']}",
                "registration/discovery",
                command="command -v whisper",
            )
        else:
            report.add(
                "local whisper",
                "fail",
                faster_err or "faster-whisper module and whisper CLI are missing",
                "registration/discovery",
                recommendation=(
                    "Install/activate faster-whisper or openai-whisper after confirming the "
                    "Python/ARM64 environment. Use ASR_PROVIDER=demo until then."
                ),
            )
        return
    if provider == "elevenlabs":
        check_elevenlabs(report, config, timeout, capability="asr")
        return
    if provider == "browser":
        status = "fail" if not bool_env("ALLOW_CLOUD") else "warn"
        report.add(
            "browser asr",
            status,
            "Browser speech recognition is not an offline proof path",
            "official activation",
            recommendation="Use ASR_PROVIDER=whisper or demo for offline validation.",
        )
        return
    report.add("asr provider", "fail", f"Unknown ASR_PROVIDER={provider}", "registration/discovery")


def check_tts(report: Report, config: dict[str, str], timeout: int, audio_smoke: bool) -> None:
    provider = config["TTS_PROVIDER"].lower()
    if provider == "demo":
        report.add("tts fallback", "pass", "Demo audio/text is selected and offline-safe", "runtime smoke")
        return
    if provider == "piper":
        piper_path = shutil.which("piper")
        voice_path = config["PIPER_VOICE_PATH"]
        if not piper_path:
            report.add(
                "piper",
                "fail",
                "piper command is missing",
                "registration/discovery",
                command="command -v piper",
                recommendation="Install Piper or switch to TTS_PROVIDER=kokoro/demo.",
            )
            return
        if not voice_path or not Path(voice_path).exists():
            report.add(
                "piper voice",
                "fail",
                "PIPER_VOICE_PATH is unset or does not exist",
                "registration/discovery",
                command="export PIPER_VOICE_PATH=/path/to/voice.onnx",
            )
            return
        if not audio_smoke:
            report.add(
                "piper",
                "pass",
                f"{piper_path}; voice={voice_path}",
                "registration/discovery",
                command="piper --help",
            )
            return
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as output:
            code, stdout, stderr = run_command_with_input(
                [
                    "piper",
                    "--model",
                    voice_path,
                    "--output_file",
                    output.name,
                ],
                "Bridge offline speech check.",
                timeout,
            )
            has_audio = output.tell() > 0 or Path(output.name).stat().st_size > 0
            detail = stdout or stderr or f"wav bytes={Path(output.name).stat().st_size}"
        report.add(
            "piper smoke",
            "pass" if code == 0 and has_audio else "fail",
            detail[:220],
            "runtime smoke",
            recommendation="Confirm PIPER_VOICE_PATH points to a compatible local voice model.",
        )
        return
    if provider == "kokoro":
        code, stdout, stderr = run_command(
            [sys.executable, "-c", "import kokoro; print('kokoro')"], timeout
        )
        if code == 0:
            report.add(
                "kokoro",
                "pass",
                f"{stdout}; KOKORO_MODEL_PATH={config['KOKORO_MODEL_PATH'] or 'unset'}",
                "registration/discovery",
            )
        else:
            report.add(
                "kokoro",
                "fail",
                stderr or stdout or "kokoro module is missing",
                "registration/discovery",
                recommendation="Use Piper if installed, or TTS_PROVIDER=demo for offline validation.",
            )
        return
    if provider == "elevenlabs":
        check_elevenlabs(report, config, timeout, capability="tts")
        return
    if provider == "browser":
        report.add(
            "browser tts",
            "warn",
            "Browser speech synthesis can work without provider keys but is not a robust offline proof",
            "official activation",
            recommendation="Use TTS_PROVIDER=piper/kokoro/demo for the judged offline path.",
        )
        return
    report.add("tts provider", "fail", f"Unknown TTS_PROVIDER={provider}", "registration/discovery")


def check_elevenlabs(
    report: Report, config: dict[str, str], timeout: int, capability: str
) -> None:
    access_mode = config["ELEVENLABS_ACCESS_MODE"].lower()
    base_url = config["ELEVENLABS_BASE_URL"]
    allow_cloud = bool_env("ALLOW_CLOUD")

    if access_mode in {"on_device", "on-prem", "on_prem", "local"}:
        if not base_url:
            report.add(
                f"elevenlabs {capability}",
                "warn",
                "on-device access declared but ELEVENLABS_BASE_URL is unset",
                "official activation",
                recommendation=(
                    "Get the official local endpoint/container details from ElevenLabs reps, "
                    "then set ELEVENLABS_BASE_URL."
                ),
            )
            return
        if not local_url(base_url):
            report.add(
                f"elevenlabs {capability}",
                "fail",
                f"on-device access declared but ELEVENLABS_BASE_URL is not local: {base_url}",
                "official activation",
            )
            return
        status, _, error = request_json("GET", base_url.rstrip("/") + "/health", timeout)
        report.add(
            f"elevenlabs {capability}",
            "pass" if status == 200 else "warn",
            "local endpoint health OK" if status == 200 else error or f"HTTP {status}",
            "registration/discovery",
            command=f"curl {base_url.rstrip()}/health",
        )
        return

    if access_mode == "cloud":
        report.add(
            f"elevenlabs {capability}",
            "warn" if allow_cloud else "fail",
            "cloud API selected; requires visible cloud label and ALLOW_CLOUD=true",
            "official activation",
            recommendation=(
                "For offline proof, use Whisper/Piper/Kokoro/demo. For sponsor mode, set "
                "ALLOW_CLOUD=true and ELEVENLABS_API_KEY, and enable zero-retention/EU residency "
                "if available."
            ),
        )
        return

    report.add(
        f"elevenlabs {capability}",
        "fail",
        "ElevenLabs selected but access mode is unset/unknown",
        "official activation",
        command="export ELEVENLABS_ACCESS_MODE=on_device|cloud|none",
    )


def print_text(report: Report) -> None:
    print("Bridge model/runtime smoke report")
    print(f"Started: {report.started_at}")
    print("")
    print("Config:")
    for key, value in report.config.items():
        redacted = "***" if "KEY" in key or "TOKEN" in key else value
        print(f"  {key}={redacted}")
    print("")
    last_layer = ""
    for check in report.checks:
        if check.layer != last_layer:
            print(f"{check.layer}:")
            last_layer = check.layer
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "skip": "SKIP"}[check.status]
        print(f"  [{marker}] {check.name}: {check.detail}")
        if check.command:
            print(f"         command: {check.command}")
        if check.recommendation:
            print(f"         next: {check.recommendation}")
    print("")
    if report.failed:
        print("Result: FAIL")
    elif report.warned:
        print("Result: WARN")
    else:
        print("Result: PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on failures")
    parser.add_argument(
        "--require-offline",
        action="store_true",
        help="fail if ALLOW_CLOUD or selected providers violate offline proof rules",
    )
    parser.add_argument("--timeout", type=int, default=12, help="seconds per command/API probe")
    parser.add_argument(
        "--audio-smoke",
        action="store_true",
        help="attempt provider-specific audio generation smoke checks when configured",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = collect_config()
    report = Report(started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), config=config)

    check_cloud_guard(report, config, args.require_offline)
    check_hardware(report, args.timeout)
    check_ollama(report, config, args.timeout)
    check_nim(report, config, args.timeout)
    check_embeddings(report, config, args.timeout)
    check_asr(report, config, args.timeout)
    check_tts(report, config, args.timeout, args.audio_smoke)

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print_text(report)

    if args.strict and report.failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
