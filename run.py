#!/usr/bin/env python3
"""
主控程序：每分钟拉取计时记录存库，然后读取全量数据计算圈数并回写。
"""

import time
from collections import defaultdict
from datetime import datetime

import fetch_records

INTERVAL = 60        # 拉取间隔（秒）
CIRCLE_GAP = 10 * 60  # 圈数分隔阈值（秒），超过此间隔则 circle +1


def calc_circles(records: list[dict]) -> list[dict]:
    """
    在内存中按芯片码分组，按 curr_time 升序计算圈数。
    规则：
      - 同一芯片的第一条记录 circle = 0
      - 后续记录与前一条时间差 <= 10分钟：circle 同前一条
      - 时间差 > 10分钟：circle = 前一条 + 1
    返回所有需要更新的记录（circle 发生变化的）。
    """
    # 按芯片分组
    by_chip = defaultdict(list)
    for r in records:
        by_chip[r["chip"]].append(r)

    # 各芯片按时间升序排序
    for chip in by_chip:
        by_chip[chip].sort(key=lambda r: r["curr_time"] or datetime.min)

    changed = []
    for chip, rows in by_chip.items():
        prev_circle = 0
        prev_time = None

        for r in rows:
            if prev_time is None:
                # 第一条，circle = 0
                new_circle = 0
            else:
                # 计算与上一条的时间差（秒）
                curr_time = r["curr_time"]
                if curr_time and prev_time:
                    diff = (curr_time - prev_time).total_seconds()
                    new_circle = prev_circle if diff <= CIRCLE_GAP else prev_circle + 1
                else:
                    new_circle = prev_circle

            if r["circle"] != new_circle:
                r["circle"] = new_circle
                changed.append(r)

            prev_circle = new_circle
            prev_time = r["curr_time"]

    return changed


def run_once(iteration: int):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts}] === 第 {iteration} 次执行 ===")

    # 1. 拉取并存库
    print("  拉取数据中...")
    try:
        records = fetch_records.fetch_records()
        n_saved = fetch_records.save_to_db(records)
        print(f"  拉取 {len(records)} 条，新写入 {n_saved} 条（重复跳过 {len(records) - n_saved} 条）")
    except Exception as e:
        print(f"  [错误] 拉取/存库失败: {e}")
        return

    # 2. 读取全量数据
    print("  读取全量数据中...")
    try:
        all_records = fetch_records.load_all_from_db()
        print(f"  数据库共 {len(all_records)} 条记录")
    except Exception as e:
        print(f"  [错误] 读取数据库失败: {e}")
        return

    # 3. 读取开始时间，过滤早于开始时间的记录
    start_time = fetch_records.get_start_time()
    if start_time:
        before = len(all_records)
        all_records = [r for r in all_records if r["curr_time"] and r["curr_time"] >= start_time]
        print(f"  开始时间: {start_time}，过滤掉 {before - len(all_records)} 条早于开始时间的记录，剩余 {len(all_records)} 条")
    else:
        print("  未设置开始时间，使用全量数据计算圈数")

    # 4. 内存计算圈数
    changed = calc_circles(list(all_records))
    print(f"  圈数计算完毕，{len(changed)} 条记录需要更新")

    # 5. 回写圈数
    if changed:
        try:
            n_updated = fetch_records.update_circles(changed)
            print(f"  圈数更新完成，实际更新 {n_updated} 条")
        except Exception as e:
            print(f"  [错误] 圈数更新失败: {e}")
    else:
        print("  圈数无变化，跳过更新")


def main():
    print("主控程序启动，每隔 60 秒执行一次（Ctrl+C 退出）")
    iteration = 1
    while True:
        run_once(iteration)
        iteration += 1
        print(f"  等待 {INTERVAL} 秒后下次执行...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已手动停止。")
