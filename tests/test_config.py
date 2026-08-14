"""Tests for configuration loading and normalization."""

import pytest

from applyr.config import load_config, create_default_config, _normalize_weights, _deep_merge


@pytest.mark.unit
class TestNormalizeWeights:

    def test_integers_normalize_to_decimals(self):
        weights = {"a": 30, "b": 20, "c": 50}
        result = _normalize_weights(weights)
        assert result == {"a": 0.3, "b": 0.2, "c": 0.5}

    def test_zero_total_returns_unchanged(self):
        weights = {"a": 0, "b": 0}
        assert _normalize_weights(weights) == {"a": 0, "b": 0}

    def test_already_decimal(self):
        weights = {"a": 0.5, "b": 0.5}
        result = _normalize_weights(weights)
        assert abs(result["a"] - 0.5) < 0.001
        assert abs(result["b"] - 0.5) < 0.001

    def test_single_weight(self):
        result = _normalize_weights({"only": 42})
        assert abs(result["only"] - 1.0) < 0.001


@pytest.mark.unit
class TestDeepMerge:

    def test_flat_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        assert _deep_merge(base, override) == {"a": 1, "b": 99}

    def test_nested_merge(self):
        base = {"general": {"threshold": 65, "followup_days": 10}}
        override = {"general": {"threshold": 80}}
        result = _deep_merge(base, override)
        assert result["general"]["threshold"] == 80
        assert result["general"]["followup_days"] == 10

    def test_new_key_added(self):
        base = {"a": 1}
        override = {"b": 2}
        assert _deep_merge(base, override) == {"a": 1, "b": 2}

    def test_base_unchanged(self):
        base = {"a": 1}
        _deep_merge(base, {"a": 2})
        assert base["a"] == 1


@pytest.mark.unit
class TestLoadConfig:

    def test_defaults_without_toml(self, tmp_applyr):
        config = load_config()
        assert config["general"]["threshold"] == 65
        assert config["general"]["followup_days"] == 10
        assert "tech_stack" in config["weights"]

    def test_weights_are_normalized(self, tmp_applyr):
        config = load_config()
        total = sum(config["weights"].values())
        assert abs(total - 1.0) < 0.001

    def test_custom_threshold(self, tmp_applyr):
        toml_content = b'[general]\nthreshold = 80\n'
        (tmp_applyr / "applyr.toml").write_bytes(toml_content)
        config = load_config()
        assert config["general"]["threshold"] == 80
        # followup_days should still be default
        assert config["general"]["followup_days"] == 10

    def test_legacy_threshold_only_derives_apply_and_maybe(self, tmp_applyr):
        """A config that sets ONLY the legacy `threshold` key must still drive
        threshold_apply/threshold_maybe.

        Regression test: _build_defaults() always populates threshold_apply/
        threshold_maybe (80/60), so after _deep_merge a legacy-only file never
        looked "incomplete" — the derivation branch checked the merged dict
        and never fired, silently ignoring the user's custom threshold in
        favor of the defaults. See config.py's load_config() for the fix
        (checks the raw user config instead of the merged one).
        """
        (tmp_applyr / "applyr.toml").write_text("[general]\nthreshold = 50\n")
        config = load_config()
        assert config["general"]["threshold_apply"] == 50
        assert config["general"]["threshold_maybe"] == 30

    def test_explicit_threshold_apply_ignores_legacy_threshold(self, tmp_applyr):
        """When threshold_apply is set explicitly, it wins over legacy `threshold`
        even if both are present (e.g. an old file edited to add the new keys)."""
        (tmp_applyr / "applyr.toml").write_text(
            "[general]\nthreshold = 50\nthreshold_apply = 90\n"
        )
        config = load_config()
        assert config["general"]["threshold_apply"] == 90
        # threshold_maybe wasn't set either — derives from threshold_apply, not legacy threshold
        assert config["general"]["threshold_maybe"] == 70

    def test_custom_weights_override(self, tmp_applyr):
        # deep_merge keeps all 6 default weights, overriding only specified ones
        toml_content = b'[weights]\ntech_stack = 50\neducation = 50\n'
        (tmp_applyr / "applyr.toml").write_bytes(toml_content)
        config = load_config()
        # tech_stack (50) should be greater than education default (15) after normalize
        assert config["weights"]["tech_stack"] > config["weights"]["english"]

    def test_corrupt_toml_falls_back(self, tmp_applyr, capsys):
        (tmp_applyr / "applyr.toml").write_text("not valid {{ toml")
        config = load_config()
        assert config["general"]["threshold"] == 65
        captured = capsys.readouterr()
        assert "Warning" in captured.out


@pytest.mark.unit
class TestCreateDefaultConfig:

    def test_creates_toml_and_cv_dir(self, tmp_applyr, capsys):
        create_default_config()
        assert (tmp_applyr / "applyr.toml").exists()
        assert (tmp_applyr / "cv").is_dir()

    def test_does_not_overwrite(self, tmp_applyr, capsys):
        (tmp_applyr / "applyr.toml").write_text("custom")
        create_default_config()
        assert (tmp_applyr / "applyr.toml").read_text() == "custom"


@pytest.mark.unit
class TestCvOutputDirLocation:
    """Generated CVs are a deliverable the user has to find and attach
    elsewhere, unlike the config/db/cv-master.md — they must default outside
    the applyr config directory so a normal file browser shows them."""

    def test_default_output_dir_follows_cv_home_not_applyr_dir(self, tmp_applyr, monkeypatch, tmp_path):
        import applyr.config as cfg

        other_dir = tmp_path / "elsewhere"
        monkeypatch.setattr(cfg, "CV_HOME", other_dir)

        config = load_config()
        assert config["cv"]["output_dir"] == str(other_dir / "cv")
        assert not config["cv"]["output_dir"].startswith(str(tmp_applyr))

    def test_written_toml_points_at_cv_home(self, tmp_applyr, monkeypatch, tmp_path):
        import applyr.config as cfg

        other_dir = tmp_path / "elsewhere"
        monkeypatch.setattr(cfg, "CV_HOME", other_dir)

        create_default_config()
        toml_text = (tmp_applyr / "applyr.toml").read_text()
        assert str(other_dir / "cv") in toml_text
        assert (other_dir / "cv").is_dir()
