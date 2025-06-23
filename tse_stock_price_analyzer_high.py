# -*- coding: utf-8 -*-
"""Analyze TSE stocks that keep hitting new highs.

This script mirrors ``stock_price_analyzer.py`` but looks for stocks that
continue to break their previous highs during the comparison period.
It reuses the corrected download logic so each date's data is fetched only
once.
"""

import csv
import io
import os
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

import requests
from openpyxl import Workbook

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
LOG_FILE = os.path.join(OUTPUT_DIR, 'stock_price_high_analyzer.log')
DOWNLOADED_DATES_FILE = os.path.join(OUTPUT_DIR, 'downloaded_dates_high.txt')
CACHE_DIR = os.path.join(OUTPUT_DIR, 'cache_high')


def setup_logging() -> None:
    """Configure logging to file and console."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )


def generate_dates(start: str, end: str) -> List[str]:
    """Return a list of YYYYMMDD strings for weekdays in the range."""
    begin = datetime.strptime(start, '%Y%m%d')
    finish = datetime.strptime(end, '%Y%m%d')
    dates: List[str] = []
    current = begin
    while current <= finish:
        if current.weekday() < 5:  # Monday-Friday
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    return dates


ALL_DATES = generate_dates('20250407', '20250620')
BASE_DATES = generate_dates('20250407', '20250525')
COMPARE_DATES = generate_dates('20250526', '20250620')

# Output filenames - 使用中文讓檔名更直觀
RECORDS_FILE = f"台股最高價紀錄_{ALL_DATES[0]}_{ALL_DATES[-1]}.xlsx"
COMPARISON_FILE = (
    f"台股創新高比較_{COMPARE_DATES[0]}_{COMPARE_DATES[-1]}.xlsx"
)

BASE_URL = (
    'https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date={date}&type=ALL'
)


def fetch_csv(date: str) -> str:
    """Download CSV text for the specified date."""
    url = BASE_URL.format(date=date)
    logging.info('Start download %s', date)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        logging.info('Downloaded %s', date)
        return resp.content.decode('cp950', errors='ignore')
    except Exception as exc:
        logging.error('Failed to download %s: %s', date, exc)
        return ''


def parse_csv(text: str) -> List[Dict[str, Any]]:
    """Parse TWSE CSV text and return valid records with high price."""
    if not text:
        return []
    lines = [line for line in text.splitlines() if line and not line.startswith('=')]
    decoded = '\n'.join(lines)
    reader = csv.reader(io.StringIO(decoded))
    records = []
    for row in reader:
        # row[0]=code, row[1]=name, row[6]=high price, row[8]=close price
        if len(row) < 9 or not row[0].isdigit():
            continue
        high_str = row[6].strip().replace(',', '')
        close_str = row[8].strip().replace(',', '')
        try:
            high_price = float(high_str)
            close_price = float(close_str)
        except ValueError:
            continue
        records.append({
            'code': row[0].strip(),
            'name': row[1].strip(),
            'high': high_price,
            'close': close_price,
        })
    return records


def fetch_records(date: str, downloaded_dates: set) -> List[Dict[str, Any]]:
    """下載並解析指定日期的股票資料
    
    Args:
        date: 要下載的日期 (YYYYMMDD)
        downloaded_dates: 已下載的日期集合
    
    Returns:
        該日期的股票記錄清單
    """
    if date in downloaded_dates:
        logging.info("日期 %s 已下載過，從快取讀取資料", date)
        # 嘗試從快取讀取資料
        cached_records = load_cache_data(date)
        if cached_records:
            return cached_records
        else:
            logging.warning("快取資料不存在，重新下載: %s", date)
    
    # 下載新資料
    text = fetch_csv(date)
    records = parse_csv(text)
    logging.info('Parsed %d records for %s', len(records), date)
    
    # 下載成功後記錄到 TXT 檔案和快取
    if records:
        if date not in downloaded_dates:
            save_downloaded_date(date)
            downloaded_dates.add(date)
        # 儲存到快取
        save_cache_data(date, records)
    
    return records


def record_highest_prices(all_records: Dict[str, List[Dict[str, Any]]],
                          dates: List[str]) -> Dict[str, Dict[str, Any]]:
    """Return each stock's highest price in the base period."""
    highest: Dict[str, Dict[str, Any]] = {}
    for date in dates:
        records = all_records.get(date, [])
        for rec in records:
            current = highest.get(rec['code'])
            if not current or rec['high'] > current['high']:
                highest[rec['code']] = {
                    'high': rec['high'],
                    'date': date,
                    'name': rec['name'],
                }
    return highest


def compare_highs(highest: Dict[str, Dict[str, Any]],
                  all_records: Dict[str, List[Dict[str, Any]]],
                  dates: List[str]) -> List[Dict[str, Any]]:
    """Find stocks making new highs during the comparison period."""
    results: List[Dict[str, Any]] = []
    current_highest: Dict[str, float] = {c: info['high'] for c, info in highest.items()}

    for date in dates:
        records = all_records.get(date, [])
        record_map = {r['code']: r for r in records}
        for code, info in highest.items():
            today = record_map.get(code)
            if not today:
                continue
            if today['high'] > current_highest[code]:
                results.append({
                    'date': date,
                    'code': code,
                    'name': info['name'],
                    'close': today['close'],
                    'base_high': info['high'],
                    'high': today['high'],
                })
                current_highest[code] = today['high']
    return results


