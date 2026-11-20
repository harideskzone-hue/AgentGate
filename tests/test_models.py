import pytest
from pydantic import ValidationError

from agentgate.models import Scenario


def test_valid_scenario():
    scenario = Scenario(
        id="t1",
        type="benign",
        goal="Resolve ticket number 42",
    )
    assert scenario.max_steps == 10


@pytest.mark.parametrize("bad_steps", [0, 51, -3])
def test_max_steps_out_of_range(bad_steps):
    with pytest.raises(ValidationError):
        Scenario(
            id="t1",
            type="benign",
            goal="Resolve ticket number 42",
            max_steps=bad_steps,
        )
