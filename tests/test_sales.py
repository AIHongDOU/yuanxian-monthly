"""Exercise packaged sales import with fictional data and no network access."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile


class SalesImport(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        with ZipFile(Path(__file__).resolve().parents[1] / "dist/yuanxian-monthly.zip") as package:
            package.extractall(self.root / "skill")
        self.identity = dict(name="虚构甲", department="销售部", month="2026-11")

    def call(self, req, success=True):
        proc = subprocess.run([sys.executable, str(self.root/"skill/report.py"),
                               "--project", str(self.root/"员工项目")],
                              input=json.dumps(req).encode(), capture_output=True)
        self.assertEqual(proc.returncode == 0, success, proc.stdout.decode())
        return json.loads(proc.stdout)

    def test_group_and_reimport(self):
        self.assertEqual(self.call({"action":"menu","choice":8})["label"], "销售日报转入月度报表")
        reports = []
        for day in ("18", "19"):
            statements = [f"回访示例客户{i}，对方要求补资料。" for i in range(4)]
            events = [dict(kind="点",raw=s,text=s) for s in statements]
            reports.append(dict(author="虚构甲",date="2026-11-"+day,sources=[day+"上页",day+"续页"],
                                today="\n".join(statements),customer_count=4,events=events,
                                tomorrow="计划前往乙院装机。",metrics={"待核原文":"无标签数字"}))
        row = dict(kind="点",key="客户回访",ids=[f"new:{i}" for i in range(8)],
                   cells={"C":"客户回访","D":"跟进资料需求","F":"客户提出补充资料要求"})
        req = dict(self.identity,action="sales_daily",reports=reports,rows=[row])
        for _ in range(2):
            result = self.call(req)
            self.assertTrue(Path(result["草稿"]).is_file())
            self.assertEqual(len(result["写入位置"]), 1)
        state = self.call(dict(self.identity,action="show"))
        self.assertEqual(len(state["records"]), 8)
        self.assertEqual(len(state["sales_reports"]), 2)
        self.assertTrue(all(len(r["record_ids"])==4 for r in state["sales_reports"].values()))
        self.assertEqual(state["next"], [])
        sys.path.insert(0, str(self.root/"skill"))
        try:
            from book import read
            sheets = read(result["草稿"])
        finally:
            sys.path.pop(0)
        summary, plan = sheets.values()
        self.assertTrue(any(c.get("F")=="客户提出补充资料要求" for c in summary.values()))
        self.assertNotIn("装机", str(sheets))
        self.assertTrue(all(not r.get("D") for n,r in plan.items() if n>=5))
        for field, value in (("author","虚构乙"), ("date","2026-12-18")):
            bad = copy.deepcopy(req)
            bad["reports"][1][field] = value
            self.call(bad, False)
        bad = copy.deepcopy(req)
        bad["reports"][0]["events"][0]["section"] = "tomorrow"
        self.call(bad, False)
        bad = copy.deepcopy(req)
        bad["rows"][0]["ids"].pop()
        self.call(bad, False)
        bad["rows"] = [dict(row,key=str(i),ids=[f"new:{i}"]) for i in range(8)]
        self.assertIn("最多五项", self.call(bad, False)["错误"])
        self.assertEqual(state,self.call(dict(self.identity,action="show")))


if __name__ == "__main__":
    unittest.main()
