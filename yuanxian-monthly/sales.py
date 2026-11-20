"""Import one employee's transcribed sales reports through the monthly grouping rules."""
from datetime import date

from compact import prepare
from ledger import require


def prepare_sales(state, request, month, person):
    archive = state.setdefault("sales_reports", {})
    reports = request["reports"]
    require(isinstance(reports, list) and reports, "请提供销售日报")
    entries = []
    for report in reports:
        require(report["author"] == person["name"], "一份月报只能转入该员工的日报，请按作者分开")
        day = date.fromisoformat(report["date"]).isoformat()
        require(day[:7] == month, "请按日报所属年月分开转入")
        key = day + "/" + (report.get("report_id") or "日报")
        sources = report["sources"]
        require(isinstance(sources, list) and sources and all(isinstance(s, str) and s.strip() for s in sources), "请注明日报来源")
        saved = archive.setdefault(key, {"author": person["name"], "date": day, "sources": []})
        for source in sources:
            if source not in saved["sources"]:
                saved["sources"].append(source)
        for field in ("location", "customer_count", "focus", "today", "tomorrow", "metrics", "questions"):
            value = report.get(field)
            if value is None or value == "":
                continue
            if field == "customer_count":
                require(type(value) is int and value >= 0, "客户数量应为非负整数或留空")
            if field in ("today", "focus", "tomorrow"):
                require(isinstance(value, str), "请保留日报栏目原文")
            if field in saved and saved[field] != value:
                raise ValueError(f"{key} 的 {field} 与已存日报不同，请核对原文后重试")
            saved[field] = value
        events = report["events"]
        require(isinstance(events, list), "请提供日报已发生事项列表")
        for event in events:
            section = event.get("section", "today")
            require(section in ("today", "focus"), "只有今日总结或重点进度中的事实可进入实绩")
            raw = event["raw"]
            require(isinstance(raw, str) and raw.strip() and
                    "".join(raw.split()) in "".join(saved.get(section, "").split()),
                    f"{key} 事项缺少对应栏目原文")
            entries.append(dict(event, date=day, source=f"销售日报 {key} / {section}", sales_report=key))
    # As with batch, validation precedes the ledger commit. A rejected grouping
    # cannot partially import an employee's reports.
    changes = prepare(state, dict(request, records=entries), month)
    for entry, change in zip(entries, changes):
        record_id = next(iter(change.values()))
        links = archive[entry["sales_report"]].setdefault("record_ids", [])
        if record_id not in links:
            links.append(record_id)
    return changes
