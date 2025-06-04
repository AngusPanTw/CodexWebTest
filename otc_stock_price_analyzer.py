import csv
import io
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

import requests
from openpyxl import Workbook

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
LOG_FILE = os.path.join(OUTPUT_DIR, 'otc_stock_price_analyzer.log')

TRADING_DAYS_URL = 'https://www.tpex.org.tw/openapi/v1/exchange/suspension_trading_days?l=zh-tw'
DAILY_URL = ('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
             '?l=zh-tw&d={date}&s=0,asc,0')


def setup_logging() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler()
        ],
    )


def to_roc_date(date: str) -> str:
    dt = datetime.strptime(date, '%Y%m%d')
    return f"{dt.year - 1911:03d}/{dt.month:02d}/{dt.day:02d}"


def fetch_trading_days(start: str, end: str) -> List[str]:
    try:
        response = requests.get(TRADING_DAYS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logging.error('Failed to fetch trading days: %s', exc)
        return []

    start_dt = datetime.strptime(start, '%Y%m%d')
    end_dt = datetime.strptime(end, '%Y%m%d')
    days: List[str] = []
    for item in data:
        if item.get('TradingType') != '0':
            continue
        roc_date = item.get('Date')
        try:
            y, m, d = map(int, roc_date.split('/'))
            g_dt = datetime(y + 1911, m, d)
        except Exception:
            continue
        if start_dt <= g_dt <= end_dt:
            days.append(g_dt.strftime('%Y%m%d'))
    return sorted(days)


def fetch_records(date: str) -> List[Dict[str, Any]]:
    roc = to_roc_date(date)
    url = DAILY_URL.format(date=roc)
    logging.info('Start download %s', date)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logging.error('Failed to download %s: %s', date, exc)
        return []

    records: List[Dict[str, Any]] = []
    for item in data:
        code = item.get('Code') or item.get('SecuritiesCompanyCode')
        if not code or not code.isdigit() or len(code) != 4:
            continue
        name = item.get('Name') or item.get('SecuritiesCompanyAbbr')
        low_str = item.get('Low') or item.get('Min') or item.get('LowestPrice')
        close_str = item.get('Close') or item.get('ClosingPrice')
        try:
            low = float(str(low_str).replace(',', ''))
            close = float(str(close_str).replace(',', ''))
        except (ValueError, TypeError):
            continue
        records.append({'code': code, 'name': name, 'low': low, 'close': close})
    logging.info('Parsed %d records for %s', len(records), date)
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
                continue
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
    path = os.path.join(OUTPUT_DIR, filename)
    wb = Workbook()
    ws = wb.active
    ws.append(['date', 'code', 'name', 'close'])
    for date, records in data.items():
        for rec in records:
            ws.append([date, rec['code'], rec['name'], f"{rec['close']:.2f}"])
    wb.save(path)
    logging.info('Saved price records to %s', path)


def save_comparison(results: List[Dict[str, Any]], filename: str) -> None:
    path = os.path.join(OUTPUT_DIR, filename)
    wb = Workbook()
    ws = wb.active
    ws.append(['code', 'name', 'date', 'close', 'base_low', 'new_low'])
    for item in results:
        dt = datetime.strptime(item['date'], '%Y%m%d').date()
        ws.append([
            item['code'],
            item['name'],
            dt,
            f"{item['close']:.2f}",
            f"{item['base_low']:.2f}",
            f"{item['low']:.2f}",
        ])
    wb.save(path)
    logging.info('Saved comparison results to %s', path)


ALL_DATES = fetch_trading_days('20250407', '20250604')
BASE_DATES = [d for d in ALL_DATES if '20250407' <= d <= '20250525']
COMPARE_DATES = [d for d in ALL_DATES if '20250526' <= d <= '20250604']

RECORDS_FILE = f"OTC_stock_records_{ALL_DATES[0]}_{ALL_DATES[-1]}.xlsx" if ALL_DATES else 'OTC_stock_records.xlsx'
COMPARISON_FILE = (
    f"OTC_stock_price_comparison_{COMPARE_DATES[0]}_{COMPARE_DATES[-1]}.xlsx"
    if COMPARE_DATES else 'OTC_stock_price_comparison.xlsx'
)


def main() -> None:
    setup_logging()

    all_records = {d: fetch_records(d) for d in ALL_DATES}
    lowest = record_lowest_prices(BASE_DATES)

    save_price_records(all_records, RECORDS_FILE)

    comparison = compare_prices(lowest, COMPARE_DATES)
    save_comparison(comparison, COMPARISON_FILE)
    logging.info('Analysis complete')


if __name__ == '__main__':
    main()
