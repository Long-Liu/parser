from parser.core.cell_unmerger import unmerge
from parser.core.header_flattener import flatten_headers
from parser.core.data_extractor import DataExtractor
from parser.core.validator import validate


class Pipeline:
    def __init__(self, config: dict):
        self.config = config
        self.extractor = DataExtractor(config)

    def run(self, ws, batch_id: int) -> dict:
        sheet_name = ws.title

        grid = unmerge(ws)
        header_rows = [r - 1 for r in self.config.get("headers", {}).get("rows", [])]
        flat_headers = flatten_headers(grid, header_rows)

        rows = self.extractor.extract_rows(grid, flat_headers)
        columns = self.config.get("columns", [])
        valid_rows, errors = validate(rows, columns)

        for row in valid_rows:
            row["batch_id"] = batch_id

        return {
            "template_id": self.config.get("template_id"),
            "sheet_name": sheet_name,
            "total_rows": len(rows),
            "success_rows": len(valid_rows),
            "error_rows": len(errors),
            "rows": valid_rows,
            "errors": errors,
        }
