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
