from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _extract(path: str, pattern: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(pattern, text)
    assert match is not None, f"Version marker not found in {path}"
    return match.group(1)


def test_release_version_markers_are_consistent() -> None:
    versions = {
        "addon_config": _extract(
            "sigenergy_optimizer_addon/config.yaml",
            r'(?m)^version:\s*"([^"]+)"\s*$',
        ),
        "addon_build": _extract(
            "sigenergy_optimizer_addon/build.yaml",
            r'(?m)^\s*io\.hass\.version:\s*"([^"]+)"\s*$',
        ),
        "build_stamp": (
            ROOT / "sigenergy_optimizer_addon/buildstamp.txt"
        ).read_text(encoding="utf-8").strip(),
        "runtime_signature": _extract(
            "app/optimizer.py",
            r'(?m)^_RUNTIME_SIGNATURE\s*=\s*"([^"]+)"\s*$',
        ),
        "api_version": _extract(
            "app/main.py",
            r'(?m)^\s*version="([^"]+)",\s*$',
        ),
    }

    assert len(set(versions.values())) == 1, versions

    release_version = next(iter(versions.values()))
    assert re.fullmatch(r"\d+\.\d+\.\d+-haos\d+", release_version)


def test_build_stamp_invalidates_source_clone_layer() -> None:
    dockerfile = (
        ROOT / "sigenergy_optimizer_addon/Dockerfile"
    ).read_text(encoding="utf-8")

    assert "COPY buildstamp.txt /tmp/buildstamp.txt" in dockerfile
    assert 'Build stamp: $(cat /tmp/buildstamp.txt)' in dockerfile
    assert dockerfile.index("COPY buildstamp.txt") < dockerfile.index("git clone")
