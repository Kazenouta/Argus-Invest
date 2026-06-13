#!/usr/bin/env python3
import os
import re
import json
import time
import html
from pathlib import Path

# Article list - updated with actual available files
ARTICLES = [
    '好像是牛市的味道？.html',
    '市场再次尝试切换 继续聊聊黄金和原油.html',
    '微盘股又新高了，期货市场却被砸了.html',
    '我的书单.html',
    '特朗普不想打了？日韩快扛不住了.html',
    '百年变局下的大宗商品（三）—中国的铝 世界的铝.html',
    '特朗普的关税战和全球经济危机分析.html',
    '百年变局下的大宗商品（一）——黄金的超级大牛市.html',  # renamed
    '百年变局下的大宗商品（二）——铜的崛起.html',
    '2025_9_26周总结.html',  # actual filename
    '2025_9_19周总结-风格持续在转换.html',  # actual filename
    '2025_9_12周总结——老A啥时候上四千？.html',  # actual filename
    '2025_9_5周总结—.html',  # actual filename
    '2025_7_25周总结.html',  # actual filename
    '2025_7_18周总结.html',  # actual filename instead of 2025_7_11
    # Note: 百年变局下的大宗商品（四） is PDF not HTML, skipping
    # 百年变局下的大宗商品（五） doesn't exist
    '2025_8_15周总结.html',  # actual filename instead of 2025_5_30
    '2025_8_1周总结暨7月总结.html',  # might match 2025_5_23
    '2025_8_8周总结—好像是在拉开一个序幕.html',  # might match 2025_5_16
    '2025_8_22 周总结——长牛建立在垃圾股的废墟之上.html',  # might match 2025_5_9
    '2025_8_29 周总结——风格要转变了吗？.html',  # might match 2025_4_30
    '2025_8_1周总结暨7月总结.html',  # might match 2025_4_25
    '2025_7_18周总结.html',  # might match 2025_4_18
    '2025_7_11周总结——静待.html',  # might exist
]

BASE_DIR = Path('/Users/bxz/Documents/projects/Argus-Invest')
HTML_DIR = BASE_DIR / 'data/kv/斯托伯的天空'
WIKI_DIR = BASE_DIR / 'wiki'
STATE_FILE = Path('/tmp/wiki_progress.json')

# Read API key
with open('/tmp/mx_key.txt', 'r') as f:
    API_KEY = f.read().strip()

