import datetime as dt
import difflib
import hashlib
import json
import re
import uuid
from collections import defaultdict
from book import KINDS, shift, title, read

FIELDS = dict(target="E", result="F", verdict="G", status="H", progress="I", evidence="J", followup="K")
OPTIONS = {"status":("待开始","进展中","已完成"), "verdict":("达成","部分达成","未达成","延期")}
def uid():
    return uuid.uuid4().hex[:12]

def require(ok, msg):
    if not ok:
        raise ValueError(msg)

def clean(value):
    return re.sub(r"[\W_]+","",value).casefold()

def import_previous(path, profile, month):
    sheets = read(path)
    expected = title(month,"计划")
    candidates = [s for s,rows in sheets.items() if expected in str(rows.get(1,{}).get("A","")) and "计划" in s]
    require(len(candidates)==1, f"上期定稿中找不到唯一的{expected}")
    rows = sheets[candidates[0]]
    for label,key in [("姓名","name"),("部门","department")]:
        require(re.search(label+r"\s*[：:]\s*"+re.escape(profile[key])+r"(?:\s|$)", rows[2]["A"]), "上期工作簿人员资料不一致")
    plans = []
    kind = None
    for rn,r in sorted(rows.items()):
        if rn < 5: continue
        kind = r.get("B") or kind
        if r.get("C") or r.get("D"):
            require(kind in KINDS,"上期分类无法识别")
            plans.append(dict(id=f"prev-{rn}",kind=kind,c=r.get("C"),d=r.get("D")))
    return plans

def validate_record(r, month, state):
    require(isinstance(r.get("raw"),str) and r["raw"].strip() and r.get("text"),"需要原文和整理后的表述")
    if r["date"] != month:
        require(dt.date.fromisoformat(r["date"]).strftime("%Y-%m")==month,"事项日期不属于总结月份")
    require(r["kind"] in (*KINDS,"待核"),"分类无效")
    for k, opts in OPTIONS.items():
        require(r.get(k) in (None,*opts),f"{k} 选项无效")
    for k in ("progress","previous","goal"):
        if r.get(k) is not None:
            require(isinstance(r[k],(float,int)) and 0<=r[k]<=1, f"{k} 取值为 0 至 1")
    plans={p["id"]:p for p in state["current"]}
    if r.get("plan"):
        require(r["plan"] in plans and plans[r["plan"]]["kind"]==r["kind"],"关联计划的编号或分类不一致")
    if r.get("parent"):
        require(r["parent"] in plans and plans[r["parent"]]["kind"]=="面","上级项目必须是本月的面计划")

def apply(state, req, month):
    recs = state["records"]
    op = req["action"]
    changes = []
    if op=="record":
        for entry in req["records"]:
            r = dict(entry,id=uid())
            validate_record(r,month,state)
            def event_key(event):
                return event["date"]," ".join(event["raw"].split()),event.get("occurrence","")
            match = next((x for x in recs if event_key(x)==event_key(r)),None)
            if entry.get("same_as"):
                match=next((x for x in recs if x["id"]==entry["same_as"] and x["date"]==r["date"]),None)
                require(match,"已匹配的历史事项编号或日期不一致")
                variants=match.setdefault("source_variants",[])
                if r["raw"]!=match["raw"] and r["raw"] not in variants:
                    variants.append(r["raw"])
            if match:
                changes.append({"重复":match["id"]})
                continue
            recs.append(r)
            changes.append({"新增":r["id"]})
    elif op in ("edit","undo"):
        target = req.get("id") or (recs[-1]["id"] if recs else None)
        r = next((x for x in recs if x["id"]==target),None)
        require(r,"未找到记录")
        if op=="undo":
            recs.remove(r)
        else:
            patch=req["set"]
            require(not set(patch).intersection(("raw","id","date")),"保留原始记录标识和日期")
            r.update(patch)
            validate_record(r,month,state)
        changes.append({op:target})
    elif op=="plans":
        side=req["side"]
        require(side in ("current","next"),"计划方向无效")
        require(side!="current" or not state["inherited"],"本月计划已从上月定稿继承")
        for item in req["items"]:
            p={k:item.get(k) for k in ("kind","c","d")}
            require(p["kind"] in KINDS and (p["c"] or p["d"]),"需要计划及分类")
            if not any(all(x[k]==v for k,v in p.items()) for x in state[side]):
                state[side].append(dict(p,id=uid()))
    elif op=="display":
        require(req["mode"] in ("逐条","汇总"),"显示模式无效")
        state["mode"]=req["mode"]
    return changes

