"""Template-specific OOXML adapter. Retain the supplied style table and worksheet parts."""
from copy import deepcopy
from pathlib import PurePosixPath
import datetime as dt
import io
import re
import unicodedata
import math
import zipfile
import xml.etree.ElementTree as ET

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
Q = lambda name: "{%s}%s" % (NS, name)
COLS = "ABCDEFGHIJKL"
KINDS = ("面", "线", "点")
PARTS = ("总结", "计划")


def shift(month, offset):
    year, m = map(int, month.split("-"))
    y, n = divmod(year * 12 + m - 1 + offset, 12)
    return f"{y:04}-{n+1:02}"


def title(month, part):
    y, m = map(int, month.split("-"))
    return f"{y}年{m}月工作{part}"


def value(cell, strings):
    if cell.find(Q("f")) is not None:
        return "=" + (cell.findtext(Q("f")) or "")
    typ = cell.get("t")
    if typ == "inlineStr":
        return "".join(e.text or "" for e in cell.iter(Q("t")))
    val = cell.findtext(Q("v"))
    if val in (None, ""):
        return None
    if typ == "s":
        return strings[int(val)] or None
    return float(val) if typ in (None, "n") else val


def read(path):
    with zipfile.ZipFile(path) as z:
        ss = "xl/sharedStrings.xml"
        strings = ["".join(t.text or "" for t in e.iter(Q("t"))) for e in ET.fromstring(z.read(ss))] if ss in z.namelist() else []
        links = {r.get("Id"):r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        sheets = {}
        for s in ET.fromstring(z.read("xl/workbook.xml")).iter(Q("sheet")):
            target = links[s.get("{%s}id" % R)]
            part = target.lstrip("/") if target.startswith("/") else str(PurePosixPath("xl") / target)
            rows = {}
            # The template styles several full-width rows. Only read the report columns.
            with z.open(part) as data:
                for _, cell in ET.iterparse(data):
                    if cell.tag == Q("c"):
                        col, row = re.fullmatch(r"([A-Z]+)(\d+)", cell.get("r")).groups()
                        if col in tuple(COLS):
                            val = value(cell, strings)
                            if val is not None:
                                rows.setdefault(int(row), {})[col] = val
                        cell.clear()
            sheets[s.get("name")] = rows
    return sheets


def set_cell(row, col, val):
    addr = col + row.get("r")
    cell = row.find(f"{{*}}c[@r='{addr}']")
    if cell is None:
        if val is None:
            return
        cell = ET.Element(Q("c"), r=addr)
        # New business cells precede the template's trailing styled columns.
        pos = next((i for i,c in enumerate(row) if re.match("[A-Z]+", c.get("r"))[0] not in COLS[:COLS.index(col)+1]), len(row))
        row.insert(pos, cell)
    for child in list(cell):
        cell.remove(child)
    cell.attrib.pop("t", None)
    if isinstance(val, (int,float)):
        ET.SubElement(cell, Q("v")).text = str(val)
    elif val is not None and val != "":
        if len(str(val))>32767 or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]",str(val)):
            raise ValueError(f"{addr} 文本过长或含 Excel 不支持的字符，请拆分或修正该字段")
        cell.set("t","inlineStr")
        t = ET.SubElement(ET.SubElement(cell,Q("is")),Q("t"))
        t.set("{http://www.w3.org/XML/1998/namespace}space","preserve")
        t.text = str(val)


def serialize(root, original):
    # Keep prefixes named by mc:Ignorable / Requires even when otherwise unused.
    namespaces = dict((p or "",u) for _,(p,u) in ET.iterparse(io.BytesIO(original),events=("start-ns",)))
    for p,u in namespaces.items():
        ET.register_namespace(p,u)
    xml = ET.tostring(root,encoding="utf-8")
    head, tail = xml.split(b">",1)
    for p,u in namespaces.items():
        attr = ("xmlns:"+p if p else "xmlns").encode()
        if attr+b"=" not in head:
            head += b" "+attr+b'="'+u.encode()+b'"'
    return head+b">"+tail


