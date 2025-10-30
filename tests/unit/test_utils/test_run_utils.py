def test_merge_jsonb_and_should_skip_event():
    # Import inside test to ensure package import resolution in test env
    from agent_server.utils.run_utils import _merge_jsonb, _should_skip_event

    # _merge_jsonb should merge dicts and ignore None
    a = {"x": 1, "y": {"a": 2}}
    b = {"y": {"b": 3}, "z": 4}
    merged = _merge_jsonb(a, None, b)
    assert merged["x"] == 1
    assert merged["z"] == 4
    # b should override a for top-level keys
    assert merged["y"] == {"b": 3}

    # _should_skip_event: tuple with last element being (something, metadata_dict)
    raw_event = ("values", {"foo": "bar"}, ("meta", {"tags": ["langsmith:nostream"]}))
    assert _should_skip_event(raw_event) is True

    # Other shapes should not be skipped
    assert _should_skip_event(("values", {"foo": "bar"})) is False
    assert _should_skip_event("just-a-string") is False
