import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from excel_to_ralf import generate_ralf, load_excel


class BlockNameDefaultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.excel = Path(self.temp.name) / "regs.xlsx"

    def write_sheet(self, blocks):
        rows = []
        for i, block in enumerate(blocks):
            rows.append({
                "BlockName": block,
                "RegName": "CTRL" if i == 0 else None,
                "RegOffset": "0x0" if i == 0 else None,
                "Bit": "7:0" if i == 0 else "15:8",
                "FieldName": "enable" if i == 0 else "mode",
                "Access": "rw",
                "ResetValue": "0x1",
                "Description": "Test field",
            })
        pd.DataFrame(rows).to_excel(self.excel, index=False)

    def check_output(self, blocks, expected_blocks):
        self.write_sheet(blocks)
        df = load_excel(self.excel, 0)
        self.assertEqual(df["BlockName"].tolist(), expected_blocks)
        result = generate_ralf(df)
        self.assertEqual(result.count("field enable @0 {"), 1)
        self.assertEqual(result.count("field mode @8 {"), 1)
        for block in set(expected_blocks):
            self.assertEqual(result.count("block " + block + " {"), 1)
        return result

    def test_entire_block_column_blank_defaults_to_top(self):
        self.check_output([None, None], ["TOP", "TOP"])

    def test_leading_blank_defaults_to_top_before_named_block(self):
        self.check_output([None, "DEVICE"], ["TOP", "DEVICE"])

    def test_continuation_retains_named_block(self):
        self.check_output(["DEVICE", None], ["DEVICE", "DEVICE"])

    def test_default_and_explicit_top_share_one_block(self):
        result = self.check_output([None, "TOP"], ["TOP", "TOP"])
        self.assertEqual(result.count("register CTRL"), 1)

    def test_missing_column_header_is_still_rejected(self):
        self.write_sheet([None, None])
        df = pd.read_excel(self.excel).drop(columns=["BlockName"])
        df.to_excel(self.excel, index=False)
        with self.assertRaisesRegex(ValueError, "BlockName"):
            load_excel(self.excel, 0)

    def test_cli_writes_fields_for_blank_block_column(self):
        self.write_sheet([None, None])
        output = Path(self.temp.name) / "regs.ralf"
        script = Path(__file__).resolve().parents[1] / "excel_to_ralf.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--excel", str(self.excel),
             "--out", str(output)], capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = output.read_text(encoding="utf-8")
        self.assertIn("block TOP {", result)
        self.assertIn("field enable @0 {", result)
        self.assertIn("field mode @8 {", result)


if __name__ == "__main__":
    unittest.main()