def extract_text_from_html(html_path):
    """Extract text from id='js_content' element."""
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find id="js_content"
    match = re.search(r'id="js_content"[^>]*>(.*)', content, re.DOTALL)
    if not match:
        return None
    
    text = match.group(1)
    
    # Strip HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Unescape HTML entities
    text = html.unescape(text)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def call_minimax_summarize(text):
    """Call MiniMax API for summarization."""
    from openai import OpenAI
    
    client = OpenAI(
        api_key=API_KEY,
        base_url="https://api.minimaxi.com/v1"
    )
    
    prompt = f"""请为以下文章生成JSON格式的摘要。

要求输出严格JSON格式，不要有任何其他内容：
{{
  "summary": "100-200字摘要",
  "key_points": ["观点1", "观点2", "观点3"],
  "stance": "看多/看空/谨慎/中性",
  "tags": ["标签1", "标签2"],
  "type": "周总结/投资理念/技术分析/书单/主题研究/仓位管理"
}}

文章内容：
{text[:8000]}

请严格输出JSON："""

    response = client.chat.completions.create(
        model="MiniMax-M2.7",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    result_text = response.choices[0].message.content
    
    # Remove thinking blocks
    result_text = re.sub(r'<[^>]*think[^>]*>[\s\S]*?</[^>]*think[^>]*>', '', result_text)
    result_text = re.sub(r'<think>[\s\S]*?</think>', '', result_text)
    
    # Extract JSON
    json_match = re.search(r'\{[\s\S]*\}', result_text)
    if json_match:
        return json.loads(json_match.group())
    return None

def stance_to_emoji(stance):
    """Convert stance to emoji prefix."""
    mapping = {
        '看多': '✅ 看多',
        '看空': '❌ 看空',
        '谨慎': '⚠️ 谨慎',
        '中性': '➡️ 中性'
    }
    return mapping.get(stance, stance)

def extract_date_from_filename(filename):
    """Extract date from filename for created field."""
    # Try to match patterns like 2025_4_11 or 2025_4_30
    match = re.search(r'(\d{4})[_-](\d{1,2})[_-](\d{1,2})', filename)
    if match:
        return f"{match.group(1)}/{match.group(2).zfill(2)}/{match.group(3).zfill(2)}"
    return None

def write_wiki_file(article_name, data, text):
    """Write wiki markdown file."""
    from datetime import datetime
    
    # Create filename from article name
    filename = article_name.replace('.html', '').replace(' ', '_')
    wiki_path = WIKI_DIR / f"{filename}.md"
    
    today = datetime.now().strftime('%Y-%m-%d')
    stance_emoji = stance_to_emoji(data.get('stance', '中性'))
    tags = data.get('tags', [])
    key_points = data.get('key_points', [])
    
    content = f"""---
title: "{article_name.replace('.html', '')}"
created: {extract_date_from_filename(article_name) or datetime.now().strftime('%Y/%m/%d')}
updated: {today}
type: {data.get('type', '周总结')}
stance: "{stance_emoji}"
tags: {json.dumps(tags, ensure_ascii=False)}
sources: ["斯托伯的天空"]
confidence: high
contested: false
---

## 摘要

{data.get('summary', '')}

## 关键观点

"""
    for i, point in enumerate(key_points, 1):
        content += f"{i}. {point}\n"
    
    with open(wiki_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return wiki_path

def load_state():
    """Load progress state."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {'processed': [], 'success': 0, 'failed': []}

def save_state(state):
    """Save progress state."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def process_articles():
    """Process all articles."""
    state = load_state()
    processed_set = set(state.get('processed', []))
    
    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    
    success_count = state.get('success', 0)
    failed = state.get('failed', [])
    
    for i, article in enumerate(ARTICLES):
        print(f"\n[{i+1}/25] Processing: {article}")
        
        if article in processed_set:
            print(f"  Already processed, skipping")
            continue

        html_path = HTML_DIR / article
        if not html_path.exists():
            # Try to find similar filename
            similar = [f for f in os.listdir(HTML_DIR) if article.replace('.html','') in f]
            if similar:
                print(f"  Note: '{article}' not found, but found: {similar[0]}")
                html_path = HTML_DIR / similar[0]
            else:
                print(f"  ERROR: File not found: {html_path}")
                failed.append(article)
                continue
        
        try:
            # Extract text
            text = extract_text_from_html(html_path)
            if not text:
                print(f"  ERROR: Could not extract text from {article}")
                failed.append(article)
                continue
            
            print(f"  Extracted {len(text)} chars")
            
            # Call API
            result = call_minimax_summarize(text)
            if not result:
                print(f"  ERROR: No result from API")
                failed.append(article)
                continue
            
            print(f"  Summary: {result.get('summary', '')[:50]}...")
            
            # Write wiki file
            wiki_path = write_wiki_file(article, result, text)
            print(f"  Written: {wiki_path}")
            
            # Update state
            processed_set.add(article)
            success_count += 1
            
            # Save progress every 5 articles
            if success_count % 5 == 0:
                state['processed'] = list(processed_set)
                state['success'] = success_count
                state['failed'] = failed
                save_state(state)
                print(f"  [CHECKPOINT] Progress saved: {success_count} articles processed")
            
            # Rate limit
            time.sleep(1.3)
            
        except Exception as e:
            print(f"  ERROR: {e}")
            failed.append(article)
            continue
    
    # Final save
    state['processed'] = list(processed_set)
    state['success'] = success_count
    state['failed'] = failed
    save_state(state)
    
    print(f"\n{'='*50}")
    print(f"DONE! Processed {success_count} articles successfully")
    print(f"Failed: {len(failed)}")
    if failed:
        print(f"Failed articles: {failed}")
    print(f"{'='*50}")

if __name__ == '__main__':
    process_articles()