def save_price_records(data: Dict[str, List[Dict[str, Any]]], filename: str) -> None:
    path = os.path.join(OUTPUT_DIR, filename)
    wb = Workbook()
    ws = wb.active
    ws.append(['date', 'code', 'name', 'close'])
    
    # 按日期排序確保資料依時間順序輸出
    sorted_dates = sorted(data.keys())
    
    for date in sorted_dates:
        records = data[date]
        for rec in records:
            ws.append([date, rec['code'], rec['name'], f"{rec['close']:.2f}"])
    
    wb.save(path)
    logging.info('Saved price records to %s', path)


def save_comparison(results: List[Dict[str, Any]]) -> None:
    path = os.path.join(OUTPUT_DIR, COMPARISON_FILE)
    wb = Workbook()
    ws = wb.active
    ws.append(['code', 'name', 'date', 'close', 'base_high', 'new_high'])
    
    # 按日期排序確保比較結果依時間順序輸出
    sorted_results = sorted(results, key=lambda x: x['date'])
    
    for item in sorted_results:
        date_str = datetime.strptime(item['date'], '%Y%m%d').date()
        ws.append([
            item['code'],
            item['name'],
            date_str,
            f"{item['close']:.2f}",
            f"{item['base_high']:.2f}",
            f"{item['high']:.2f}",
        ])
    wb.save(path)
    logging.info('Saved comparison results to %s', path)


def load_downloaded_dates() -> set:
    """讀取已下載日期記錄檔案，回傳已下載日期的集合"""
    if not os.path.exists(DOWNLOADED_DATES_FILE):
        logging.info("已下載日期記錄檔案不存在，建立新檔案")
        return set()
    
    try:
        with open(DOWNLOADED_DATES_FILE, 'r', encoding='utf-8') as f:
            downloaded_dates = {line.strip() for line in f if line.strip()}
        logging.info("載入 %d 筆已下載日期記錄", len(downloaded_dates))
        return downloaded_dates
    except Exception as e:
        logging.error("讀取已下載日期記錄檔案失敗: %s", e)
        return set()


def save_downloaded_date(date: str) -> None:
    """將新下載的日期追加到記錄檔案中"""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(DOWNLOADED_DATES_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{date}\n")
        logging.info("記錄已下載日期: %s", date)
    except Exception as e:
        logging.error("寫入已下載日期記錄失敗: %s", e)


def save_cache_data(date: str, records: List[Dict[str, Any]]) -> None:
    """將下載的資料快取到本地檔案"""
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_file = os.path.join(CACHE_DIR, f"{date}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        logging.info("快取資料儲存成功: %s", date)
    except Exception as e:
        logging.error("快取資料儲存失敗 %s: %s", date, e)


def load_cache_data(date: str) -> List[Dict[str, Any]]:
    """從本地快取讀取資料"""
    try:
        cache_file = os.path.join(CACHE_DIR, f"{date}.json")
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                records = json.load(f)
            logging.info("從快取載入 %d 筆記錄: %s", len(records), date)
            return records
        return []
    except Exception as e:
        logging.error("快取資料讀取失敗 %s: %s", date, e)
        return []


def main() -> None:
    setup_logging()
    
    # 在程式開始時載入已下載的日期記錄 (只讀取一次)
    downloaded_dates = load_downloaded_dates()
    
    # 過濾出需要下載的日期
    dates_to_download = [date for date in ALL_DATES if date not in downloaded_dates]
    
    logging.info("總共需要處理 %d 個日期", len(ALL_DATES))
    logging.info("已下載過的日期: %d 個", len(downloaded_dates & set(ALL_DATES)))
    logging.info("需要新下載的日期: %d 個", len(dates_to_download))
    
    if dates_to_download:
        logging.info("開始下載新日期: %s", dates_to_download)
    else:
        logging.info("所有日期都已下載過，無需重複下載")
    
    # 下載資料：已下載的日期會被跳過，只下載新的日期
    all_records = {}
    for date in ALL_DATES:
        records = fetch_records(date, downloaded_dates)
        all_records[date] = records
    
    # 過濾出有資料的記錄進行分析
    valid_records = {date: records for date, records in all_records.items() if records}
    
    if not valid_records:
        logging.warning("沒有任何有效的資料記錄，無法進行分析")
        return
    
    logging.info("有效資料日期數: %d", len(valid_records))

    # Fetch each date only once to avoid duplicate downloads
    highest = record_highest_prices(valid_records, BASE_DATES)

    if valid_records:  # 只有在有資料時才儲存
        save_price_records(valid_records, RECORDS_FILE)

    comparison = compare_highs(highest, valid_records, COMPARE_DATES)
    save_comparison(comparison)
    logging.info('Analysis complete')


if __name__ == '__main__':
    main()
