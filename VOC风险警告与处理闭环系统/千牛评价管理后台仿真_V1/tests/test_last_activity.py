# -*- coding: utf-8 -*-
"""
增量巡检自动化测试
==================================================================
覆盖需求第 10 条：

    A. 无追评：last_activity_time = review_time
    B. 有追评：last_activity_time = append_review_time
    C. 旧首评 + 昨天追评：使用「昨天」筛选可以查出来
    D. 旧首评 + 非昨天追评：「昨天」筛选不会出现
    E. 页面默认排序为 last_activity_time DESC
    F. CSV 仍保持 15 字段且正常导出

外加回归项（保证本次改动没有破坏既有的 Source Schema 冻结口径）：
    G. 一行 = 一个评价线程（无独立追评行、order_id 不重复、append 两列同空同非空）
    H. 有追评时 append_review_time 严格晚于 review_time
    I. 导出内容 = 当前筛选结果；页面统计与筛选口径一致
    J. 「今天 / 昨天 / 近7天」区间边界正确

运行：
    python tests/test_last_activity.py
"""

import csv
import io
import os
import re
import sys
import unittest
from collections import Counter
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module                                   # noqa: E402
from app import app, DEMO_USERNAME, DEMO_PASSWORD          # noqa: E402
from mock_data import REVIEWS, CSV_FIELDS, SIM_BASE_DATE   # noqa: E402

PAGE = 100


def today_str():
    """后台的「今天」锚在 Demo 时钟 SIM_BASE_DATE，不是 datetime.now()。"""
    return SIM_BASE_DATE.strftime("%Y-%m-%d")


def day_offset_str(days):
    return (SIM_BASE_DATE - timedelta(days=days)).strftime("%Y-%m-%d")


def login_client():
    c = app.test_client()
    resp = c.post("/login", data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
                  follow_redirects=True)
    assert resp.status_code == 200, "登录失败"
    return c


def csv_rows(client, query):
    """请求 /export 并解析成 dict 列表；同时返回原始文本与表头。"""
    resp = client.get("/export?" + query)
    assert resp.status_code == 200, "导出失败：{}".format(resp.status_code)
    text = resp.data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    table = list(reader)
    header, body = table[0], table[1:]
    rows = [dict(zip(header, r)) for r in body]
    return header, rows, text


def page_review_ids(client, query):
    """抓取页面里按顺序出现的 review_id。"""
    ids = []
    page = 1
    while True:
        resp = client.get("/reviews?" + query + "&size={}&page={}".format(PAGE, page))
        assert resp.status_code == 200
        html = resp.data.decode("utf-8")
        found = re.findall(r'data-review-id="([^"]+)"', html)
        if not found:
            break
        ids.extend(found)
        if len(found) < PAGE:
            break
        page += 1
        if page > 20:
            break
    return ids


class TestLastActivityField(unittest.TestCase):
    """A / B：last_activity_time 的取值规则"""

    def test_A_no_append_equals_review_time(self):
        bad = [r["review_id"] for r in REVIEWS
               if not r["append_review_time"]
               and r["last_activity_time"] != r["review_time"]]
        self.assertEqual([], bad, "无追评时 last_activity_time 必须等于 review_time")

    def test_B_with_append_equals_append_time(self):
        bad = [r["review_id"] for r in REVIEWS
               if r["append_review_time"]
               and r["last_activity_time"] != r["append_review_time"]]
        self.assertEqual([], bad, "有追评时 last_activity_time 必须等于 append_review_time")

    def test_field_not_in_csv(self):
        self.assertNotIn("last_activity_time", CSV_FIELDS)
        self.assertEqual(15, len(CSV_FIELDS))


