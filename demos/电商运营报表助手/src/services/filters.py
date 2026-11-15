# -*- coding: utf-8 -*-
# 筛选条件
# 作用：解析日期、款号、链接和标签，形成页面与查询共用的筛选对象。
"""全局筛选条件（）。

日期区间 / 店铺 / 品类 / 款 / 链接（多值） / 只看主推 / 标签（多选） / 数据范围。
数据范围：全店 / 指定运营 / 仅我的链接（演示操作人固定，不做账号体系）。
筛选通过 URL 查询参数在页面之间传递；默认视图为近 7 天。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import config
from src.services import my_links as my_links_store

_ITEM_SPLIT = re.compile(r"[,，\s，;；]+")


# parse_item_ids
# 作用：链接 ID 支持英文逗号 / 中文逗号 / 换行 / 空格分隔，去重去空。
def parse_item_ids(text: str | None) -> list[str]:
    """链接 ID 支持英文逗号 / 中文逗号 / 换行 / 空格分隔，去重去空。"""
    if not text:
        return []
    parts = [part.strip() for part in _ITEM_SPLIT.split(str(text))]
    seen = set()
    result = []
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            result.append(part)
    return result


# _parse_date
# 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
def _parse_date(text: str | None, fallback: date) -> date:
    if not text:
        return fallback
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return fallback


# _resolve_owner
# 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
def _resolve_owner(scope: str, owner: str) -> str:
    if not scope or scope == config.DATA_SCOPE_ALL:
        return ""
    if scope == config.DATA_SCOPE_MINE:
        return config.DEMO_OPERATOR
    if scope.startswith(config.DATA_SCOPE_OWNER_PREFIX):
        return scope[len(config.DATA_SCOPE_OWNER_PREFIX):] or owner
    return owner or ""


# Filters 数据对象
# 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
@dataclass
class Filters:
    start: str = ""
    end: str = ""
    shop_id: str = ""
    category_l2: str = ""
    style_code: str = ""
    item_ids: list[str] = field(default_factory=list)
    primary_only: bool = False
    tags: list[str] = field(default_factory=list)
    scope: str = config.DATA_SCOPE_ALL
    owner: str = ""
    my_links_only: bool = True
    my_links_ids: list[str] = field(default_factory=list, repr=False)

    # __post_init__
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def __post_init__(self):
        default_start = config.END_DATE - timedelta(days=config.DEFAULT_WINDOW_DAYS - 1)
        start = _parse_date(self.start, default_start)
        end = _parse_date(self.end, config.END_DATE)
        if end > config.END_DATE:
            end = config.END_DATE
        if start > end:
            start, end = end, start
        self.start = start.strftime("%Y-%m-%d")
        self.end = end.strftime("%Y-%m-%d")
        self.item_ids = [item for item in dict.fromkeys(self.item_ids or []) if item]
        allowed_tags = set(config.TAG_OPTIONS) | {"未打标"}
        self.tags = [tag for tag in dict.fromkeys(self.tags or [])
                     if tag in allowed_tags]
        if not self.scope:
            self.scope = config.DATA_SCOPE_ALL
        self.owner = _resolve_owner(self.scope, self.owner)
        self.my_links_ids = my_links_store.get_ids() if self.my_links_only else []

    # ---------------------------------------------------------------- 参数
    # from_request_args
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @classmethod
    def from_request_args(cls, args) -> "Filters":
        item_text = args.get("item", "") or ""
        tag_arg = args.get("tag", "")
        tags = []
        if tag_arg:
            if tag_arg in config.TAG_OPTIONS or tag_arg == "未打标":
                tags = [tag_arg]
        else:
            tags = [tag for tag in args.getlist("tags")
                    if tag in config.TAG_OPTIONS or tag == "未打标"]
        scope = args.get("scope", "") or config.DATA_SCOPE_ALL
        return cls(
            start=args.get("start", "") or "",
            end=args.get("end", "") or "",
            shop_id=args.get("shop", "") or "",
            category_l2=args.get("category", "") or "",
            style_code=args.get("style", "") or "",
            item_ids=parse_item_ids(item_text),
            primary_only=args.get("primary") in ("1", "on", "true"),
            tags=tags,
            scope=scope,
            owner=args.get("owner", "") or "",
        )

    # item_id
    # 作用：兼容单链接用法：返回单个 ID 或逗号拼接文本（仅用于展示）。
    @property
    def item_id(self) -> str:
        """兼容单链接用法：返回单个 ID 或逗号拼接文本（仅用于展示）。"""
        return ",".join(self.item_ids)

    # item_ids_input
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def item_ids_input(self) -> str:
        return ",".join(self.item_ids)

    # owner_scope_active
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def owner_scope_active(self) -> bool:
        return bool(self.owner)

    # ---------------------------------------------------------------- URL
    # _pairs
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def _pairs(self) -> list[tuple[str, str]]:
        pairs = [("start", self.start), ("end", self.end)]
        if self.shop_id:
            pairs.append(("shop", self.shop_id))
        if self.category_l2:
            pairs.append(("category", self.category_l2))
        if self.style_code:
            pairs.append(("style", self.style_code))
        for item in self.item_ids:
            pairs.append(("item", item))
        if self.primary_only:
            pairs.append(("primary", "1"))
        for tag in self.tags:
            pairs.append(("tags", tag))
        if self.scope != config.DATA_SCOPE_ALL:
            pairs.append(("scope", self.scope))
            if self.scope.startswith(config.DATA_SCOPE_OWNER_PREFIX) and self.owner:
                pairs.append(("owner", self.owner))
        return pairs

    # to_query
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def to_query(self) -> str:
        return urlencode(self._pairs(), doseq=True)

    # with_query
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def with_query(self, path: str, **overrides) -> str:
        pairs = self._pairs()
        if "tags" in overrides:
            tags = overrides.pop("tags")
            pairs = [pair for pair in pairs if pair[0] != "tags"]
            for tag in (tags or []):
                pairs.append(("tags", tag))
        if "item" in overrides:
            item_value = overrides.pop("item")
            pairs = [pair for pair in pairs if pair[0] != "item"]
            for item in parse_item_ids(item_value):
                pairs.append(("item", item))
        filters = {
            "start": "start", "end": "end", "shop": "shop",
            "category": "category", "style": "style",
            "primary": "primary", "scope": "scope", "owner": "owner",
        }
        for key, value in overrides.items():
            if key not in filters:
                continue
            pairs = [pair for pair in pairs if pair[0] != key]
            if value not in ("", None, False):
                pairs.append((key, str(value)))
        # 数据范围为全店时清理 owner
        scope_values = [value for key, value in pairs if key == "scope"]
        if not scope_values or scope_values[-1] == config.DATA_SCOPE_ALL:
            pairs = [pair for pair in pairs if pair[0] not in ("scope", "owner")]
        query = urlencode(pairs, doseq=True)
        return f"{path}?{query}" if query else path

    # ---------------------------------------------------------------- 条件
    # _tag_clauses
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def _tag_clauses(self, alias: str) -> tuple[list[str], list]:
        clauses: list[str] = []
        params: list = []
        if self.tags:
            parts = []
            for tag in self.tags:
                if tag == "未打标":
                    parts.append("(lt.tag IS NULL OR lt.tag = '')")
                else:
                    parts.append("lt.tag = ?")
                    params.append(tag)
            clauses.append(
                f"EXISTS (SELECT 1 FROM link_tags lt WHERE lt.shop_id = {alias}.shop_id "
                f"AND lt.item_id = {alias}.item_id AND (" + " OR ".join(parts) + "))")
        return clauses, params

    # _owner_clauses
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def _owner_clauses(self, alias: str, direct_mapping: bool = False) -> tuple[list[str], list]:
        if not self.owner:
            return [], []
        if direct_mapping:
            return [f"{alias}.owner = ?"], [self.owner]
        return [
            f"EXISTS (SELECT 1 FROM dim_item_mapping dm WHERE dm.shop_id = {alias}.shop_id "
            f"AND dm.item_id = {alias}.item_id AND dm.owner = ?)"
        ], [self.owner]

    # _item_clause
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def _item_clause(self, alias: str) -> tuple[str | None, list]:
        if not self.item_ids:
            return None, []
        marks = ",".join(["?"] * len(self.item_ids))
        return f"{alias}.item_id IN ({marks})", list(self.item_ids)

    # _my_links_clause
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def _my_links_clause(self, alias: str) -> tuple[str | None, list]:
        if not self.my_links_only:
            return None, []
        if not self.my_links_ids:
            return "1 = 0", []
        marks = ",".join(["?"] * len(self.my_links_ids))
        return f"{alias}.item_id IN ({marks})", list(self.my_links_ids)

    # wide_where
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def wide_where(self, alias: str = "w") -> tuple[str, list]:
        clauses = [f"{alias}.stat_date BETWEEN ? AND ?"]
        params: list = [self.start, self.end]
        if self.shop_id:
            clauses.append(f"{alias}.shop_id = ?")
            params.append(self.shop_id)
        if self.category_l2:
            clauses.append(f"{alias}.category_l2 = ?")
            params.append(self.category_l2)
        if self.style_code:
            clauses.append(f"{alias}.style_code = ?")
            params.append(self.style_code)
        if self.primary_only:
            clauses.append(f"{alias}.is_primary = 1")
        locked_clause, locked_params = self._my_links_clause(alias)
        if locked_clause:
            clauses.append(locked_clause)
            params.extend(locked_params)
        item_clause, item_params = self._item_clause(alias)
        if item_clause:
            clauses.append(item_clause)
            params.extend(item_params)
        tag_clauses, tag_params = self._tag_clauses(alias)
        clauses.extend(tag_clauses)
        params.extend(tag_params)
        owner_clauses, owner_params = self._owner_clauses(alias)
        clauses.extend(owner_clauses)
        params.extend(owner_params)
        return " AND ".join(clauses), params

    # order_where
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def order_where(self, alias: str = "o") -> tuple[str, list]:
        clauses = [f"{alias}.stat_date BETWEEN ? AND ?"]
        params: list = [self.start, self.end]
        if self.shop_id:
            clauses.append(f"{alias}.shop_id = ?")
            params.append(self.shop_id)
        item_clause, item_params = self._item_clause(alias)
        if item_clause:
            clauses.append(item_clause)
            params.extend(item_params)
        tag_clauses, tag_params = self._tag_clauses(alias)
        clauses.extend(tag_clauses)
        params.extend(tag_params)
        owner_clauses, owner_params = self._owner_clauses(alias)
        clauses.extend(owner_clauses)
        params.extend(owner_params)
        return " AND ".join(clauses), params

    # mapping_where
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def mapping_where(self, alias: str = "m") -> tuple[str, list]:
        clauses, params = [], []
        if self.shop_id:
            clauses.append(f"{alias}.shop_id = ?")
            params.append(self.shop_id)
        if self.category_l2:
            clauses.append(f"{alias}.category_l2 = ?")
            params.append(self.category_l2)
        if self.style_code:
            clauses.append(f"{alias}.style_code = ?")
            params.append(self.style_code)
        if self.primary_only:
            clauses.append(f"{alias}.is_primary = 1")
        locked_clause, locked_params = self._my_links_clause(alias)
        if locked_clause:
            clauses.append(locked_clause)
            params.extend(locked_params)
        item_clause, item_params = self._item_clause(alias)
        if item_clause:
            clauses.append(item_clause)
            params.extend(item_params)
        tag_clauses, tag_params = self._tag_clauses(alias)
        clauses.extend(tag_clauses)
        params.extend(tag_params)
        owner_clauses, owner_params = self._owner_clauses(alias, direct_mapping=True)
        clauses.extend(owner_clauses)
        params.extend(owner_params)
        return (" AND ".join(clauses), params) if clauses else ("1 = 1", [])

    # ---------------------------------------------------------------- 展示
    # label
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def label(self) -> str:
        return f"{self.start} ~ {self.end}"

    # days
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def days(self) -> int:
        d0 = datetime.strptime(self.start, "%Y-%m-%d").date()
        d1 = datetime.strptime(self.end, "%Y-%m-%d").date()
        return (d1 - d0).days + 1

    # previous
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    def previous(self) -> "Filters":
        d0 = datetime.strptime(self.start, "%Y-%m-%d").date()
        d1 = datetime.strptime(self.end, "%Y-%m-%d").date()
        span = (d1 - d0).days + 1
        prev_end = d0 - timedelta(days=1)
        prev_start = prev_end - timedelta(days=span - 1)
        return Filters(start=prev_start.strftime("%Y-%m-%d"),
                       end=prev_end.strftime("%Y-%m-%d"),
                       shop_id=self.shop_id, category_l2=self.category_l2,
                       style_code=self.style_code, item_ids=list(self.item_ids),
                       primary_only=self.primary_only, tags=list(self.tags),
                       scope=self.scope, owner=self.owner,
                       my_links_only=self.my_links_only)


    # ---------------------------------------------------------------- 日期可见性
    # short_start
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def short_start(self) -> str:
        return datetime.strptime(self.start, "%Y-%m-%d").strftime("%m/%d")

    # short_end
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def short_end(self) -> str:
        return datetime.strptime(self.end, "%Y-%m-%d").strftime("%m/%d")

    # short_range
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def short_range(self) -> str:
        return f"{self.short_start}-{self.short_end}（{self.days}天）"

    # compare_label
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def compare_label(self) -> str:
        prev = self.previous()
        return f"{prev.short_start}~{prev.short_end}"

    # compare_full_label
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def compare_full_label(self) -> str:
        prev = self.previous()
        return f"{prev.start} ~ {prev.end}"

    # scope_label
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def scope_label(self) -> str:
        if self.my_links_only:
            return f"我的链接池（{len(self.my_links_ids)} 条）"
        if self.owner:
            if self.scope == config.DATA_SCOPE_MINE:
                return f"仅我的链接（{self.owner}）"
            return f"指定运营：{self.owner}"
        return "全部链接"

    # is_full_range
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def is_full_range(self) -> bool:
        return (self.start == config.START_DATE.strftime("%Y-%m-%d")
                and self.end == config.END_DATE.strftime("%Y-%m-%d"))

    # date_switched
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def date_switched(self) -> bool:
        default_start = (config.END_DATE - timedelta(
            days=config.DEFAULT_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")
        return (self.start != default_start
                or self.end != config.END_DATE.strftime("%Y-%m-%d"))

    # scope_parts
    # 作用：完成筛选条件中的该步骤，结果交给调用方继续使用。
    @property
    def scope_parts(self) -> list[tuple[str, str]]:
        parts = [("全店", None)]
        if self.shop_id:
            parts.append((config.shop_display(self.shop_id), "shop"))
        if self.category_l2:
            parts.append((self.category_l2, "category"))
        if self.style_code:
            parts.append((self.style_code, "style"))
        if self.item_ids:
            label = self.item_ids[0] if len(self.item_ids) == 1 else f"{len(self.item_ids)} 个链接"
            parts.append((label, "item"))
        if self.primary_only:
            parts.append(("仅主推", "primary"))
        if self.tags:
            parts.append(("标签：" + " / ".join(self.tags), "tags"))
        if self.owner:
            parts.append(("数据范围：" + self.owner, "owner"))
        return parts
