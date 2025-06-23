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
from datetime import datetime, timedelta
from typing import Dict, List, Any

import requests
from openpyxl import Workbook

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
LOG_FILE = os.path.join(OUTPUT_DIR, 'stock_price_high_analyzer.log')


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

# Output filenames include "TSE" to 標示上市股票
RECORDS_FILE = f"TSE_stock_high_records_{ALL_DATES[0]}_{ALL_DATES[-1]}.xlsx"
COMPARISON_FILE = (
    f"TSE_stock_price_highs_{COMPARE_DATES[0]}_{COMPARE_DATES[-1]}.xlsx"
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


def fetch_records(date: str) -> List[Dict[str, Any]]:
    text = fetch_csv(date)
    records = parse_csv(text)
    logging.info('Parsed %d records for %s', len(records), date)
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
    for date, records in data.items():
        for rec in records:
            ws.append([date, rec['code'], rec['name'], f"{rec['close']:.2f}"])
    wb.save(path)
    logging.info('Saved price records to %s', path)


def save_comparison(results: List[Dict[str, Any]]) -> None:
    path = os.path.join(OUTPUT_DIR, COMPARISON_FILE)
    wb = Workbook()
    ws = wb.active
    ws.append(['code', 'name', 'date', 'close', 'base_high', 'new_high'])
    for item in results:
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


def main() -> None:
    setup_logging()

    # Fetch each date only once to avoid duplicate downloads
    all_records = {d: fetch_records(d) for d in ALL_DATES}
    highest = record_highest_prices(all_records, BASE_DATES)

    save_price_records(all_records, RECORDS_FILE)

    comparison = compare_highs(highest, all_records, COMPARE_DATES)
    save_comparison(comparison)
    logging.info('Analysis complete')


if __name__ == '__main__':
    main()
