"""Environment and package sanity tests.

These verify that the uv development environment is correctly configured
and the hermes_bacmap package is importable — the foundation everything
else builds on.
"""
import sys


def test_python_version():
    """Development environment must use Python 3.11 (same as Hermes)."""
    assert sys.version_info >= (3, 11), f"Need >=3.11, got {sys.version}"
    assert sys.version_info < (3, 14), f"Need <3.14, got {sys.version}"


def test_biopython_importable():
    """Biopython must be available — it's the core runtime dependency."""
    import Bio
    assert Bio.__version__


def test_package_importable():
    """The hermes_bacmap package must be importable (editable install works)."""
    import hermes_bacmap
    assert hasattr(hermes_bacmap, "__doc__")


def test_pyproject_config():
    """pyproject.toml must declare correct requires-python."""
    from pathlib import Path
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    text = pyproject.read_text()
    assert 'requires-python = ">=3.12,<3.14"' in text
    assert "biopython" in text


def test_pixi_config():
    """pixi.toml must declare the bioconda channel and key CLI tools."""
    from pathlib import Path
    pixi = Path(__file__).resolve().parents[1] / "pixi.toml"
    text = pixi.read_text()
    assert "bioconda" in text
    for tool in ["samtools", "bwa", "minimap2", "bcftools"]:
        assert tool in text, f"{tool} missing from pixi.toml"
