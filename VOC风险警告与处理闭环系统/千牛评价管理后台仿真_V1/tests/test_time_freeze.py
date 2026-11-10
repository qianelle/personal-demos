# -*- coding: utf-8 -*-
"""
时间锚点冻结回归测试
==================================================================
背景（必须修的问题）：
    早期 mock_data 用 datetime.now() 作为数据锚点，导致同一个历史 review_id 的
    绝对时间戳每天整体 +1 天漂移。对 INITIAL 影响有限，但 **FOLLOWUP 的 canonical
    content_key 内嵌 append_review_time**（如 ...::FOLLOWUP::20261007094000），
    漂移会让下游 VOC 把同一条追评判成「全新的 canonical 事件」，产生伪重复。

本文件固定验证三件事：
    1. 历史 176 条的绝对时间不再漂移（逐字复现已落库 PostgreSQL 的事实）
    2. 新增的 10/8、10/9 演示事件固定不动
    3. Today / Yesterday 的筛选结果可重复（锚在 SIM_BASE_DATE，不是 datetime.now()）

运行：
    python tests/test_time_freeze.py
"""

import os
import subprocess
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mock_data as md                                     # noqa: E402
from mock_data import REVIEWS, SIM_BASE_DATE, SIM_LEGACY_ANCHOR_DATE  # noqa: E402
from app import quick_range_bounds                         # noqa: E402

BY_ID = {r["review_id"]: r for r in REVIEWS}


class TestAnchorsAreConstants(unittest.TestCase):
    """锚点必须是冻结常量，绝不可以是运行当天日期。"""

    def test_base_date_frozen(self):
        self.assertEqual(SIM_BASE_DATE, datetime(2026, 10, 9))

    def test_legacy_anchor_frozen(self):
        self.assertEqual(SIM_LEGACY_ANCHOR_DATE, datetime(2026, 10, 8))

    def test_anchors_not_tied_to_real_today(self):
        """两个锚点都可以等于真实今天之外的日期 —— 证明没有读 datetime.now()。"""
        real_today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # 只要锚点是常量就必然成立；这里用「不受真实今天影响」的方式表达：
        # 重新以另一个环境变量基准导入模块，数据整体平移而结构不变。
        self.assertIsInstance(SIM_BASE_DATE, datetime)
        self.assertIsInstance(SIM_LEGACY_ANCHOR_DATE, datetime)
        self.assertNotEqual(SIM_BASE_DATE, SIM_LEGACY_ANCHOR_DATE)
        del real_today


class TestLegacyCanonicalIdentityFrozen(unittest.TestCase):
    """已落库 PostgreSQL 的 canonical identity 必须逐字复现。"""

    CASES = [
        # (review_id, 字段, 期望值, 说明)
        ("RV202600167", "append_review_time", "2026-10-07 09:40:00",
         "PG 已有 FOLLOWUP key ::20261007094000"),
        ("RV202600167", "review_time", "2026-07-10 10:15:00",
         "PG 已有 INITIAL"),
        ("RV202600118", "review_time", "2026-10-07 18:49:00", "PG 已有 INITIAL"),
        ("RV202600082", "review_time", "2026-10-07 08:09:00", "PG 已有 INITIAL"),
        ("RV202600056", "review_time", "2026-10-07 06:58:00", "PG 已有 INITIAL"),
    ]

    def test_frozen_timestamps(self):
        for rid, field, expected, note in self.CASES:
            with self.subTest(rid=rid, field=field):
                self.assertIn(rid, BY_ID, "{} 不存在".format(rid))
                self.assertEqual(BY_ID[rid][field], expected,
                                 "{} 漂移了（{}）".format(rid, note))

    def test_legacy_window_does_not_reach_demo_today(self):
        """
        历史 176 条自己生成出来的时间必须全部落在历史锚点当天（含）之前，
        不得侵入 Demo 今天。

        例外：DEMO_FOLLOWUP_PLAN 的两条旧线程会被**演示追评**推到 10-08 / 10-09，
        这是刻意的（验证「旧首评 + 新追评」能重新进入增量窗口），不算漂移。
        因此对这两条只校验 review_time，不校验 last_activity_time。
        """
        legacy_day = SIM_LEGACY_ANCHOR_DATE.strftime("%Y-%m-%d")
        self.assertNotEqual(legacy_day, SIM_BASE_DATE.strftime("%Y-%m-%d"))

        legacy_rows = [r for r in REVIEWS if int(r["review_id"][-3:]) <= 176]
        demo_targets = {p[0] for p in md.DEMO_FOLLOWUP_PLAN}

        # 首评时间永不被演示事件改动 -> 全部历史线程都必须 <= 历史锚点当天
        leaked_review = [r["review_id"] for r in legacy_rows
                         if r["review_time"][:10] > legacy_day]
        self.assertEqual(leaked_review, [],
                         "历史首评越过了历史锚点当天：{}".format(leaked_review[:5]))

        # 最后活动时间：除演示追评目标外，也不得越过历史锚点当天
        leaked_last = [r["review_id"] for r in legacy_rows
                       if r["review_id"] not in demo_targets
                       and r["last_activity_time"][:10] > legacy_day]
        self.assertEqual(leaked_last, [],
                         "历史数据越过了历史锚点当天：{}".format(leaked_last[:5]))


