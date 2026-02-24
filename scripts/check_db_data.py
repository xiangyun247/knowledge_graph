#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库里是否有数据：知识图谱、用户、历史记录等。
使用项目 db.mysql_client，读取 .env 配置。
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def main():
    print("=" * 60)
    print("数据库数据检查（使用 .env 中的 MySQL 配置）")
    print("=" * 60)

    try:
        from db.mysql_client import get_mysql_client
        client = get_mysql_client()
    except Exception as e:
        print(f"\n[FAIL] 连接 MySQL 失败: {e}")
        return

    # 1. knowledge_graphs 表
    print("\n【1】knowledge_graphs（知识图谱）")
    print("-" * 40)
    try:
        all_graphs = client.get_graphs(user_id=None, limit=500)
        try:
            default_graphs = client.get_default_graphs(limit=500)  # user_id IS NULL
        except Exception:
            default_graphs = []
        print(f"  总条数: {len(all_graphs)}")
        print(f"  其中默认图谱（user_id 为空）: {len(default_graphs)} 条")
        if all_graphs:
            for i, r in enumerate(all_graphs[:15], 1):
                gid = r.get("graph_id") or r.get("id") or ""
                name = r.get("graph_name") or r.get("name") or ""
                uid = r.get("user_id")
                uid_str = "(NULL，所有人可见)" if uid is None or uid == "" else repr(uid)
                status = r.get("status") or ""
                print(f"  [{i}] graph_id={gid}")
                print(f"      graph_name={name}")
                print(f"      user_id={uid_str}, status={status}")
            if len(all_graphs) > 15:
                print(f"  ... 还有 {len(all_graphs) - 15} 条未显示")
        else:
            print("  [空] 表内没有任何图谱记录")
    except Exception as e:
        print(f"  [FAIL] 查询失败: {e}")

    # 2. users 表（若存在）
    print("\n【2】users（用户）")
    print("-" * 40)
    try:
        rows = client.execute_query("SELECT user_id, username, email FROM users LIMIT 20")
        print(f"  总条数（前 20）: {len(rows)}")
        if rows:
            for i, r in enumerate(rows[:5], 1):
                uid = r.get("user_id") or r.get("id")
                uname = r.get("username") or ""
                print(f"  [{i}] user_id={uid}, username={uname}")
            if len(rows) > 5:
                print(f"  ... 还有 {len(rows) - 5} 条未显示")
        else:
            print("  [空] 表内没有用户记录")
    except Exception as e:
        print(f"  [FAIL] 查询失败（可能表不存在）: {e}")

    # 3. history_records 表（若存在）
    print("\n【3】history_records（历史记录）")
    print("-" * 40)
    try:
        rows = client.execute_query(
            "SELECT history_id, graph_id, user_id, operation_type FROM history_records ORDER BY created_at DESC LIMIT 10"
        )
        print(f"  最近 10 条: {len(rows)}")
        if rows:
            for i, r in enumerate(rows[:3], 1):
                hid = r.get("history_id") or ""
                gid = r.get("graph_id") or ""
                op = r.get("operation_type") or ""
                print(f"  [{i}] history_id={hid[:20]}..., graph_id={gid}, operation_type={op}")
        else:
            print("  [空] 没有历史记录")
    except Exception as e:
        print(f"  [FAIL] 查询失败（可能表不存在）: {e}")

    print("\n" + "=" * 60)
    print("检查结束。若 knowledge_graphs 总条数为 0，前端图谱页会为空；")
    print("可运行 init_mysql.sql 插入示例数据，或由后端 ensure_default_graph 自动插入一条默认图谱。")
    print("=" * 60)


if __name__ == "__main__":
    main()
