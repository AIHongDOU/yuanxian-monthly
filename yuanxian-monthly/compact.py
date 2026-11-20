"""Validate the agent's editorial grouping against the complete month ledger."""
from ledger import KINDS, OPTIONS, require, apply


def prepare(state, req, month):
    rows = req["rows"]
    records = req.get("records", [])
    changes = apply(state, {"action":"record","records":records}, month)
    aliases = {f"new:{i}":next(iter(change.values())) for i,change in enumerate(changes)}
    known = {r["id"]:r for r in state["records"] if r["kind"] in KINDS}
    plans = {p["id"]:p for p in state["current"]}
    seen, linked, counts = set(), set(), dict.fromkeys(KINDS,0)
    result = []
    counted = set()
    for row in rows:
        kind = row["kind"]
        require(kind in KINDS, "汇总分类无效")
        counts[kind] += 1
        require(counts[kind]<=5,"每类最多五项，请合并相关工作")
        ids = [aliases.get(x,x) for x in row["ids"]]
        ps = row.get("plans", [])
        require(bool(ids or ps), "汇总行须有来源")
        for rid in ids:
            require(rid in known and known[rid]["kind"]==kind and rid not in seen,"明细缺失、重复或跨分类")
            seen.add(rid)
        for pid in ps:
            require(pid in plans and plans[pid]["kind"]==kind and pid not in linked,"原计划缺失、重复或跨分类")
            linked.add(pid)
        cells = dict(row["cells"])
        require(set(cells)<=set("CDEFGHIJK") and cells.get("C") and cells.get("D"),"请提供工作标题及内容")
        if len(ps)==1:
            cells.update(C=plans[ps[0]]["c"],D=plans[ps[0]]["d"])
        for col,field in (("G","verdict"),("H","status")):
            require(not cells.get(col) or cells[col] in OPTIONS[field],"状态或判定无效")
        if cells.get("I") is not None:
            require(isinstance(cells["I"],(int,float)) and 0<=cells["I"]<=1,"进度应为 0 至 1")
        evidence = {}
        if row.get("tally"):
            # Each identity is a verified distinct work item, never a chat/commit count.
            tally=row["tally"]
            items=tally["items"]
            require(isinstance(items,dict) and items and all(key.strip() and aliases.get(ref,ref) in ids for key,ref in items.items()),"计数缺少对应明细")
            require(counted.isdisjoint(items),"同一成果已在另一行计数")
            counted.update(items)
            evidence={k:aliases.get(v,v) for k,v in items.items()}
            require("{数量}" in cells.get("F",""),"计数结果请使用 {数量}")
            cells["F"]=cells["F"].replace("{数量}",str(len(items)))
        result.append(dict(kind=kind,ids=ids,plans=ps,tally=evidence,cells=cells,key="compact-"+str(row.get("key") or (ps or ids)[0])))
    require(len({r["key"] for r in result})==len(result),"汇总行编号重复")
    require(seen==set(known) and linked==set(plans),"尚有明细或原计划未归入月报，请补齐后生成")
    if "next_groups" in req:
        old={p["id"]:p for p in state["next"]}
        assigned=set()
        combined=[]
        for g in req["next_groups"]:
            ids=g["plans"]
            require(ids and len(ids)==len(set(ids)) and assigned.isdisjoint(ids) and all(i in old and old[i]["kind"]==g["kind"] for i in ids),"来月计划分组无效")
            assigned.update(ids)
            require(g.get("c") and g.get("d"),"请提供合并后的来月计划")
            combined.append(dict(old[ids[0]],c=g["c"],d=g["d"],originals=[old[i] for i in ids]))
        require(assigned==set(old),"有来月计划未覆盖")
        state["next"]=combined
    require(all(sum(p["kind"]==k for p in state["next"])<=5 for k in KINDS),"请用 next_groups 合并来月计划，每类最多五项")
    state["compact_rows"]=result
    state["compact_stale"]=False
    return changes
