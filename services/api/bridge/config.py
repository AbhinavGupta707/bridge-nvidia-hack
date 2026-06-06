import os
from dataclasses import dataclass
from pathlib import Path

from bridge.bus.events import BridgeMode


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _default_data_dir() -> Path:
    configured = os.getenv("BRIDGE_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    module_path = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "data",
        Path.cwd().parent / "data",
        Path.cwd().parent.parent / "data",
        module_path.parents[3] / "data",
        module_path.parents[1] / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / "data").resolve()


@dataclass(frozen=True)
class BridgeSettings:
    mode: BridgeMode
    asr_provider: str
    tts_provider: str
    llm_provider: str
    rag_provider: str
    allow_cloud: bool
    data_dir: Path
    demo_scenario: str
    demo_step_ms: int
    record_output_dir: Path

    @property
    def deterministic_demo(self) -> bool:
        return (
            self.mode == "demo"
            and self.asr_provider == "demo"
            and self.tts_provider == "demo"
            and self.llm_provider == "demo"
            and not self.allow_cloud
        )


def load_settings() -> BridgeSettings:
    data_dir = _default_data_dir()
    record_output_dir = os.getenv("BRIDGE_RECORD_OUTPUT_DIR")
    return BridgeSettings(
        mode=os.getenv("BRIDGE_MODE", "demo"),  # type: ignore[arg-type]
        asr_provider=os.getenv("ASR_PROVIDER", "demo"),
        tts_provider=os.getenv("TTS_PROVIDER", "demo"),
        llm_provider=os.getenv("LLM_PROVIDER", "demo"),
        rag_provider=os.getenv("RAG_PROVIDER", "local"),
        allow_cloud=_env_bool("ALLOW_CLOUD", False),
        data_dir=data_dir,
        demo_scenario=os.getenv("BRIDGE_DEMO_SCENARIO", "fixtures/demo_scenario.json"),
        demo_step_ms=max(0, _env_int("BRIDGE_DEMO_STEP_MS", 250)),
        record_output_dir=(
            Path(record_output_dir).expanduser().resolve()
            if record_output_dir
            else Path("/tmp/bridge-records/generated")
        ),
    )
