import pytest

from app.core.ids import generate_id


def test_generate_id_has_correct_prefix():
    assert generate_id("creator").startswith("cr_")
    assert generate_id("content_item").startswith("cnt_")
    assert generate_id("opportunity").startswith("opp_")


def test_generate_id_is_unique():
    ids = {generate_id("creator") for _ in range(1000)}
    assert len(ids) == 1000


def test_generate_id_unknown_entity_raises():
    with pytest.raises(ValueError):
        generate_id("not_a_real_entity")
