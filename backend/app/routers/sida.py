"""
Sida (斯托伯的天空) API router.
"""
import re
import json
import html
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from app.config import settings

router = APIRouter(prefix="/api/sida", tags=["Sida"])


SIDA_DIR = settings.DATA_DIR / "sida"
KV_SIDA_DIR = settings.KV_DIR / "斯托伯的天空"


def parse_sida_weekly_report(html_content: str) -> dict:
    """Parse a Sida weekly report HTML file and extract structured data."""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Extract title from content (first line that looks like a title)
    title_match = re.search(r'([^《\n]{5,50}?(?:周总结|年终总结|展望)[^》\n]{0,30})', text)
    title = title_match.group(1).strip() if title_match else ''

    # Extract date
    date_match = re.search(r'(\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}[日]?)', text)
    date_str = date_match.group(1) if date_match else ''

    # Extract core thinking (first paragraph with quotes or key insight)
    # Look for content after date/title, before "先说说大盘"
    core_sections = re.findall(
        r'(?:本文不构成投资建议[^，]*，)[^"]*[""'']([^""'']{10,200})[""'']',
        text
    )
    core_thinking = core_sections[0] if core_sections else ''

    # If no quoted text found, look for key insight patterns
    if not core_thinking:
        insight_match = re.search(
            r'(?:风险|收益|长期|逻辑|本质)[^。\n]{10,100}[。]',
            text
        )
        if insight_match:
            core_thinking = insight_match.group(0).strip()

    # Extract signal keywords for each sector
    def extract_signal(text: str, sector_keywords: list, positive_kw: list, negative_kw: list) -> dict:
        """Extract view and signal level for a sector."""
        # Find the section about this sector
        section = ''
        for kw in sector_keywords:
            pattern = rf'{kw}[^。，]{{0,200}}[，。].*?(?=(?:原油|黄金|大盘|铜|铝|化工|说说)|$)'
            m = re.search(pattern, text)
            if m:
                section = m.group(0)
                break

        if not section:
            return {'view': '等待观察', 'detail': '', 'signal': '中性', 'level': 3}

        # Determine signal
        signal = '中性'
        level = 3
        pos_count = sum(1 for k in positive_kw if k in section)
        neg_count = sum(1 for k in negative_kw if k in section)
        if pos_count > neg_count:
            if pos_count >= 3:
                signal = '强烈看多'
                level = 5
            elif pos_count >= 1:
                signal = '看多'
                level = 4
        elif neg_count > pos_count:
            if neg_count >= 3:
                signal = '强烈看空'
                level = 1
            elif neg_count >= 1:
                signal = '偏空/谨慎'
                level = 2

        # Extract view summary
        view_match = re.search(
            r'(?:原油|黄金|大盘|铜|铝|化工)[:：][^。\n]{5,100}',
            section
        )
        view = view_match.group(0).split('：')[-1].split('：')[-1].strip()[:80] if view_match else '等待观察'

        # Extract first meaningful sentence as detail
        detail = re.findall(r'[^。！？]{20,150}[。！？]', section)
        detail_text = detail[0] if detail else ''

        return {'view': view, 'detail': detail_text, 'signal': signal, 'level': level}

    # Define sector keywords
    sectors = {
        '大盘': {
            'keywords': ['说说大盘', '大盘', '市场', 'A股'],
            'positive': ['长牛', '牛市', '看多', '上涨', '机会', '新高', '乐观'],
            'negative': ['风险', '偏空', '谨慎', '下跌', '回调', '熊市', '危机', '烂']
        },
        '原油/能源': {
            'keywords': ['原油', '能源', '石油', '煤', '霍尔木兹'],
            'positive': ['看多', '上涨', '新高', '能源危机', '紧缺', '强势', '必选'],
            'negative': ['下跌', '回调', '谨慎', '过剩']
        },
        '黄金': {
            'keywords': ['黄金', '金价', '金矿'],
            'positive': ['看多', '上涨', '牛市', '长逻辑', '新高', '长期看多'],
            'negative': ['回调', '下跌', '谨慎', '等待', '不着急', '压力']
        },
        '铜': {
            'keywords': ['铜', '电解铜'],
            'positive': ['看多', '上涨', '短缺', '看好'],
            'negative': ['下跌', '回调', '谨慎', '等待', '衰退', '流动性']
        },
        '电解铝': {
            'keywords': ['铝', '电解铝', '铝价'],
            'positive': ['看多', '上涨', '短缺', '优势', '看好'],
            'negative': ['下跌', '回调', '谨慎', '等待']
        },
        '化工': {
            'keywords': ['化工', '化肥'],
            'positive': ['看多', '上涨', '看好', '逻辑不变', '机会'],
            'negative': ['下跌', '回调', '谨慎', '保供']
        }
    }

    market_views = {}
    for sector, cfg in sectors.items():
        market_views[sector] = extract_signal(
            text,
            cfg['keywords'],
            cfg['positive'],
            cfg['negative']
        )

    # Extract position info
    position_map = {
        '整体仓位': re.search(r'仓位[^：：]*[：:][^。，]{2,30}', text),
        '主要持仓': re.search(r'(?:主要持仓|持仓)[^：：]*[：:][^。，]{2,50}', text),
    }

    # Extract year return
    return_match = re.search(r'(?:年度收益|收益)[^回是]{0,5}(?:是|：|:)[^%，。]{1,20}[%％]', text)

    return {
        '_meta': {
            'sourceFile': title,
            'dateStr': date_str
        },
        'coreThinking': core_thinking[:200] if core_thinking else '风险才是投资里最重要最值钱的东西。',
        'marketViews': market_views,
        'positionSummary': {
            '整体仓位': position_map.get('整体仓位') and position_map['整体仓位'].group(0).split('：')[-1].split(':')[-1].strip()[:30] or '',
            '主要持仓': position_map.get('主要持仓') and position_map['主要持仓'].group(0).split('：')[-1].split(':')[-1].strip()[:30] or '',
        },
        'yearReturn': return_match.group(0) if return_match else ''
    }


