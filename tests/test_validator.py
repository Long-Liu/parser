from core.validator import validate


def make_columns():
    return [
        {"db_field": "name", "type": "varchar(100)", "match_header": ["姓名"]},
        {"db_field": "amount", "type": "decimal(10,2)", "match_header": ["金额"]},
    ]


def test_validate_passes_clean_data():
    rows = [
        {"name": "张三", "amount": 100.50},
        {"name": "李四", "amount": 200.00},
    ]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 2
    assert len(errors) == 0


def test_validate_casts_string_to_decimal():
    rows = [{"name": "张三", "amount": "150.75"}]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 1
    assert valid[0]["amount"] == 150.75


def test_validate_sets_none_for_invalid_decimal():
    rows = [{"name": "张三", "amount": "not_a_number"}]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 1
    assert valid[0]["amount"] is None


def test_validate_records_error():
    rows = [
        {"name": "张三", "amount": "bad"},
        {"name": "李四", "amount": 200},
    ]
    valid, errors = validate(rows, make_columns())
    assert len(valid) == 2
    assert len(errors) == 1
    assert errors[0]["row_index"] == 0
    assert "amount" in errors[0]["field"]