class TestIncrementalFilter(unittest.TestCase):
    """C / D：按最后活动时间做增量筛选"""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = login_client()
        cls.y = day_offset_str(1)
        cls.expected_yesterday = {
            r["review_id"] for r in REVIEWS if r["last_activity_time"][:10] == cls.y
        }

    def test_yesterday_has_old_review_with_new_append(self):
        """C：存在「首评很早 + 昨天追评」的线程，且能被昨天筛选命中"""
        candidates = [r for r in REVIEWS
                      if r["append_review_time"]
                      and r["append_review_time"][:10] == self.y
                      and r["review_time"][:10] < day_offset_str(30)]
        self.assertTrue(candidates,
                        "数据中必须存在「旧首评 + 昨天追评」的样本，否则无法验证增量巡检")
        row = candidates[0]
        header, rows, _ = csv_rows(self.client, "range=yesterday")
        ids = {r["review_id"] for r in rows}
        self.assertIn(row["review_id"], ids,
                      "首评 {} 的线程，昨天({})发生追评，必须能被「昨天」筛出"
                      .format(row["review_time"], self.y))

    def test_yesterday_result_exactly_matches_last_activity(self):
        """C + D：昨天筛选的结果集必须精确等于 last_activity_time 落在昨天的线程集合"""
        header, rows, _ = csv_rows(self.client, "range=yesterday")
        ids = {r["review_id"] for r in rows}
        self.assertEqual(self.expected_yesterday, ids)

    def test_non_yesterday_append_not_selected(self):
        """D：追评不在昨天的线程，不得出现在昨天筛选结果里"""
        others = [r for r in REVIEWS
                  if r["append_review_time"] and r["append_review_time"][:10] != self.y]
        self.assertTrue(others, "数据中必须存在追评时间不是昨天的样本")
        header, rows, _ = csv_rows(self.client, "range=yesterday")
        ids = {r["review_id"] for r in rows}
        leaked = [r["review_id"] for r in others if r["review_id"] in ids]
        self.assertEqual([], leaked, "非昨天追评的线程不应出现在昨天筛选结果中")

    def test_custom_date_range_also_uses_last_activity(self):
        """自定义起止日期同样按 last_activity_time 过滤"""
        expected = {r["review_id"] for r in REVIEWS if r["last_activity_time"][:10] == self.y}
        header, rows, _ = csv_rows(
            self.client, "date_start={}&date_end={}".format(self.y, self.y))
        self.assertEqual(expected, {r["review_id"] for r in rows})

    def test_old_review_only_not_in_yesterday(self):
        """只有老首评、没有追评的线程，绝不应出现在昨天结果里"""
        old_only = [r for r in REVIEWS
                    if not r["append_review_time"] and r["review_time"][:10] < day_offset_str(30)]
        header, rows, _ = csv_rows(self.client, "range=yesterday")
        ids = {r["review_id"] for r in rows}
        leaked = [r["review_id"] for r in old_only if r["review_id"] in ids]
        self.assertEqual([], leaked)


class TestDefaultSort(unittest.TestCase):
    """E：默认排序 last_activity_time DESC"""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = login_client()

    def test_default_page_sorted_desc(self):
        ids = page_review_ids(self.client, "")
        self.assertEqual(len(REVIEWS), len(ids), "默认页应能翻完所有数据")
        times = [next(r["last_activity_time"] for r in REVIEWS if r["review_id"] == rid)
                 for rid in ids]
        self.assertEqual(sorted(times, reverse=True), times,
                         "默认排序必须是 last_activity_time 倒序")

    def test_top_row_has_max_last_activity(self):
        ids = page_review_ids(self.client, "")
        top = next(r for r in REVIEWS if r["review_id"] == ids[0])
        self.assertEqual(max(r["last_activity_time"] for r in REVIEWS),
                         top["last_activity_time"])

    def test_old_thread_with_new_append_rises_to_top_area(self):
        """首评很早但追评很新的线程，排名必须靠前（前 20%）"""
        idx = {rid: i for i, rid in enumerate(page_review_ids(self.client, ""))}
        total = len(REVIEWS)
        rising = [r for r in REVIEWS
                  if r["append_review_time"]
                  and r["review_time"][:10] < day_offset_str(30)
                  and r["append_review_time"][:10] >= day_offset_str(7)]
        self.assertTrue(rising, "缺少用于验证「老线程因追评回到顶部」的样本")
        for r in rising:
            self.assertLess(idx[r["review_id"]], total * 0.2,
                            "{} 首评 {} 但追评 {}，应排在列表前部"
                            .format(r["review_id"], r["review_time"], r["append_review_time"]))


class TestCsvExport(unittest.TestCase):
    """F：CSV 仍是 15 字段且正常导出"""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = login_client()

    def test_header_is_frozen_15_fields(self):
        header, rows, _ = csv_rows(self.client, "")
        self.assertEqual(CSV_FIELDS, header)
        self.assertEqual(15, len(header))
        for r in rows:
            self.assertEqual(15, len(r))

    def test_export_all_rows(self):
        header, rows, _ = csv_rows(self.client, "")
        self.assertEqual(len(REVIEWS), len(rows))
        self.assertEqual({r["review_id"] for r in REVIEWS}, {r["review_id"] for r in rows})

    def test_export_matches_current_filter(self):
        """需求 9：导出内容必须是当前筛选结果"""
        header, rows, _ = csv_rows(self.client, "range=yesterday")
        expected = {r["review_id"] for r in REVIEWS
                    if r["last_activity_time"][:10] == day_offset_str(1)}
        self.assertEqual(expected, {r["review_id"] for r in rows})
        for r in rows:
            last = r["append_review_time"] or r["review_time"]
            self.assertEqual(day_offset_str(1), last[:10])

    def test_bom_present(self):
        resp = self.client.get("/export?")
        self.assertTrue(resp.data.startswith(b"\xef\xbb\xbf"), "CSV 需带 UTF-8 BOM")