@router.post("/upload")
async def upload_sida_report(
    file: UploadFile = File(...),
    author: str = Form(default="斯托伯的天空")
):
    """上传斯大周报 HTML 文件，解析并更新最新观点。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    if not (file.filename.endswith('.html') or file.filename.endswith('.htm')):
        raise HTTPException(status_code=400, detail="仅支持 .html 文件")

    content = await file.read()

    # Parse the HTML
    try:
        html_text = content.decode('utf-8')
    except UnicodeDecodeError:
        html_text = content.decode('gbk', errors='replace')

    parsed = parse_sida_weekly_report(html_text)

    # Save to KV directory with original filename
    target_dir = KV_SIDA_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    # Clean filename
    safe_name = re.sub(r'[\\/:*?"<>|]', '_', file.filename)
    file_path = target_dir / safe_name
    file_path.write_bytes(content)

    # Update latest.json
    SIDA_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = SIDA_DIR / "latest.json"

    # Load existing latest to preserve some fields
    existing = {}
    if latest_path.exists():
        try:
            existing = json.loads(latest_path.read_text(encoding='utf-8'))
        except:
            pass

    # Merge: use parsed data for market views, keep recent history
    merged = {
        **existing,
        **parsed,
        'name': '斯大',
        'fullName': author,
        'lastUpdated': str(settings.DATA_DIR),  # will be set as date below
    }
    # Use parsed date as lastUpdated
    import datetime
    merged['lastUpdated'] = datetime.date.today().isoformat()

    # Preserve recentHistory from existing
    if 'recentHistory' in existing and len(existing['recentHistory']) > 0:
        merged['recentHistory'] = existing['recentHistory']
    else:
        merged['recentHistory'] = []

    # Prepend new entry to recentHistory
    new_entry = {
        'date': parsed.get('_meta', {}).get('dateStr', '') or datetime.date.today().isoformat(),
        'title': parsed.get('_meta', {}).get('sourceFile', file.filename),
        'signal': parsed.get('marketViews', {}).get('原油/能源', {}).get('signal', '中性')
    }
    merged['recentHistory'] = [new_entry] + merged['recentHistory'][:11]  # keep last 12

    latest_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        "success": True,
        "filename": safe_name,
        "parsed": {
            "title": parsed.get('_meta', {}).get('sourceFile', ''),
            "date": parsed.get('_meta', {}).get('dateStr', ''),
        }
    }


@router.get("/latest")
def get_sida_latest():
    """获取斯大最新观点数据。"""
    latest_path = SIDA_DIR / "latest.json"
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail="暂无数据，请先上传周报")
    return json.loads(latest_path.read_text(encoding='utf-8'))
