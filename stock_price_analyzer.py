import csv
import io
import os
from datetime import datetime
from typing import Dict, List, Any

import requests

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')

APR_DATES = [
    '20250407', '20250408', '20250409', '20250410', '20250411',
    '20250412', '20250413', '20250414', '20250415', '20250416',
    '20250417', '20250418', '20250419', '20250420', '20250421',
    '20250422', '20250423', '20250424', '20250425', '20250426',
    '20250427', '20250428', '20250429', '20250430',
]

JUN_DATES = [
    '20250601',
    '20250602',
    '20250603',
    '20250604',
]

# Output filenames include "TSE" to標示上市股票
RECORDS_FILE = f"TSE_stock_records_{APR_DATES[0]}_{JUN_DATES[-1]}.txt"
COMPARISON_FILE = f"TSE_stock_price_comparison_{JUN_DATES[0]}_{JUN_DATES[-1]}.txt"

BASE_URL = 'https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date={date}&type=ALL'


def fetch_csv(date: str) -> str:
    """Download CSV text for the specified date."""
    url = BASE_URL.format(date=date)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        # TWSE files use Big5 (CP950) encoding
        return response.content.decode('cp950', errors='ignore')
    except Exception as exc:
        print(f"Failed to download data for {date}: {exc}")
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
    return parse_csv(text)


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
                    'apr_low': info['low'],
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


def save_comparison(results: List[Dict[str, Any]]) -> None:
    """Save comparison results to COMPARISON_FILE."""
    path = os.path.join(OUTPUT_DIR, COMPARISON_FILE)
    with open(path, 'w', encoding='utf-8') as f:
        for item in results:
            date_str = datetime.strptime(item['date'], '%Y%m%d').date()
            f.write(
                f"{item['code']},{item['name']},{date_str}創新低,"
                f"收盤價{item['close']:.2f},(4月低點:{item['apr_low']:.2f}),"
                f"新低價{item['low']:.2f}\n"
            )


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    april_records = {d: fetch_records(d) for d in APR_DATES}
    lowest = record_lowest_prices(APR_DATES)

    june_records = {d: fetch_records(d) for d in JUN_DATES}

    # Save raw trading data covering April and June dates
    save_price_records({**april_records, **june_records}, RECORDS_FILE)

    comparison = compare_prices(lowest, JUN_DATES)
    save_comparison(comparison)


if __name__ == '__main__':
    main()