def content(records):
    cells={}
    results=[]
    goal=None
    for r in sorted(records,key=lambda x:x["date"]):
        if r.get("goal") is not None:
            goal=r["goal"]
            cells["E"]=f"本月累计目标 {goal*100:g}%"
        for key,col in FIELDS.items():
            if key!="result" and r.get(key) is not None:
                cells[col]=r[key]
        facts=[r["result"]] if r.get("result") else []
        if r.get("progress") is not None:
            cur=r["progress"]
            if r.get("previous") is not None:
                facts.append(f"累计由 {r['previous']*100:g}% 至 {cur*100:g}%，本月变动 {(cur-r['previous'])*100:g} 个百分点")
            if goal is not None and not r.get("verdict"):
                if cur>=goal:
                    cells["G"]="达成"
                else:
                    cells.pop("G",None)
        if facts: results.append(r["date"]+" "+"；".join(facts))
    if results: cells["F"]="\n".join(results)
    return cells

def layout(state,side):
    groups=defaultdict(list)
    extras={}
    links=defaultdict(list)
    compact=side=="current" and "compact_rows" in state
    if side=="current" and not compact:
        for r in state["records"]:
            if r.get("plan"):
                links[r["plan"]].append(r)
            elif r["kind"] in KINDS:
                group = r.get("group") if r["kind"]!="点" or state["mode"]=="汇总" else None
                key=(r["kind"],group or r["id"],r.get("parent"))
                extras.setdefault(key,[]).append(r)
    for p in ([] if compact else state[side]):
        rs=links[p["id"]]
        cells={"C":p["c"],"D":p["d"],**content(rs)}
        if p["kind"]=="点" and rs and state["mode"]=="汇总":
            cells["F"]=f"共 {len(rs)} 次"+("\n"+cells["F"] if cells.get("F") else "")
        groups[p["kind"],False].append((p["id"],cells,[x["id"] for x in rs]))
        if p["kind"]=="点" and state["mode"]=="逐条" and len(rs)>1:
            groups[p["kind"],False][-1]=(p["id"],{"C":p["c"],"D":p["d"],**content(rs[:1])},[rs[0]["id"]])
            for x in rs[1:]:
                groups[p["kind"],False].append((x["id"],{"C":p["c"],"D":p["d"],**content([x])},[x["id"]]))
    for (kind,group,parent),rs in extras.items():
        cells={"C":rs[0].get("group") or rs[0]["text"],"D":rs[-1]["text"],**content(rs)}
        if kind=="点" and state["mode"]=="汇总":
            cells["D"]=f"{cells['D']}（共 {len(rs)} 次）"
        groups[kind,True].append(("extra-"+rs[0]["id"],cells,[r["id"] for r in rs]))
    if compact:
        for row in state["compact_rows"]:
            groups[row["kind"],False].append((row["key"],row["cells"],row["ids"]))
    items=[]
    serial=0
    for idx,kind in enumerate(KINDS):
        for insert in (False,True):
            entries=groups[kind,insert]
            for j in range(max(1 if insert else 5,len(entries))):
                key,cells,ids=entries[j] if j<len(entries) else (f"blank-{kind}-{insert}-{j}",{},[])
                if not insert: serial+=1
                row=dict(A="插入项" if insert else serial, B=None if insert else kind, **cells)
                items.append(dict(key=key,cells=row,ids=ids,kind=kind,insert=insert,prototype=5+idx*6+(5 if insert else min(4,j))))
    return items

def review(state,rows):
    issues=defaultdict(list)
    for item in rows:
        c=item["cells"]
        if not (c.get("C") or c.get("D")): continue
        label={"id":item["key"],"工作项":c.get("C") or c.get("D")}
        for col,reason in [("F","缺实绩"),("J","缺判定依据")]:
            if not c.get(col): issues[reason].append(label)
        if c.get("H")!="已完成": issues["供核对是否续排"].append(label)
    recs=state["records"]
    issues["尚未归类"]=[r for r in recs if r["kind"]=="待核"]
    for i,r in enumerate(recs):
        for other in recs[:i]:
            if r["date"]==other["date"] and (r.get("group") and r.get("group")==other.get("group") or difflib.SequenceMatcher(None,clean(r["raw"]),clean(other["raw"])).ratio()>=0.62):
                issues["疑似重复（保留两条）"].append([other["id"],r["id"]])
    return issues

