#!/usr/bin/env python3
"""
通过企微智能表格 Webhook 导入新闻数据
使用 webhook key 直接 POST JSON
"""

import json
import os
import sys
import time
import urllib.request
from email.utils import parsedate_to_datetime

INPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "news_output.json")
WEBHOOK_URL = os.environ.get("WECOM_WEBHOOK_URL", "")
BATCH_SIZE = 10

# 字段 ID 映射 (与用户表格字段对应)
FIELD_MAP = {
    "title": "f04Gwj",       # 新闻标题
    "company": "ftQMc5",     # 公司
    "summary": "ftk5Tx",     # 简介
    "importance": "ffFwIh",  # 重要度评分
    "published": "fn8TJd",   # 新闻时间
    "url": "fZCqYK",         # 新闻链接
    "source": "fY967Y",      # 来源
}


def format_datetime(published_str):
    """RFC 2822 → 毫秒时间戳字符串"""
    try:
        dt = parsedate_to_datetime(published_str)
        return str(int(dt.timestamp() * 1000))
    except Exception:
        return ""


def article_to_record(article):
    """文章 → webhook 记录格式"""
    return {
        "values": {
            FIELD_MAP["title"]: article["title"][:500],
            FIELD_MAP["company"]: [{"text": article["company"]}],
            FIELD_MAP["summary"]: (article["summary"] or "")[:500],
            FIELD_MAP["importance"]: article["importance"],
            FIELD_MAP["published"]: format_datetime(article["published"]),
            FIELD_MAP["url"]: [{"link": article["url"], "text": "阅读原文"}],
            FIELD_MAP["source"]: (article["source"] or "")[:100],
        }
    }


def post_batch(records):
    """POST 一批记录到 webhook"""
    payload = json.dumps({"add_records": records}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result
    except Exception as e:
        return {"error": str(e)}


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    articles = sorted(data["articles"], key=lambda x: x["importance"], reverse=True)
    print(f"读取 {len(articles)} 条新闻，按重要度降序\n")

    success = 0
    total_batches = (len(articles) - 1) // BATCH_SIZE + 1

    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i : i + BATCH_SIZE]
        records = [article_to_record(a) for a in batch]
        batch_num = i // BATCH_SIZE + 1

        print(f"Batch {batch_num}/{total_batches}: 发送 {len(records)} 条...", end=" ")
        result = post_batch(records)

        if "errcode" in result and result["errcode"] == 0:
            success += len(records)
            print(f"✓")
        elif "error" in result:
            print(f"✗ 网络错误: {result['error']}")
        else:
            print(f"✗ errcode={result.get('errcode')}, errmsg={result.get('errmsg', '')}")

        if i + BATCH_SIZE < len(articles):
            time.sleep(0.5)

    print(f"\n{'='*40}")
    print(f"完成: {success}/{len(articles)} 条导入成功")
    if success > 0:
        print(f"表格: https://doc.weixin.qq.com/smartsheet/s3_AZIApgYYALQCNYzt27TsSRW0x0WLR")


if __name__ == "__main__":
    main()
