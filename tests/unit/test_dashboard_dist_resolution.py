"""Tests for resolve_dashboard_dist() when an explicit WebUI directory is used."""

import logging

import pytest

from astrbot.core import logger
from astrbot.core.config.default import VERSION
from astrbot.core.dashboard_assets import resolve_dashboard_dist

WARNING_FRAGMENT = "does not declare a version matching core"


def _make_dist(root, version: str | None) -> str:
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    if version is not None:
        (assets / "version").write_text(version, encoding="utf-8")
    return str(root)


class TestExplicitWebuiDir:
    def test_matching_version_is_served_quietly(self, tmp_path, caplog):
        """The happy path must not add startup noise."""
        dist = _make_dist(tmp_path / "webui", f"v{VERSION}")

        logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.WARNING):
                resolved = resolve_dashboard_dist(dist)
        finally:
            logger.removeHandler(caplog.handler)

        assert resolved is not None
        assert str(resolved) == str(tmp_path / "webui")
        assert WARNING_FRAGMENT not in caplog.text

    def test_mismatched_version_warns_but_is_still_served(self, tmp_path, caplog):
        """A stale packaged WebUI must not be swapped in silently."""
        dist = _make_dist(tmp_path / "webui", "v0.0.1")

        logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.WARNING):
                resolved = resolve_dashboard_dist(dist)
        finally:
            logger.removeHandler(caplog.handler)

        assert resolved is not None  # behaviour unchanged: still served
        assert WARNING_FRAGMENT in caplog.text
        assert "v0.0.1" in caplog.text
        assert VERSION in caplog.text

    def test_missing_version_marker_warns_as_unknown(self, tmp_path, caplog):
        """Assets without a version marker cannot be verified, so say so."""
        dist = _make_dist(tmp_path / "webui", None)

        logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.WARNING):
                resolved = resolve_dashboard_dist(dist)
        finally:
            logger.removeHandler(caplog.handler)

        assert resolved is not None
        assert WARNING_FRAGMENT in caplog.text
        assert "unknown" in caplog.text

    def test_nonexistent_dir_falls_through(self, tmp_path, caplog):
        """A path that does not exist must not be reported as a stale dist."""
        logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.WARNING):
                resolve_dashboard_dist(str(tmp_path / "does-not-exist"))
        finally:
            logger.removeHandler(caplog.handler)

        assert WARNING_FRAGMENT not in caplog.text

    @pytest.mark.parametrize("empty", ["", None])
    def test_no_explicit_dir_falls_through(self, empty, caplog):
        """Without --webui-dir the managed/bundled resolution path is used."""
        logger.addHandler(caplog.handler)
        try:
            with caplog.at_level(logging.WARNING):
                resolve_dashboard_dist(empty)
        finally:
            logger.removeHandler(caplog.handler)

        assert WARNING_FRAGMENT not in caplog.text
