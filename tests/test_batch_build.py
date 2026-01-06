import time
import json
from pathlib import Path

import requests

# ==== 根据你实际后端情况修改这里 ====
BASE_URL = "http://127.0.0.1:5001"  # 或 http://localhost:8000 / 你的后端地址
# 放几个本地 PDF 文件路径
PDF_FILES = [
    r"C:\Users\23035\Desktop\pdf_test1.pdf",
    r"C:\Users\23035\Desktop\pdf_test2.pdf"
    # r"C:\path\to\another.pdf",
]
# ================================


def upload_batch_files():
    url = f"{BASE_URL}/api/hadoop/upload/batch"

    files = []
    for p in PDF_FILES:
        path = Path(p)
        if not path.exists():
            print(f"[WARN] 文件不存在，跳过: {path}")
            continue
        files.append(
            (
                "files",
                (path.name, open(path, "rb"), "application/pdf"),
            )
        )

    if not files:
        raise RuntimeError("没有可用的 PDF 文件, 请先在 PDF_FILES 中配置正确路径")

    print(f"[INFO] 上传 {len(files)} 个文件到: {url}")
    resp = requests.post(url, files=files, timeout=600)
    print(f"[INFO] 上传响应状态码: {resp.status_code}")

    try:
        data = resp.json()
    except Exception:
        print("[ERROR] 无法解析 JSON 响应，原始内容：")
        print(resp.text)
        raise

    print("[INFO] 上传响应内容:")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if resp.status_code != 200:
        raise RuntimeError(f"批量上传失败: {data}")

    uploaded_file_ids = data.get("uploaded_file_ids") or []
    if not uploaded_file_ids:
        raise RuntimeError("上传成功但未返回 uploaded_file_ids")

    return uploaded_file_ids


def trigger_batch_build(file_ids):
    url = f"{BASE_URL}/api/hadoop/build/batch"
    payload = {
        "file_ids": file_ids,
        "use_hadoop": True,
    }

    print(f"[INFO] 触发批量构建: {url}")
    resp = requests.post(url, json=payload, timeout=60)
    print(f"[INFO] 构建响应状态码: {resp.status_code}")

    data = resp.json()
    print("[INFO] 构建响应内容:")
    print(json.dumps(data, ensure_ascii=False, indent=2))

    if resp.status_code not in (200, 202):
        raise RuntimeError(f"批量构建请求失败: {data}")

    task_id = data.get("task_id")
    if not task_id:
        raise RuntimeError("响应中没有 task_id")

    return task_id


def poll_task_status(task_id, interval=5, max_minutes=30):
    url = f"{BASE_URL}/api/hadoop/status/{task_id}"
    max_seconds = max_minutes * 60
    elapsed = 0

    print(f"[INFO] 开始轮询任务状态, task_id={task_id}")

    while True:
        resp = requests.get(url, timeout=30)
        try:
            data = resp.json()
        except Exception:
            print("[ERROR] 状态接口返回非 JSON：")
            print(resp.text)
            break

        task = data.get("task") or {}
        status = task.get("status")
        progress = task.get("progress")
        message = task.get("message")

        print(
            f"[STATUS] status={status}, progress={progress}, "
            f"message={message}"
        )

        # 根据 backend.app 里的 TaskStatus 枚举，大概率是 PROCESSING / SUCCESS / FAILED
        if status in ("SUCCESS", "FAILED", "ERROR"):
            print("[INFO] 任务结束，完整返回：")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            break

        time.sleep(interval)
        elapsed += interval
        if elapsed >= max_seconds:
            print("[WARN] 轮询超时，停止等待")
            print(json.dumps(data, ensure_ascii=False, indent=2))
            break


def main():
    print("==== 第一步：批量上传文件 ====")
    file_ids = upload_batch_files()
    print(f"[INFO] 上传得到 file_ids: {file_ids}")

    print("\n==== 第二步：批量构建知识图谱 ====")
    task_id = trigger_batch_build(file_ids)
    print(f"[INFO] 收到 task_id: {task_id}")

    print("\n==== 第三步：轮询任务状态 ====")
    poll_task_status(task_id)


if __name__ == "__main__":
    main()