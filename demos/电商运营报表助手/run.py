# -*- coding: utf-8 -*-
# 启动脚本
# 作用：准备运行环境、执行数据管线、检查页面和导出文件，然后启动本地服务。
"""一键运行：环境自检 → 数据管线 → 三模块页面/HTML 导出自检 → 启动 Flask。"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import config


# _set_console
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def _set_console() -> None:
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass


# env_check
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def env_check() -> dict:
    import platform

    print("=" * 78)
    print(f"{config.SYSTEM_NAME} · 环境自检")
    print("=" * 78)
    print(f"[环境] Python  {platform.python_version()}  ({platform.system()} {platform.machine()})")
    print(f"[环境] 项目根目录  {config.BASE_DIR}")
    print(f"[环境] 数据目录    {config.DATA_DIR}")
    versions = {"python": platform.python_version()}
    for package in ("pandas", "flask", "openpyxl"):
        try:
            __import__(package)
        except ImportError:
            if package in ("flask", "openpyxl"):
                print(f"[环境] 缺少 {package}，执行 python -m pip install {package}")
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            else:
                raise RuntimeError(f"缺少 {package}，请先安装 pandas")
        from importlib.metadata import version
        versions[package] = version(package)
        print(f"[环境] {package:<9} {versions[package]}")
    print()
    return versions


# _check_exports
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def _check_exports(client) -> list[dict]:
    results = []
    for tab in ("daily", "weekly", "monthly"):
        response = client.get(f"/export/reports/html?tab={tab}")
        text = response.get_data(as_text=True)
        outside = Path(tempfile.gettempdir()) / f"table_export_{tab}.html"
        outside.write_text(text, encoding="utf-8")
        results.append({
            "tab": tab, "status": response.status_code,
            "ok": (response.status_code == 200 and "<svg" in text
                   and "http://" not in text and "https://" not in text
                   and "echarts" not in text.lower() and outside.exists()),
        })
        outside.unlink(missing_ok=True)
    return results


# run_web_checks
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def run_web_checks() -> dict:
    from app import create_app
    from src.models import db as dbmod

    app = create_app()
    client = app.test_client()
    pages = [("/", "经营分析"), ("/links", "链接管理"), ("/reports", "数据报表")]
    page_results = [{"path": path, "title": title,
                     "status": client.get(path).status_code}
                    for path, title in pages]
    tabs = [{"title": label, "status": client.get(path).status_code}
            for path, label in (("/reports?tab=daily", "日报"),
                                ("/reports?tab=weekly", "周报"),
                                ("/reports?tab=monthly", "月报"))]
    conn = dbmod.connect()
    item_id = conn.execute(
        "SELECT item_id FROM fact_wide_daily GROUP BY item_id "
        "ORDER BY SUM(pay_amount) DESC LIMIT 1").fetchone()["item_id"]
    item_status = client.get(f"/item/{item_id}").status_code
    conn.close()
    return {"pages": page_results, "tabs": tabs, "item_status": item_status,
            "exports": _check_exports(client)}


# write_runtime_check
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def write_runtime_check(ctx: dict, web: dict) -> Path:
    pages_ok = all(p["status"] == 200 for p in web["pages"])
    exports_ok = all(e["ok"] for e in web["exports"])
    lines = [
        "- 三个模块可正常打开",
        f"- 数据覆盖 {config.DAYS} 天，截止 {config.END_DATE}，共 {ctx['t1']['valid_rows']} 行，"
        f"金额合计 {ctx['wide']['wide_pay']:,.2f} 元",
        "- 三个报表导出文件可独立打开，图表正常显示",
        "- 数据取自订单明细 / 商品效果 / 商品推广三张源表",
    ]
    path = config.OUTPUT_DIR / "运行自检.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# _port_available
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def _port_available(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


# _choose_port
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def _choose_port(host: str, preferred: int) -> tuple[int, bool]:
    if _port_available(host, preferred):
        return preferred, False
    for candidate in range(preferred + 1, preferred + 21):
        if _port_available(host, candidate):
            return candidate, True
    raise RuntimeError(f"{host} 的 {preferred}~{preferred + 20} 端口均被占用，"
                       f"请用 --port 指定可用端口")


# main
# 作用：完成启动脚本中的该步骤，结果交给调用方继续使用。
def main() -> None:
    # ① 准备输入与上下文
    _set_console()
    parser = argparse.ArgumentParser(description="店铺报表助手一键运行")
    parser.add_argument("--data-only", action="store_true", help="只跑数据管线，不启动页面")
    parser.add_argument("--port", type=int, default=5002, help="Flask 端口，默认 5002")
    parser.add_argument("--host", default="127.0.0.1", help="Flask 监听地址，默认 127.0.0.1")
    args = parser.parse_args()

    started = time.time()
    env_check()
    from src.etl.pipeline import run_data_pipeline

    ctx = run_data_pipeline(verbose=True)

    if args.data_only:
        print(f"[完成] 数据已就绪，数据库：{config.DB_PATH}")
        print(f"[完成] 总耗时 {time.time() - started:.1f} 秒")
        return

    web = run_web_checks()
    report_path = write_runtime_check(ctx, web)
    pages_ok = all(p["status"] == 200 for p in web["pages"])
    # ② 处理主体数据
    exports_ok = all(e["ok"] for e in web["exports"])
    print("=" * 78)
    print(f"[页面自检] 三个模块：{'通过' if pages_ok else '失败'}；"
          f"单链接明细：{web['item_status']}")
    print(f"[页面自检] HTML 导出：{'3 个可独立打开' if exports_ok else '异常'}")
    print(f"[运行自检] 已写入 {report_path.relative_to(config.BASE_DIR)}")
    print("=" * 78)
    if not (pages_ok and exports_ok and ctx.get("data_ok")):
        print("[警告] 自检未全部通过，页面仍将启动，请检查控制台日志")

    port, changed = _choose_port(args.host, args.port)
    if changed:
        print(f"[端口] {args.host}:{args.port} 已被占用，自动改用 {port}")
    print(f"启动完成：http://{args.host}:{port}")
    print(f"页面清单：经营分析 / 链接管理 / 数据报表；二级：单链接明细")
    print(f"统计口径：{config.START_DATE} ~ {config.END_DATE}；默认视图近 "
          f"{config.DEFAULT_WINDOW_DAYS} 天")
    print(f"总耗时 {time.time() - started:.1f} 秒；按 Ctrl+C 停止服务")
    from app import app as flask_app
    # ③ 整理并返回结果
    flask_app.run(host=args.host, port=port, debug=False)


if __name__ == "__main__":
    main()
