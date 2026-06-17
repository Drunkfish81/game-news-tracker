#!/usr/bin/env python3
"""
游戏公司每日新闻抓取器
基于 GNews (Google News Python 封装) + 关键词评分
抓取 6 家游戏公司：Roblox, Epic Games, Take-Two, Microsoft, EA, Sony
输出 JSON 格式，供导入腾讯文档智能表格使用
"""

import json
import sys
import os
import time
import hashlib
import re
from datetime import datetime, timezone, timedelta
from gnews import GNews

# ============================================================
# 配置
# ============================================================

# 目标公司及搜索关键词（英文 + 中文双通道）
COMPANIES = {
    "Roblox": {
        "queries": ["Roblox corporation gaming"],
    },
    "Epic Games": {
        "queries": ["Epic Games Unreal Fortnite"],
    },
    "Take-Two": {
        "queries": ["Take-Two Interactive Rockstar GTA"],
    },
    "Microsoft": {
        "queries": ["Microsoft Xbox gaming Activision"],
    },
    "EA": {
        "queries": ["Electronic Arts EA gaming"],
    },
    "Sony": {
        "queries": ["Sony PlayStation gaming"],
    },
}

# 每家公司每次搜索最多获取条数
MAX_RESULTS_PER_QUERY = 8
# 只保留最近 N 天的新闻
MAX_AGE_DAYS = 3
# 请求间隔（秒）
REQUEST_DELAY = 1.5

# 重要度评分关键词 (0-10分)
IMPORTANCE_KEYWORDS = {
    # 10分：重大事件
    10: [
        r"\bacquisition\b", r"\bmerger\b", r"\bacquire[sd]?\b", r"\bbillion\b",
        r"\bIPO\b", r"\b上市\b", r"\b收购\b", r"\b并购\b", r"\b十亿\b",
        r"\blawsuit\b", r"\b诉讼\b", r"\bantitrust\b", r"\b反垄断\b",
        r"\blayoff[s]?\b", r"\b裁员\b", r"\bshutdown\b", r"\b关闭\b",
    ],
    # 8分：重要动态
    8: [
        r"\blaunch\b", r"\brelease\b date", r"\b发售\b", r"\b发布\b",
        r"\bpartnership\b", r"\b合作\b", r"\bexclusive\b", r"\b独占\b",
        r"\brevenue\b", r"\b营[收货]\b", r"\bprofit\b", r"\b利润\b",
        r"\bstock\b (?:surge|drop|plunge|soar|jump)", r"\b股价\b",
        r"\bCEO\b", r"\bexecutive\b", r"\b高管\b",
    ],
    # 6分：值得关注
    6: [
        r"\bupdate\b", r"\b更新\b", r"\bexpansion\b", r"\b扩展\b",
        r"\bpatch\b", r"\b补丁\b", r"\brecord\b", r"\b纪录\b",
        r"\binvest(?:ment|or)\b", r"\b投资\b", r"\bvaluation\b", r"\b估值\b",
        r"\bregulatory\b", r"\b监管\b", r"\bdelay\b", r"\b延期\b",
    ],
    # 4分：一般动态
    4: [
        r"\bevent\b", r"\b活动\b", r"\bannounce\b", r"\b宣布\b",
        r"\bnew\b (?:game|title|feature|content)", r"\b新(?:游戏|作|功能|内容)\b",
        r"\breview\b", r"\b评测\b", r"\bplayer[s]?\b", r"\b玩家\b",
    ],
}

# 输出文件路径
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "news_output.json")


def score_importance(title: str, description: str = "") -> float:
    """根据标题和摘要关键词评分 (0-10)"""
    text = f"{title} {description}".lower()
    score = 2.0  # 基础分

    for points, patterns in sorted(IMPORTANCE_KEYWORDS.items(), reverse=True):
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score = max(score, float(points))
                break

    # 标题长度太短通常是低质量
    if len(title) < 15:
        score = min(score, 3.0)

    return min(score, 10.0)


def normalize_url(url: str) -> str:
    """标准化 URL 用于去重"""
    return re.sub(r'[?#].*$', '', url).rstrip('/')


def scrape_company(gn: GNews, company: str, config: dict) -> list:
    """抓取单家公司的新闻"""
    articles = []
    seen_urls = set()

    for query in config["queries"]:
        try:
            results = gn.get_news(query)
            for item in results:
                url = normalize_url(item.get("url", ""))
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = item.get("title", "")
                description = item.get("description", "")

                articles.append({
                    "title": title,
                    "company": company,
                    "summary": (description[:200] + "...") if len(description) > 200 else description,
                    "importance": score_importance(title, description),
                    "published": item.get("published date", ""),
                    "url": url,
                    "source": item.get("publisher", {}).get("title", ""),
                })
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            print(f"  [WARN] 查询 '{query}' 失败: {e}", file=sys.stderr)

    return articles


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始抓取6家游戏公司新闻...", file=sys.stderr)

    gn = GNews(
        language="en",
        country="US",
        max_results=MAX_RESULTS_PER_QUERY,
        period=f"{MAX_AGE_DAYS}d",
        exclude_websites=["youtube.com", "reddit.com"],
    )

    all_articles = []
    for company, config in COMPANIES.items():
        print(f"  抓取 {company}...", file=sys.stderr)
        articles = scrape_company(gn, company, config)
        all_articles.extend(articles)
        print(f"    → {len(articles)} 条", file=sys.stderr)

    # 按重要度降序排列
    all_articles.sort(key=lambda x: x["importance"], reverse=True)

    # 去重（跨公司）
    seen_titles = set()
    unique_articles = []
    for a in all_articles:
        title_hash = hashlib.md5(a["title"].lower().strip().encode()).hexdigest()
        if title_hash not in seen_titles:
            seen_titles.add(title_hash)
            unique_articles.append(a)

    # 输出统计
    print(f"\n总计: {len(unique_articles)} 条新闻（去重后）", file=sys.stderr)
    for company in COMPANIES:
        count = len([a for a in unique_articles if a["company"] == company])
        avg_score = sum(a["importance"] for a in unique_articles if a["company"] == company) / max(count, 1)
        print(f"  {company}: {count} 条, 平均评分 {avg_score:.1f}", file=sys.stderr)

    # 写 JSON
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(unique_articles),
        "companies": list(COMPANIES.keys()),
        "articles": unique_articles,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存至: {OUTPUT_FILE}", file=sys.stderr)
    return OUTPUT_FILE


if __name__ == "__main__":
    main()
