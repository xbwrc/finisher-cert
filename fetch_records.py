#!/usr/bin/env python3
"""
从计时系统拉取成绩记录（xlsx格式），解析成 dict 列表并存入 MySQL。
"""

import io
import sys
import urllib.request

import openpyxl
import pymysql

import config

URL = (
    "https://cloud-time.marathon8.com/gubin_admin/records"
    "?_pjax=%23pjax-container"
    "&mac%5B0%5D=P513"
    "&mac%5B1%5D=P591"
    "&mac%5B2%5D=P753"
    "&_export_=all"
)

COOKIES = (
    "XSRF-TOKEN=eyJpdiI6ImFxcHZhY2drbmZyQVJ2NVlUbHJDWGc9PSIsInZhbHVlIjoiMlhmdTdjTUhkN1U4VVBXdkkxNnlZNjNUSEV6ZGw5eVFreVA0Njc1K0RPblRiV1RKMFhFYmkyemVUeHVTMllSUXV3ZGVUbERmc2J3SjUyUTUyZ2JnV0lmdnpZcUMydThSaCt2aE1HZHQ1V3pSREhMaHJkYVZIaUY3eUVRaUpyOUciLCJtYWMiOiJjNTI3ZWZhNTc5ZDczOWIxNzQyOTE1MGZjYTYyNDBkYWVmMjM5NWJlMzgwNDhiZWVmMWFiYjA0MmM3ZWVhODUxIiwidGFnIjoiIn0%3D; "
    "new_running8_marathon_time_system_session=eyJpdiI6IlhIcnRxc1YvcE1IUDhoS1RXb1cyOGc9PSIsInZhbHVlIjoiU1IxR2xnYXVING4xMXZuNG9iNmtzbXZ6eUZQRVplOUZQRjNRdm5WZW02Zmx1SnJOUnVSSUNMMzVFN09EYithTzR0WEJ1Kyt1QkRzU3RHZ0hnVmFlZjdwaHB5MUswUUU2YWZ5M0R1d0lEVGc1MjBvQ3NJN2lVZlZ0WkRrSjBwMXgiLCJtYWMiOiI0M2FkMGUwNmNhMDVhYWU4OGU1OTI3NWFmYTk0OWM5NTRiZmUyNTE4OWFjODUyNGU0MzgyNzZlNzMzNGMyYzU0IiwidGFnIjoiIn0%3D"
)

HEADERS = {
    "Cookie": COOKIES,
    "x-pjax": "true",
}


def fetch_records() -> list[dict]:
    """请求接口，解析 xlsx，返回 dict 列表（第一行为表头）。"""
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()

    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h) if h is not None else "" for h in rows[0]]
    records = []
    strip_fields = {"芯片码", "时间"}
    for row in rows[1:]:
        record = {}
        for i, h in enumerate(headers):
            v = row[i]
            if h in strip_fields and isinstance(v, str):
                v = v.strip()
            record[h] = v
        records.append(record)

    wb.close()
    return records


def get_conn(**kwargs):
    """创建并返回数据库连接。"""
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        database=config.DB_NAME,
        charset="utf8mb4",
        **kwargs,
    )


def save_to_db(records: list[dict]) -> int:
    """将记录写入 MySQL m_record 表，跳过重复记录，返回实际插入条数。"""
    if not records:
        return 0

    conn = get_conn()
    sql = """
        INSERT IGNORE INTO m_record (chip, curr_time, circle)
        VALUES (%s, %s, %s)
    """
    inserted = 0
    try:
        with conn.cursor() as cur:
            for r in records:
                chip = r.get("芯片码") or ""
                curr_time = r.get("自然时间") or None
                cur.execute(sql, (chip, curr_time, 0))
                inserted += cur.rowcount
        conn.commit()
    finally:
        conn.close()

    return inserted


def main():
    print("正在拉取成绩数据...")
    try:
        records = fetch_records()
    except Exception as e:
        print(f"请求失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not records:
        print("未获取到任何记录。")
        return

    print(f"共获取到 {len(records)} 条记录\n")

    headers = list(records[0].keys())
    print("字段列表:", headers)
    print("-" * 60)

    for i, row in enumerate(records[:5], 1):
        print(f"[{i}]", row)

    if len(records) > 5:
        print(f"... 共 {len(records)} 条，以上显示前5条")

    print("\n正在写入数据库...")
    try:
        n = save_to_db(records)
        print(f"已写入数据库 {n} 条（重复跳过 {len(records) - n} 条）")
    except Exception as e:
        print(f"数据库写入失败: {e}", file=sys.stderr)
        sys.exit(1)


def load_all_from_db() -> list[dict]:
    """从数据库读取全量 m_record 记录，返回 dict 列表。
    每条记录包含: id, chip, curr_time, circle
    """
    conn = get_conn(cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, chip, curr_time, circle FROM m_record")
            return cur.fetchall()
    finally:
        conn.close()


def get_start_time():
    """从 start_time 表读取唯一的开始时间，若表为空则返回 None。"""
    conn = get_conn(cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT start_time FROM start_time LIMIT 1")
            row = cur.fetchone()
            return row["start_time"] if row else None
    finally:
        conn.close()


def update_circles(records: list[dict]) -> int:
    """批量更新 m_record 表中各记录的 circle 字段，返回更新条数。
    records 中每条需包含 id 和 circle。
    """
    if not records:
        return 0

    conn = get_conn()
    sql = "UPDATE m_record SET circle = %s WHERE id = %s"
    updated = 0
    try:
        with conn.cursor() as cur:
            for r in records:
                cur.execute(sql, (r["circle"], r["id"]))
                updated += cur.rowcount
        conn.commit()
    finally:
        conn.close()

    return updated


if __name__ == "__main__":
    main()
