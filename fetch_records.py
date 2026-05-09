#!/usr/bin/env python3
"""
从计时系统拉取成绩记录（xlsx格式），解析成 dict 列表并返回。
"""

import io
import sys
import urllib.request

import openpyxl

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


if __name__ == "__main__":
    main()
