from parser.core.header_flattener import flatten_headers


def test_flatten_headers_concatenates():
    grid = [
        ["序号", "截止到当前", ""],
        ["", "实际人月", "实际总成本"],
    ]
    result = flatten_headers(grid, header_rows=[0, 1])
    assert result == ["序号", "截止到当前_实际人月", "实际总成本"]


def test_flatten_headers_skips_empty_parts():
    grid = [
        ["姓名", "部门", ""],
        ["", "", ""],
    ]
    result = flatten_headers(grid, header_rows=[0, 1])
    assert result == ["姓名", "部门", ""]


def test_flatten_headers_three_level():
    grid = [
        ["累计已发生", "累计已发生", "累计已发生"],
        ["2025年", "2025年", "2025年"],
        ["7月", "8月", "9月"],
    ]
    result = flatten_headers(grid, header_rows=[0, 1, 2])
    assert result == [
        "累计已发生_2025年_7月",
        "累计已发生_2025年_8月",
        "累计已发生_2025年_9月",
    ]
