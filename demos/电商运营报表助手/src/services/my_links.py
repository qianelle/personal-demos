# -*- coding: utf-8 -*-
# 链接池
# 作用：读写三个模块共享的链接池文件，维护链接范围。
""" 我的链接池（全局共享查询范围）。

初始 = 单店全量在售链接（约 219 条）；由左侧导航「设置我的链接池」弹窗整体编辑。
集合保存在 data/my_links.json，不参与清洗脚本与宽表生成；查询层统一按 item_id 过滤。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config

_STRUCTURE_VERSION = 2


# _path
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def _path() -> Path:
    return Path(config.MY_LINKS_FILE)


# _load_raw
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def _load_raw() -> dict:
    path = _path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


# _write_raw
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def _write_raw(data: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


# _normalize_items
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def _normalize_items(items) -> list[str]:
    result = []
    seen = set()
    for raw in items or []:
        if isinstance(raw, dict):
            item_id = str(raw.get("item_id") or "").strip()
        else:
            item_id = str(raw or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)
    return result


# load_items
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def load_items() -> list[dict]:
    return [{"item_id": item_id} for item_id in get_ids()]


# get_ids
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def get_ids() -> list[str]:
    return _normalize_items(_load_raw().get("items"))


# get_owner_map
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def get_owner_map() -> dict[str, str | None]:
    return {item_id: None for item_id in get_ids()}


# count
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def count() -> int:
    return len(get_ids())


# all_on_sale_ids
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def all_on_sale_ids(conn) -> list[str]:
    return [row[0] for row in conn.execute(
        "SELECT item_id FROM dim_item_mapping WHERE item_status='在售' ORDER BY item_id")]


# ensure_seeded
# 作用：首次运行：链接池初始写入全量在售链接。
def ensure_seeded(conn) -> int:
    """首次运行：链接池初始写入全量在售链接。"""
    data = _load_raw()
    if data.get("items") is not None:
        return len(_normalize_items(data.get("items")))
    items = all_on_sale_ids(conn)
    _write_raw({"structure_version": _STRUCTURE_VERSION,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_by": "演示环境", "items": items})
    return len(items)


# _append_log
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def _append_log(action: str, added: int, removed: int,
                missing: list[str], total: int) -> None:
    path = Path(config.MY_LINKS_LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "# 链接池变更日志\n\n"
            "记录「我的链接池」整体编辑；不修改源数据、宽表与链接状态。\n\n",
            encoding="utf-8")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    missing_text = "、".join(missing) if missing else "无"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"## {now} 演示环境 {action}\n\n")
        fh.write(f"- 成功：{added} 条\n- 移除：{removed} 条\n"
                 f"- 未找到：{missing_text}\n- 当前链接池：{total} 条\n\n")


# validate_on_sale
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def validate_on_sale(conn, item_ids: list[str]) -> tuple[list[str], list[str]]:
    ids = [str(item).strip() for item in dict.fromkeys(item_ids or []) if str(item).strip()]
    if not ids:
        return [], []
    marks = ",".join(["?"] * len(ids))
    valid = {row[0] for row in conn.execute(
        f"SELECT item_id FROM dim_item_mapping WHERE item_status = '在售' "
        f"AND item_id IN ({marks})", ids)}
    return [item for item in ids if item in valid], [item for item in ids if item not in valid]


# replace_items
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def replace_items(conn, item_ids: list[str]) -> dict:
    found, missing = validate_on_sale(conn, item_ids)
    old = set(get_ids())
    new = list(dict.fromkeys(found))
    _write_raw({"structure_version": _STRUCTURE_VERSION,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_by": "演示环境", "items": new})
    _append_log("设置我的链接池", len(new), len(old - set(new)), missing, len(new))
    return {"ok": len(found), "missing": missing, "total": len(new)}


# load_all_on_sale
# 作用：完成链接池中的该步骤，结果交给调用方继续使用。
def load_all_on_sale(conn) -> dict:
    ids = all_on_sale_ids(conn)
    _write_raw({"structure_version": _STRUCTURE_VERSION,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_by": "演示环境", "items": ids})
    _append_log("载入本店全部链接", len(ids), 0, [], len(ids))
    return {"ok": len(ids), "missing": [], "total": len(ids)}


# remove_items
# 作用：保留兼容：移除池内 ID（页面不再提供入口）。
def remove_items(item_ids: list[str]) -> dict:
    """保留兼容：移除池内 ID（页面不再提供入口）。"""
    remove = {str(item).strip() for item in item_ids or [] if str(item).strip()}
    old = get_ids()
    kept = [item for item in old if item not in remove]
    _write_raw({"structure_version": _STRUCTURE_VERSION,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_by": "演示环境", "items": kept})
    return {"removed": len(old) - len(kept), "total": len(kept)}
