from spatialscope.utils.json_utils import extract_json_object


def test_extract_plain_json_object():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extract_fenced_json_object():
    assert extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_embedded_json_object():
    assert extract_json_object('Here is the result: {"a": 1}') == {"a": 1}

