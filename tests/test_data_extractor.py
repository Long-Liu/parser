from core.data_extractor import extract_rows


def make_config():
    return {
        "headers": {"data_start_row": 2},
        "hierarchy": {"column_name": "序号", "separator": "."},
        "columns": [
            {"db_field": "person_name", "match_header": ["姓名"], "type": "varchar(100)"},
            {"db_field": "dept", "match_header": ["部门"], "type": "varchar(100)"},
        ],
        "dynamic_columns": [],
        "stop_rules": [],
    }


def test_extract_fixed_columns_by_header_name():
    grid = [
        ["序号", "姓名", "部门"],
        ["1.1", "张三", "技术部"],
    ]
    flat_headers = ["序号", "姓名", "部门"]
    rows = extract_rows(grid, flat_headers, make_config())

    assert len(rows) == 1
    assert rows[0]["person_name"] == "张三"
    assert rows[0]["dept"] == "技术部"
    assert rows[0]["hierarchy_code"] == "1.1"


def test_extract_handles_column_order_change():
    grid = [
        ["部门", "姓名", "序号"],
        ["技术部", "李四", "2.3"],
    ]
    flat_headers = ["部门", "姓名", "序号"]
    rows = extract_rows(grid, flat_headers, make_config())

    assert len(rows) == 1
    assert rows[0]["person_name"] == "李四"
    assert rows[0]["dept"] == "技术部"


def test_extract_unmatched_column_is_none():
    grid = [
        ["序号", "其他列"],
        ["1", "xxx"],
    ]
    flat_headers = ["序号", "其他列"]
    rows = extract_rows(grid, flat_headers, make_config())

    assert rows[0]["person_name"] is None
    assert rows[0]["hierarchy_code"] == "1"


def test_extract_hierarchy_from_merged_header():
    grid = [
        ["部门", "序号", "姓名"],
        ["技术部", "3.5", "王五"],
    ]
    flat_headers = ["部门", "序号", "姓名"]
    rows = extract_rows(grid, flat_headers, make_config())

    assert rows[0]["hierarchy_code"] == "3.5"
    assert rows[0]["dept"] == "技术部"
