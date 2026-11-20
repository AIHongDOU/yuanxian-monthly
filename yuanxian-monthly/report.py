"""Local JSON request interface; all platforms use the same project directory."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import datetime as dt

from book import COLS, PARTS, generate, read, shift, title
from ledger import apply, import_previous, layout, require, review
from mail_report import digest, process
from compact import prepare
from diary import update as update_diary

BASE=Path(__file__).resolve().parent
TEMPLATE=BASE/"模板_11月工作计划与10月工作总结.xlsx"

def atomic(path,data):
    with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as f:
        tmp=Path(f.name)
        try:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        except BaseException:
            f.close()
            tmp.unlink(missing_ok=True)
            raise
    try: os.replace(tmp,path)
    finally: tmp.unlink(missing_ok=True)

def put(path,obj):
    atomic(path,json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False).encode())

def get(path,default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default

@contextlib.contextmanager
def guard(path):
    with path.open("a+b") as f:
        f.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(f.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(f,fcntl.LOCK_EX)
        yield

def safe_label(label):
    require(isinstance(label,str) and label==label.strip(" .") and 0<len(label)<=64 and not re.search(r'[\\/:*?"<>|\x00-\x1f]',label),"姓名或部门含无效字符")
    return label

def paths(folder,person,month):
    stem=f"{person['name']}_{month}_月度报表"
    return folder/(stem+"_草稿.xlsx"),folder/(stem+"_定稿.xlsx")

def merge(draft,month,state,layouts,person):
    before=state.get("baseline")
    if not before:
        require(not draft.exists(),"发现无同步基线的草稿，请先保留副本并人工核对")
        return
    require(draft.exists(),"草稿缺失，请恢复文件后重试")
    sheets=read(draft)
    for i,(old,items) in enumerate(zip(before,layouts)):
        name=title(shift(month,i),PARTS[i])
        require(name in sheets,f"草稿页签已变更：{name}")
        rows=sheets[name]
        info=str(rows.get(2,{}).get("A",""))
        for label,field in (("姓名","name"),("部门","department")):
            require(re.search(label+r"\s*[：:]\s*"+re.escape(person[field])+r"(?:\s|$)",info),f"{name} A2 人员信息不一致，请核对原稿")
        match=re.search(r"检查人[：:]\s*(.*?)\s*制表时间",info)
        if match and match[1].strip():
            person.setdefault("checkers",{})[name]=match[1].strip()
        require(not any(r>len(old)+4 and any(k in COLS for k in c) for r,c in rows.items()),f"{name} 有手动新增行，请先将新增内容录入台账")
        by_key={item["key"]:item for item in items}
        for rn,base in enumerate(old,5):
            live=rows.get(rn,{})
            target=by_key.get(base["key"])
            for col in COLS:
                v=live.get(col)
                b=base["cells"].get(col)
                if v==b: continue
                ident=base["cells"].get("C") or base["key"]
                location=f"{name} {ident} {col}{rn}"
                require(col not in "AB",f"{location} 序号或分类布局已变更，请在台账修正分类")
                require(target,f"{location} 对应行已移动或删除，人工值 {v!r}；请核对后重试")
                require(not (i and col in "EFGHIJKL" and v is not None),f"{location} 计划页只能填写 C、D")
                require(not (i==0 and state["inherited"] and base["key"].startswith("prev-") and col in "CD"),f"{location} 须保留上月定稿原文 {b!r}")
                new=target["cells"].get(col)
                require(new==b or new==v,f"{location} 字段冲突：上次 {b!r}，Excel {v!r}，台账 {new!r}。保留 Excel 值请调整台账，采用台账值请将该格恢复为上次值。")
                if isinstance(v,str) and v.startswith("="):
                    raise ValueError(f"{location} 含人工公式，请先核对；原稿已保留")
                target["cells"][col]=v

def run(root,req):
    data=root.resolve()/"月报数据"
    data.mkdir(parents=True,exist_ok=True)
    if req["action"] in ("diary","diary_show"):
        folder=data/"工作日记"/safe_label(req["diary_id"])
        folder.mkdir(parents=True,exist_ok=True)
        with guard(folder/"操作.lock"):
            return update_diary(folder,req,get,put,atomic)
    if req["action"]=="profiles":
        return [get(x) for x in sorted(data.glob("*/员工.json"))]
    name=safe_label(req["name"])
    department=req.get("department")
    if department is None:
        matches=[x for x in data.glob("*/员工.json") if get(x)["name"]==name]
        require(len(matches)==1,"首次使用或姓名重名，请提供部门")
        existing=get(matches[0])
        department=existing["department"]
        if existing.get("employee_id"):
            req.setdefault("employee_id",existing["employee_id"])
    if not req.get("employee_id"):
        identities=[get(x) for x in data.glob("*/员工.json")]
        same=[p for p in identities if p["name"]==name and p["department"]==department]
        require(len(same)<=1,"同名同部门员工，请指定 employee_id")
        if same and same[0].get("employee_id"):
            req["employee_id"]=same[0]["employee_id"]
    safe_label(department)
    identity=hashlib.sha256(json.dumps([name,department,req.get("employee_id","")],ensure_ascii=False).encode()).hexdigest()[:16]
    person_dir=data/f"{name}-{identity}"
    person_dir.mkdir(exist_ok=True)
    with guard(person_dir/"操作.lock"):
        person={"name":name,"department":department}
        if req.get("employee_id"): person["employee_id"]=req["employee_id"]
        put(person_dir/"员工.json",person)
        return monthly(req,person,person_dir)

def monthly(req,person,person_dir):
    action=req["action"]
    actions=("show","batch","record","edit","undo","plans","display","sync","final","preview","send","reconcile")
    require(action in actions,"未知操作")
    month=req["month"]
    require(re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])",month),"年月格式应为 YYYY-MM")
    folder=person_dir/month
    folder.mkdir(exist_ok=True)
    draft,final=paths(folder,person,month)
    db=folder/"台账.json"
    state=get(db)
    if state is None:
        prev=shift(month,-1)
        last=paths(person_dir/prev,person,prev)[1]
        if "previous_file" in req:
            last=Path(req["previous_file"]).resolve()
            require(last.is_file() and not last.name.startswith("~$"),"上期文件不可用")
        inherited=last.exists()
        plans=import_previous(last,person,month) if inherited else []
        state=dict(current=plans,next=[],inherited=inherited,mode="汇总",records=[])
    save=lambda:put(db,state)
    if action in ("preview","send","reconcile"):
        return process(req,state,final,folder,person,month,save)
    if action=="show":
        return {**{k:v for k,v in state.items() if k!="baseline" and k!="mail"},"目录":str(folder)}
    require(not final.exists() or action=="final","该月已定稿，请核对定稿版本")
    if final.exists():
        require(digest(final.read_bytes())==state.get("final_sha"),"定稿校验失败")
        return {"定稿":str(final)}
    receipt=None
    if action=="record" and ("source_file" in req or "source_text" in req):
        source=Path(req["source_file"]).read_bytes() if "source_file" in req else req["source_text"].encode("utf-8")
        receipt=digest(source)
    if action=="batch":
        changes=prepare(state,req,month)
    elif receipt and receipt in state.get("imports",{}):
        changes=[{"已导入同一份笔记":state["imports"][receipt]}]
    else:
        changes=apply(state,req,month)
        if "compact_rows" in state and action in ("record","edit","undo","plans") and (action=="plans" or any("重复" not in change for change in changes)):
            state["compact_stale"]=True
        if receipt:
            state.setdefault("imports",{})[receipt]=changes
    save() # Commit records even if Excel has the draft open.
    journal=folder/"同步事务.json"
    try:
        require(not state.get("compact_stale"),"月末汇总后明细或计划有更新，请按最新台账重新运行 batch")
        if journal.exists():
            pending=get(journal)
            if draft.exists() and digest(draft.read_bytes())==pending["hash"]:
                state["baseline"]=pending["baseline"]
                save()
            journal.unlink()
        require(not (folder/("~$"+draft.name)).exists(),"Excel 正在使用草稿")
        start=digest(draft.read_bytes()) if draft.exists() else None
        layouts=[layout(state,s) for s in ("current","next")]
        baseline=[[{"key":x["key"],"cells":dict(x["cells"])} for x in items] for items in layouts]
        merge(draft,month,state,layouts,person)
        if start and start!=state.get("draft_sha"):
            archive=folder/"人工修改留档"/(start[:16]+".xlsx")
            archive.parent.mkdir(exist_ok=True)
            if not archive.exists():
                atomic(archive,draft.read_bytes())
        output=folder/"同步中.tmp"
        try:
            generate(TEMPLATE,output,person,month,layouts)
            require((digest(draft.read_bytes()) if draft.exists() else None)==start,"草稿在同步期间发生变化，请重试")
            fingerprint=digest(output.read_bytes())
            put(journal,dict(hash=fingerprint,baseline=baseline))
            os.replace(output,draft)
        finally: output.unlink(missing_ok=True)
        state["baseline"]=baseline
        state["draft_sha"]=fingerprint
        state.pop("pending",None)
        save()
        journal.unlink(missing_ok=True)
        issues=review(state,layouts[0])
        result={"变更":changes,"草稿":str(draft),"核对":issues,"写入位置":[{"记录":x["ids"],"工作项":x["cells"].get("C"),"行":n,"页签":title(month,"总结"),"栏":{k:v for k,v in x["cells"].items() if k not in "AB" and v is not None}} for n,x in enumerate(layouts[0],5) if x["ids"]]}
        if action=="final":
            state["final_sha"]=fingerprint
            save()
            atomic(final,draft.read_bytes())
            result["定稿"]=str(final)
        return result
    except (OSError,ValueError) as e:
        state["pending"]=str(e)
        save()
        return {"变更":changes,"台账已保存":True,"草稿待同步":str(e),"草稿":str(draft)}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--project",type=Path,default=Path.cwd())
    parser.add_argument("request",nargs="?",type=Path,help="UTF-8 JSON，省略时读标准输入")
    args=parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        request=json.loads(args.request.read_text(encoding="utf-8-sig") if args.request else sys.stdin.buffer.read().decode("utf-8-sig"))
        print(json.dumps(run(args.project,request),ensure_ascii=False,indent=2))
    except Exception as exc:
        print(json.dumps({"错误":str(exc)},ensure_ascii=False))
        sys.exit(1)

