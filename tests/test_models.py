"""Tests for xiswalker.models — JSONL serialization pure functions."""

import json
import pytest
from xiswalker.models import InputEvent, serialize_event, deserialize_event


class TestSerializeEvent:
    """Test serialize_event produces valid JSON with correct fields."""

    def test_key_press_event(self) -> None:
        event = InputEvent(type="key_press", timestamp=1.234, key="a")
        result = serialize_event(event)
        data = json.loads(result)
        assert data["type"] == "key_press"
        assert data["timestamp"] == 1.234
        assert data["key"] == "a"
        assert "x" not in data
        assert "y" not in data
        assert "button" not in data

    def test_key_release_event(self) -> None:
        event = InputEvent(type="key_release", timestamp=2.5, key="shift")
        result = serialize_event(event)
        data = json.loads(result)
        assert data["type"] == "key_release"
        assert data["key"] == "shift"

    def test_mouse_click_event(self) -> None:
        event = InputEvent(
            type="mouse_click", timestamp=3.0, x=100, y=200, button="left"
        )
        result = serialize_event(event)
        data = json.loads(result)
        assert data["type"] == "mouse_click"
        assert data["x"] == 100
        assert data["y"] == 200
        assert data["button"] == "left"
        assert "key" not in data

    def test_mouse_drag_events(self) -> None:
        press_event = InputEvent(
            type="mouse_press", timestamp=4.0, x=100, y=200, button="left"
        )
        move_event = InputEvent(
            type="mouse_move", timestamp=4.1, x=150, y=250
        )
        release_event = InputEvent(
            type="mouse_release", timestamp=4.2, x=150, y=250, button="left"
        )

        p_data = json.loads(serialize_event(press_event))
        assert p_data["type"] == "mouse_press"
        assert p_data["button"] == "left"

        m_data = json.loads(serialize_event(move_event))
        assert m_data["type"] == "mouse_move"
        assert m_data["x"] == 150
        assert m_data["y"] == 250
        assert "button" not in m_data

        r_data = json.loads(serialize_event(release_event))
        assert r_data["type"] == "mouse_release"
        assert r_data["button"] == "left"

    def test_none_fields_omitted(self) -> None:
        """None-valued optional fields should not appear in output."""
        event = InputEvent(type="key_press", timestamp=0.0, key="b")
        result = serialize_event(event)
        data = json.loads(result)
        assert set(data.keys()) == {"type", "timestamp", "key"}


class TestDeserializeEvent:
    """Test deserialize_event parses JSON lines back to InputEvent."""

    def test_round_trip_key_event(self) -> None:
        original = InputEvent(type="key_press", timestamp=1.0, key="w")
        line = serialize_event(original)
        restored = deserialize_event(line)
        assert restored.type == original.type
        assert restored.timestamp == original.timestamp
        assert restored.key == original.key
        assert restored.x is None
        assert restored.y is None

    def test_round_trip_mouse_click_event(self) -> None:
        original = InputEvent(
            type="mouse_click", timestamp=5.5, x=300, y=450, button="right"
        )
        line = serialize_event(original)
        restored = deserialize_event(line)
        assert restored.type == original.type
        assert restored.timestamp == original.timestamp
        assert restored.x == original.x
        assert restored.y == original.y
        assert restored.button == original.button
        assert restored.key is None

    def test_round_trip_mouse_drag_events(self) -> None:
        original_press = InputEvent(
            type="mouse_press", timestamp=6.0, x=100, y=100, button="left"
        )
        original_move = InputEvent(
            type="mouse_move", timestamp=6.1, x=150, y=150
        )
        
        restored_press = deserialize_event(serialize_event(original_press))
        assert restored_press.type == "mouse_press"
        assert restored_press.button == "left"
        
        restored_move = deserialize_event(serialize_event(original_move))
        assert restored_move.type == "mouse_move"
        assert restored_move.x == 150
        assert restored_move.button is None

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            deserialize_event("not valid json")

    def test_missing_required_field_raises(self) -> None:
        with pytest.raises(TypeError):
            deserialize_event('{"type": "key_press"}')


class TestCompositeModels:
    """Test CompositeMission, CompositeStep and parse_composite_yaml."""

    def test_parse_composite_yaml_valid(self, tmp_path) -> None:
        from xiswalker.models import parse_composite_yaml
        import yaml
        
        test_file = tmp_path / "test_mission.yaml"
        data = {
            "name": "test_evening_farm",
            "description": "Farming mission",
            "grace_period": 3,
            "steps": [
                {"mission": "mount_up", "atomic": True, "retries": 1},
                {"wait": 5.0},
                {"mission": "attack", "on_fail": "skip"}
            ]
        }
        with open(test_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f)
            
        mission = parse_composite_yaml(test_file)
        
        assert mission.name == "test_evening_farm"
        assert mission.description == "Farming mission"
        assert mission.grace_period == 3
        assert len(mission.steps) == 3
        
        assert mission.steps[0].mission == "mount_up"
        assert mission.steps[0].atomic is True
        assert mission.steps[0].retries == 1
        assert mission.steps[0].on_fail == "abort"  # default
        
        assert mission.steps[1].wait == 5.0
        assert mission.steps[1].mission is None
        
        assert mission.steps[2].mission == "attack"
        assert mission.steps[2].on_fail == "skip"

    def test_parse_empty_yaml_raises(self, tmp_path) -> None:
        from xiswalker.models import parse_composite_yaml
        test_file = tmp_path / "empty.yaml"
        test_file.write_text("")
        
        with pytest.raises(ValueError, match="Empty or invalid"):
            parse_composite_yaml(str(test_file))
