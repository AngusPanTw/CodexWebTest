import csv
import io
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

import requests

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
LOG_FILE = os.path.join(OUTPUT_DIR, 'stock_price_analyzer.log')


def setup_logging() -> None:
    """Configure logging to file and console."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ],
    )


def generate_dates(start: str, end: str) -> List[str]:
    """Generate YYYYMMDD strings for weekdays between start and end inclusive."""
    begin = datetime.strptime(start, '%Y%m%d')
    finish = datetime.strptime(end, '%Y%m%d')
    dates: List[str] = []
    current = begin
    while current <= finish:
        if current.weekday() < 5:  # Monday-Friday
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)
    return dates


ALL_DATES = generate_dates('20250407', '20250604')
BASE_DATES = generate_dates('20250407', '20250525')
COMPARE_DATES = generate_dates('20250526', '20250604')

# Output filenames include "TSE" to標示上市股票
RECORDS_FILE = f"TSE_stock_records_{ALL_DATES[0]}_{ALL_DATES[-1]}.txt"
COMPARISON_FILE = f"TSE_stock_price_comparison_{COMPARE_DATES[0]}_{COMPARE_DATES[-1]}.txt"

BASE_URL = 'https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date={date}&type=ALL'


def fetch_csv(date: str) -> str:
    """Download CSV text for the specified date."""
    url = BASE_URL.format(date=date)
    logging.info("Start download %s", date)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        logging.info("Downloaded %s", date)
        # TWSE files use Big5 (CP950) encoding
        return response.content.decode('cp950', errors='ignore')
    except Exception as exc:
        logging.error("Failed to download %s: %s", date, exc)
        return ''


def parse_csv(text: str) -> List[Dict[str, Any]]:
    """Parse CSV text encoded as Big5/CP950 and return valid stock rows."""
    if not text:
        return []
    # Remove comment lines starting with '=' and empty lines
    lines = [line for line in text.splitlines() if line and not line.startswith('=')]
    decoded = '\n'.join(lines)
    reader = csv.reader(io.StringIO(decoded))
    records = []
    for row in reader:
        # Expected row[0] is code, row[1] is name, row[7] is low price, row[8] is closing price
        if len(row) < 9 or not row[0].isdigit():
            continue
        low_str = row[7].strip().replace(',', '')
        close_str = row[8].strip().replace(',', '')
        try:
            low_price = float(low_str)
            close_price = float(close_str)
        except ValueError:
            continue
        records.append({
            'code': row[0].strip(),
            'name': row[1].strip(),
            'low': low_price,
            'close': close_price,
        })
    return records


def fetch_records(date: str) -> List[Dict[str, Any]]:
    text = fetch_csv(date)
    records = parse_csv(text)
    logging.info("Parsed %d records for %s", len(records), date)
    return records


def record_lowest_prices(dates: List[str]) -> Dict[str, Dict[str, Any]]:
    lowest: Dict[str, Dict[str, Any]] = {}
    for date in dates:
        records = fetch_records(date)
        for rec in records:
            current = lowest.get(rec['code'])
            if not current or rec['low'] < current['low']:
                lowest[rec['code']] = {
                    'low': rec['low'],
                    'date': date,
                    'name': rec['name'],
                }
    return lowest


def compare_prices(lowest: Dict[str, Dict[str, Any]], dates: List[str]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for date in dates:
        records = fetch_records(date)
        record_map = {r['code']: r for r in records}
        for code, info in lowest.items():
            today = record_map.get(code)
            if not today:
                continue  # No trading data for this stock on the date
            if today['low'] < info['low']:
                results.append({
                    'date': date,
                    'code': code,
                    'name': info['name'],
                    'close': today['close'],
                    'base_low': info['low'],
                    'low': today['low'],
                })
    return results


def save_price_records(data: Dict[str, List[Dict[str, Any]]], filename: str) -> None:
    """Save raw price records to the given filename."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        for date, records in data.items():
            for rec in records:
                f.write(f"{date},{rec['code']},{rec['name']},{rec['close']:.2f}\n")
    logging.info("Saved price records to %s", path)


def save_comparison(results: List[Dict[str, Any]]) -> None:
    """Save comparison results to COMPARISON_FILE."""
    path = os.path.join(OUTPUT_DIR, COMPARISON_FILE)
    with open(path, 'w', encoding='utf-8') as f:
        for item in results:
            date_str = datetime.strptime(item['date'], '%Y%m%d').date()
            f.write(
                f"{item['code']},{item['name']},{date_str}創新低,"
                f"收盤價{item['close']:.2f},(基準低點:{item['base_low']:.2f}),"
                f"新低價{item['low']:.2f}\n"
            )
    logging.info("Saved comparison results to %s", path)


def main():
    setup_logging()
    
    all_records = {d: fetch_records(d) for d in ALL_DATES}
    lowest = record_lowest_prices(BASE_DATES)

    # Save raw trading data covering April到六月初期間
    save_price_records(all_records, RECORDS_FILE)

    comparison = compare_prices(lowest, COMPARE_DATES)
    save_comparison(comparison)
    logging.info("Analysis complete")


if __name__ == '__main__':
    main()