"""Autopilot parameters: expected values, write/read-back, unknown names (TC-070..TC-072)."""

import pytest

from sitl.params import EXPECTED_SAFETY_PARAMS
from utils.commands import get_param

pytestmark = pytest.mark.sitl


class TestParameters:
    """Parameter protocol and safety-relevant parameter values."""

    def test_param_write_read_back(self, vehicle, param_changer):
        """TC-071: written parameter value is read back unchanged."""
        param = "DISARM_DELAY"
        param_changer(param, 5)

        value = get_param(vehicle, param)
        assert value == pytest.approx(5), f"{param} after write: expected 5, got {value}"

    @pytest.mark.parametrize("param, expected", list(EXPECTED_SAFETY_PARAMS.items()))
    def test_safety_params(self, vehicle, param, expected):
        """TC-070: safety-relevant parameters have their expected values."""
        value = get_param(vehicle, param)
        assert value == pytest.approx(expected), f"{param}: expected {expected}, got {value}"

    def test_param_unknown_name(self, vehicle):
        """TC-072: request for a non-existent parameter gets no answer."""
        with pytest.raises(TimeoutError, match="PARAM_UNKNOWN"):
            get_param(vehicle, "PARAM_UNKNOWN", timeout=3)
