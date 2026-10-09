from __future__ import annotations
import re
from pathlib import Path
from typing import TypedDict
STATUS_MAPPING = {"ПЕРЕВІРЕНО": "DONE", "РОЗРОБКА": "IN PROGRESS", "ПЛАН": "PLANNED", "БЛОКЕР": "BLOCKED", "УЗГОДЖЕНО": "PLANNED", "БАЗА": "BASE"}
GROUP_MAPPING = {"CORE": "Core / Реєстрація і тарифи", "CAT": "Матеріали", "FUR": "Фурнітура", "MNT": "Монтажні вузли", "ROOM": "3D / Проєктування", "MOD": "3D / Проєктування", "RULE": "3D / Проєктування", "STOCK": "Склад / Операції", "CUT": "Склад / Операції", "COST": "Кошторис", "AI": "Асистент", "PROD": "Виробництво", "UX": "Мобільна версія", "OPS": "Product Center"}
class ProductMapRecord(TypedDict):
    id: str
    title: str
    section: str
    original_status: str
    normalized_status: str
    goal: str
    dependencies: list[str]
    description: str
    acceptance_criteria: str
    decisions: list[str]
    source_lines: list[int]
    group: str
_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]+-\d{3}\b")
_STATUS_RE = re.compile(r"\[([^]]+)\]")
def group_for_id(record_id: str) -> str:
    prefix = record_id.split("-", 1)[0].upper()
    return GROUP_MAPPING.get(prefix, "Інше")

def normalize_status(original_status: str) -> str:
    statuses = [STATUS_MAPPING.get(value.strip()) for value in _STATUS_RE.findall(original_status)]
    statuses = [status for status in statuses if status is not None]
    if not statuses: return "UNKNOWN"
    priority = {"BLOCKED": 5, "IN PROGRESS": 4, "PLANNED": 3, "DONE": 2, "BASE": 1}
    return max(statuses, key=lambda status: priority[status])
def _table_cells(line: str) -> list[str]: return [cell.strip() for cell in line.strip().strip("|").split("|")]
def _section_blocks(lines: list[str]) -> list[tuple[int, str, list[str]]]:
    blocks=[]; start=None; title=""; block=[]
    for number,line in enumerate(lines,1):
        if line.startswith("## "):
            if start is not None: blocks.append((start,title,block))
            start,title,block=number,line[3:].strip(),[line]
        elif start is not None: block.append(line)
    if start is not None: blocks.append((start,title,block))
    return blocks
def parse_product_map(path: str | Path) -> list[ProductMapRecord]:
    lines=Path(path).read_text(encoding="utf-8").splitlines(); records={}
    for number,line in enumerate(lines,1):
        if not line.startswith("|") or "| ID |" in line or re.match(r"^\|\s*[-:| ]+\|$",line): continue
        cells=_table_cells(line)
        if len(cells)<5 or not _ID_RE.fullmatch(cells[0]): continue
        record_id,title,goal,original_status,dependency_text=cells[:5]
        records[record_id]={"id":record_id,"title":title,"group":group_for_id(record_id),"section":"3. Реєстр напрямів та залежностей","original_status":original_status,"normalized_status":normalize_status(original_status),"goal":goal,"dependencies":[x.strip() for x in dependency_text.split(",") if x.strip()],"description":"","acceptance_criteria":"","decisions":[],"source_lines":[number]}
    for start,title,block in _section_blocks(lines):
        ids=set(_ID_RE.findall(title))
        if not ids: continue
        text=re.sub(r"\n{3,}","\n\n","\n".join(block[1:]).strip())
        match=re.search(r"\*\*Критерії приймання:\*\*\s*(.*?)(?=\n\n|\Z)",text,re.S)
        for record_id in ids:
            record=records.get(record_id)
            if record is None: continue
            record["description"]=text; record["acceptance_criteria"]=match.group(1).strip() if match else ""; record["source_lines"].extend(range(start,start+len(block)))
    for number,line in enumerate(lines,1):
        if not line.startswith("|"): continue
        cells=_table_cells(line)
        if len(cells)<4 or not cells[0].startswith("2026-"): continue
        for record_id in _ID_RE.findall(cells[1]):
            if record_id in records: records[record_id]["decisions"].append(cells[2]); records[record_id]["source_lines"].append(number)
    for record in records.values(): record["source_lines"]=sorted(set(record["source_lines"]))
    return list(records.values())

def filter_product_map_records(records: list[ProductMapRecord], query: str = "", status: str = "Усі") -> list[ProductMapRecord]:
    normalized_query = query.strip().casefold()
    visible: list[ProductMapRecord] = []
    for record in records:
        if status != "Усі" and str(record["normalized_status"]) != status:
            continue
        searchable = " ".join(
            [
                str(record["id"]), str(record["title"]), str(record["group"]),
                str(record["normalized_status"]), str(record["original_status"]),
                str(record["goal"]), " ".join(str(item) for item in record["dependencies"]),
                str(record["description"]), str(record["acceptance_criteria"]),
                " ".join(str(item) for item in record["decisions"]),
            ]
        ).casefold()
        if normalized_query and normalized_query not in searchable:
            continue
        visible.append(record)
    return visible
def summarize_product_map_records(records: list[ProductMapRecord]) -> dict[str, int]:
    counts = {"total": 0, "DONE": 0, "IN PROGRESS": 0, "PLANNED": 0, "BLOCKED": 0, "BASE": 0, "V2": 0, "IDEA": 0, "UNKNOWN": 0}
    for record in records:
        status = str(record["normalized_status"])
        counts["total"] += 1
        counts[status] = counts.get(status, 0) + 1
    counts["progress"] = round((counts["DONE"] / counts["total"]) * 100) if counts["total"] else 0
    return counts