def generate(template, dest, person, month, layouts):
    with zipfile.ZipFile(template) as src, zipfile.ZipFile(dest,"w",zipfile.ZIP_DEFLATED) as out:
        changed = {}
        names = []
        ss_path="xl/sharedStrings.xml"
        original_ss=src.read(ss_path)
        strings=ET.fromstring(original_ss)
        compact=ET.Element(Q("sst"))
        indexes={}
        reference_count=0
        for i, layout in enumerate(layouts):
            m = shift(month,i)
            name = title(m, PARTS[i])
            names.append(name)
            part = f"xl/worksheets/sheet{i+1}.xml"
            original = src.read(part)
            root = ET.fromstring(original)
            data = root.find(Q("sheetData"))
            prototypes = list(data)
            data.clear()
            for r in prototypes[:4]:
                data.append(r)
            set_cell(data[0],"A",name+"（标准化梳理）")
            checker=person.get("checkers",{}).get(name,person.get("checker",""))
            set_cell(data[1],"A",f"部门：{person['department']}　　姓名：{person['name']}　　检查人：{checker}　　制表时间：{dt.date.today():%Y.%m.%d}")
            set_cell(data[3],"C",f"{int(m[-2:])}月度工作计划")
            for header in list(data):
                for cell in header.findall("{*}c[@t='s']"):
                    index=cell.find(Q("v"))
                    old=int(index.text)
                    if old not in indexes:
                        indexes[old]=len(compact)
                        compact.append(strings[old])
                    index.text=str(indexes[old])
                    reference_count+=1
            merges = root.find(Q("mergeCells"))
            for merge in list(merges)[3:]:
                merges.remove(merge)
            normal = []
            widths = {int(c.get("min")): float(c.get("width")) for c in root.findall("{*}cols/{*}col") if c.get("width")}
            for rn, item in enumerate(layout,5):
                proto = prototypes[item["prototype"]-1]
                row = deepcopy(proto)
                row.set("r",str(rn))
                for c in row:
                    c.set("r",re.sub(r"\d+$",str(rn),c.get("r")))
                for col in COLS:
                    set_cell(row,col,item["cells"].get(col))
                # Keep the template's minimum height; leave space for wrapped business text.
                lines = 1
                for col in "CDEFJK":
                    width = max(1, widths.get(COLS.index(col)+1, 16)-2)
                    blocks = str(item["cells"].get(col) or "").split("\n")
                    lines = max(lines, sum(max(1, math.ceil(sum(2 if unicodedata.east_asian_width(ch) in ("W","F") else 1 for ch in block)/width)) for block in blocks))
                if lines > 1:
                    row.set("ht", str(min(409, max(float(row.get("ht", 15)), 16*lines+4))))
                    row.set("customHeight","1")
                data.append(row)
                if item["insert"]:
                    ET.SubElement(merges,Q("mergeCell"),ref=f"A{rn}:B{rn}")
                else:
                    normal.append(f"B{rn}")
            end = len(layout)+4
            merges.set("count",str(len(merges)))
            root.find(Q("dimension")).set("ref",f"A1:XFD{end}")
            for cf in root.findall(Q("conditionalFormatting")):
                col = cf.get("sqref")[0]
                cf.set("sqref",f"{col}5:{col}{end}")
            for dv,col in zip(root.iter(Q("dataValidation")),"BGH"):
                dv.set("sqref"," ".join(normal) if col=="B" else f"{col}5:{col}{end}")
            changed[part] = serialize(root,original)
        compact.attrib.update(count=str(reference_count),uniqueCount=str(len(compact)))
        changed[ss_path]=serialize(compact,original_ss)
        for filename, tag in [("xl/workbook.xml",Q("sheet")),("docProps/app.xml","{*}TitlesOfParts")]:
            xml = src.read(filename)
            rt = ET.fromstring(xml)
            if filename.startswith("xl/"):
                for item in rt.findall("{*}AlternateContent"):
                    if item.find(".//{*}absPath") is not None:
                        rt.remove(item)
                for sheet,name in zip(rt.iter(tag),names):
                    sheet.set("name",name)
            else:
                for node,name in zip(rt.find(tag).iter("{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}lpstr"),names):
                    node.text=name
            changed[filename]=serialize(rt,xml)
        for info in src.infolist():
            out.writestr(info, changed[info.filename] if info.filename in changed else src.read(info))

