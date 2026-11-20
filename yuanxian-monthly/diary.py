"""Local personal work diary. The desktop agent supplies evidence from its chat tools."""
from datetime import date, datetime


def update(folder, req, read_json, save_json, atomic):
    db = folder / "采集索引.json"
    txt = folder / "工作日记.txt"
    state = read_json(db, {"until": None, "days": {}})
    if req["action"] == "diary_show":
        return {"文件": str(txt), **state}
    until = datetime.fromisoformat(req["until"])
    if until.utcoffset() is None:
        raise ValueError("采集截止时间需含时区")
    for day, block in req.get("days", {}).items():
        date.fromisoformat(day)
        current = state["days"].setdefault(day, {"events": {}, "summary": []})
        for event in block.get("events", []):
            if not all(isinstance(event.get(k), str) and event[k].strip() for k in ("key","source","text","status")):
                raise ValueError("每项需提供稳定编号、来源、工作表述和状态")
            current["events"][event["key"]] = event
        # A summary replaces only this day's prose and must cover its retained history.
        if set(block["covers"]) != set(current["events"]):
            raise ValueError(f"{day} 的日报尚未覆盖全部事件")
        lines = block["summary"]
        if not isinstance(lines,list) or not all(isinstance(x,str) and x.strip() for x in lines) or (current["events"] and not lines):
            raise ValueError("请提供可直接使用的日报正文")
        current["summary"] = lines
    if req.get("complete") and (not state["until"] or until >= datetime.fromisoformat(state["until"])):
        state["until"] = until.isoformat()
    body = []
    for day, block in sorted(state["days"].items()):
        body.extend([day, "日报正文", *block["summary"], "工作明细"])
        for event in block["events"].values():
            body.append(f"[{event['status']}] {event['text']}（来源：{event['source']}）")
        body.append("")
    save_json(db,state)
    atomic(txt, ("\n".join(body)+"\n").encode("utf-8-sig"))
    return {"文件":str(txt),"已完整采集至":state["until"]}
