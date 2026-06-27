from core.stop_detector import StopDetector


def make_col_map(headers):
    return {chr(65 + i): i for i in range(len(headers))}


def test_cell_match_stops_on_pattern():
    rules = [
        {"type": "cell_match", "patterns": ["^注：", "^说明："], "columns": ["A"]},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A", "B"])

    assert detector.check(["注：这是注释", "data"], col_map) == "stop"
    assert detector.check(["说明：xxx", "data"], col_map) == "stop"
    assert detector.check(["正常数据", "data"], col_map) == "continue"


def test_consecutive_empty_rows():
    rules = [
        {"type": "consecutive_empty_rows", "count": 3},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A", "B"])

    assert detector.check([None, None], col_map) == "continue"
    assert detector.consecutive_empty == 1
    assert detector.check(["", ""], col_map) == "continue"
    assert detector.consecutive_empty == 2
    assert detector.check([None, ""], col_map) == "stop"


def test_consecutive_empty_resets_on_data():
    rules = [
        {"type": "consecutive_empty_rows", "count": 3},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A"])

    assert detector.check([None], col_map) == "continue"
    assert detector.check(["data"], col_map) == "continue"
    assert detector.consecutive_empty == 0


def test_mixed_rules():
    rules = [
        {"type": "cell_match", "patterns": ["^注："], "columns": ["A"]},
        {"type": "consecutive_empty_rows", "count": 2},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A"])

    assert detector.check(["注：xx"], col_map) == "stop"


def test_last_action_extracts_then_stops():
    rules = [
        {"type": "cell_match", "patterns": ["^合计"], "columns": ["A"], "action": "last"},
    ]
    detector = StopDetector(rules)
    col_map = make_col_map(["A"])

    assert detector.check(["合计", "100"], col_map) == "last"
    assert detector.check(["正常数据", "200"], col_map) == "continue"