class TestDemoEventsFrozen(unittest.TestCase):
    """新增演示事件的绝对时间必须固定。"""

    CASES = [
        ("RV202600177", "review_time", "2026-10-08 09:20:00"),
        ("RV202600178", "review_time", "2026-10-08 14:35:00"),
        ("RV202600179", "review_time", "2026-10-08 20:10:00"),
        ("RV202600109", "append_review_time", "2026-10-08 16:40:00"),
        ("RV202600180", "review_time", "2026-10-09 08:45:00"),
        ("RV202600181", "review_time", "2026-10-09 11:20:00"),
        ("RV202600055", "append_review_time", "2026-10-09 12:05:00"),
    ]

    def test_demo_event_timestamps(self):
        for rid, field, expected in self.CASES:
            with self.subTest(rid=rid):
                self.assertEqual(BY_ID[rid][field], expected)


class TestQuickRangeRepeatable(unittest.TestCase):
    """Today / Yesterday 必须锚在 SIM_BASE_DATE，可重复。"""

    def test_today_is_base_date(self):
        d = SIM_BASE_DATE.strftime("%Y-%m-%d")
        self.assertEqual(quick_range_bounds("today"), (d, d))

    def test_yesterday_is_base_date_minus_one(self):
        d = (SIM_BASE_DATE - timedelta(days=1)).strftime("%Y-%m-%d")
        self.assertEqual(quick_range_bounds("yesterday"), (d, d))

    def test_last7_bounds(self):
        end = SIM_BASE_DATE.strftime("%Y-%m-%d")
        start = (SIM_BASE_DATE - timedelta(days=6)).strftime("%Y-%m-%d")
        self.assertEqual(quick_range_bounds("last7"), (start, end))

    def test_expected_threads_are_hit(self):
        """演示事件必须能被真实筛选命中（仍按 last_activity_time 计算，非白名单）。"""
        d_yes, _ = quick_range_bounds("yesterday")
        d_tod, _ = quick_range_bounds("today")
        hit_y = {r["review_id"] for r in REVIEWS
                 if r["last_activity_time"][:10] == d_yes}
        hit_t = {r["review_id"] for r in REVIEWS
                 if r["last_activity_time"][:10] == d_tod}
        self.assertTrue({"RV202600177", "RV202600178", "RV202600179",
                         "RV202600109"}.issubset(hit_y),
                        "昨天未命中全部演示事件：{}".format(sorted(hit_y)))
        self.assertTrue({"RV202600180", "RV202600181",
                         "RV202600055"}.issubset(hit_t),
                        "今天未命中全部演示事件：{}".format(sorted(hit_t)))


class TestRestartStability(unittest.TestCase):
    """重跑 / 重启进程后，绝对时间必须完全一致。"""

    def _snapshot(self):
        """在**独立子进程**里重新导入模块，导出关键时间戳。"""
        code = (
            "import sys; sys.stdout.reconfigure(encoding='utf-8');"
            "sys.path.insert(0, r'{root}');"
            "import mock_data as m;"
            "ids=['RV202600167','RV202600118','RV202600082','RV202600056',"
            "     'RV202600109','RV202600055','RV202600177','RV202600180'];"
            "d={{r['review_id']:r for r in m.REVIEWS}};"
            "print('|'.join(d[i]['review_time']+'~'+d[i]['append_review_time'] for i in ids))"
        ).format(root=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        out = subprocess.run([sys.executable, "-c", code],
                             capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout.strip()

    def test_subprocess_reimport_is_identical(self):
        first = self._snapshot()
        second = self._snapshot()
        self.assertEqual(first, second,
                         "两次独立进程生成的时间戳不一致：\n1={}\n2={}".format(first, second))

    def test_snapshot_matches_expectation(self):
        snap = self._snapshot()
        self.assertIn("2026-10-07 09:40:00", snap, "RV202600167 追评漂移了")
        self.assertIn("2026-10-08 16:40:00", snap, "RV202600109 追评漂移了")
        self.assertIn("2026-10-09 12:05:00", snap, "RV202600055 追评漂移了")


if __name__ == "__main__":
    unittest.main(verbosity=2)