class TestQuickRangeBounds(unittest.TestCase):
    """J：今天 / 昨天 / 近7天 区间边界"""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = login_client()

    def _expect(self, start_off, end_off):
        lo = day_offset_str(start_off)
        hi = day_offset_str(end_off)
        return {r["review_id"] for r in REVIEWS
                if lo <= r["last_activity_time"][:10] <= hi}

    def test_today(self):
        header, rows, _ = csv_rows(self.client, "range=today")
        self.assertEqual(self._expect(0, 0), {r["review_id"] for r in rows})
        self.assertTrue(rows, "「今天」应有数据，否则快捷筛选无演示价值")

    def test_yesterday(self):
        header, rows, _ = csv_rows(self.client, "range=yesterday")
        self.assertEqual(self._expect(1, 1), {r["review_id"] for r in rows})
        self.assertTrue(rows, "「昨天」应有数据")

    def test_last7(self):
        header, rows, _ = csv_rows(self.client, "range=last7")
        self.assertEqual(self._expect(6, 0), {r["review_id"] for r in rows})
        self.assertTrue(rows, "「近7天」应有数据")
        # 边界：7 天前的线程不应被「近7天」命中
        boundary = [r["review_id"] for r in REVIEWS
                    if r["last_activity_time"][:10] == day_offset_str(7)]
        ids = {r["review_id"] for r in rows}
        self.assertEqual([], [b for b in boundary if b in ids])

    def test_quick_buttons_rendered(self):
        resp = self.client.get("/reviews")
        html = resp.data.decode("utf-8")
        for k in ("quick-today", "quick-yesterday", "quick-last7"):
            self.assertIn(k, html, "页面应渲染快捷筛选按钮 {}".format(k))


class TestSourceSchemaRegression(unittest.TestCase):
    """G / H / I：既有冻结口径回归"""

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = login_client()

    def test_one_row_per_thread(self):
        ids = [r["review_id"] for r in REVIEWS]
        self.assertEqual(len(ids), len(set(ids)))
        dup = {k: v for k, v in Counter(r["order_id"] for r in REVIEWS).items() if v > 1}
        self.assertEqual({}, dup, "同一 order_id 不得对应多行（追评不得独立成行）")
        texts = {r["review_text"] for r in REVIEWS}
        leaked = [r["append_review_text"] for r in REVIEWS
                  if r["append_review_text"] and r["append_review_text"] in texts]
        self.assertEqual([], leaked, "追评内容不得被复制成独立评价行")

    def test_append_columns_pairing(self):
        for r in REVIEWS:
            self.assertEqual((r["append_review_text"] == ""),
                             (r["append_review_time"] == ""),
                             "append 两列必须同空同非空：{}".format(r["review_id"]))

    def test_append_after_review(self):
        bad = [r["review_id"] for r in REVIEWS
               if r["append_review_time"] and r["append_review_time"] <= r["review_time"]]
        self.assertEqual([], bad, "追评时间必须严格晚于首评时间")

    def test_page_counter_matches_filter(self):
        resp = self.client.get("/reviews?range=yesterday")
        html = resp.data.decode("utf-8")
        m = re.search(r'id="result-total"[^>]*>(\d+)<', html)
        self.assertIsNotNone(m, "页面应输出筛选结果条数")
        expected = sum(1 for r in REVIEWS
                       if r["last_activity_time"][:10] == day_offset_str(1))
        self.assertEqual(expected, int(m.group(1)))

    def test_page_append_counter_matches_filter(self):
        resp = self.client.get("/reviews?range=last7")
        html = resp.data.decode("utf-8")
        m = re.search(r'id="result-append-total"[^>]*>(\d+)<', html)
        self.assertIsNotNone(m, "页面应输出筛选结果中的含追评条数")
        expected = sum(1 for r in REVIEWS
                       if r["has_append"] == "是"
                       and day_offset_str(6) <= r["last_activity_time"][:10] <= today_str())
        self.assertEqual(expected, int(m.group(1)))

    def test_append_visible_on_page(self):
        resp = self.client.get("/reviews?has_append=是")
        html = resp.data.decode("utf-8")
        self.assertIn("[追评]", html, "页面必须把追评内容明显展示出来")
        self.assertIn("cell-append-text", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
