import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
import sys
import os
import glob

NAMESPACE = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
BASE_DATE = date(1899, 12, 30)


def parse_xlsx(path):
    with zipfile.ZipFile(path) as z:
        xml_data = z.read('xl/worksheets/sheet1.xml')
    root = ET.fromstring(xml_data)
    rows = []
    for row in root.findall('.//a:row', NAMESPACE):
        cells = []
        for c in row.findall('a:c', NAMESPACE):
            if c.get('t') == 'inlineStr':
                t = c.find('a:is/a:t', NAMESPACE)
                text = t.text if t is not None else ''
            else:
                v = c.find('a:v', NAMESPACE)
                text = v.text if v is not None else ''
            cells.append(text)
        rows.append(cells)
    if not rows:
        return []
    header = rows[0]
    data = []
    for r in rows[1:]:
        if not r:
            continue
        item = dict(zip(header, r))
        if 'date' in item:
            try:
                serial = int(float(item['date']))
                item['date'] = str(BASE_DATE + timedelta(days=serial))
            except Exception:
                pass
        data.append(item)
    return data


def batch_convert():
    """批次轉換 output 資料夾中包含'比較'的 Excel 檔案為 JSON"""
    # 取得當前腳本的目錄
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, 'output')
    
    # 檢查 output 資料夾是否存在
    if not os.path.exists(output_dir):
        print(f'錯誤: output 資料夾不存在 ({output_dir})')
        sys.exit(1)
    
    # 尋找所有的 Excel 檔案
    all_xlsx_files = glob.glob(os.path.join(output_dir, '*.xlsx'))
    
    # 只篩選包含'比較'且不是臨時檔案的檔案
    xlsx_files = [f for f in all_xlsx_files 
                  if '比較' in os.path.basename(f) 
                  and not os.path.basename(f).startswith('~$')]
    
    if not xlsx_files:
        print('在 output 資料夾中找不到包含"比較"的 Excel 檔案')
        print(f'搜尋路徑: {output_dir}')
        if all_xlsx_files:
            print(f'找到 {len(all_xlsx_files)} 個 Excel 檔案，但沒有包含"比較"的檔案')
        else:
            print('output 資料夾中沒有任何 Excel 檔案')
        sys.exit(1)    
    print(f'找到 {len(xlsx_files)} 個比較類型的 Excel 檔案需要轉換:')
    
    success_count = 0
    error_count = 0
    
    for xlsx_path in xlsx_files:
        try:
            # 建立對應的 JSON 檔案路徑
            json_path = xlsx_path.replace('.xlsx', '.json')
            
            print(f'正在轉換: {os.path.basename(xlsx_path)} -> {os.path.basename(json_path)}')
            
            # 解析 Excel 檔案
            data = parse_xlsx(xlsx_path)
              # 寫入 JSON 檔案
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f'[OK] 成功轉換: {os.path.basename(json_path)}')
            success_count += 1
            
        except FileNotFoundError as e:
            print(f'[ERROR] 檔案未找到 {os.path.basename(xlsx_path)}: {str(e)}')
            error_count += 1
        except PermissionError as e:
            print(f'[ERROR] 權限錯誤 {os.path.basename(xlsx_path)}: 檔案可能正在被使用中')
            error_count += 1
        except Exception as e:
            print(f'[ERROR] 轉換失敗 {os.path.basename(xlsx_path)}: {str(e)}')
            error_count += 1
    
    print(f'批次轉換完成! 成功: {success_count}, 失敗: {error_count}')
    
    # 如果有錯誤，返回非零退出碼
    if error_count > 0:
        sys.exit(1)


def main():
    if len(sys.argv) == 1:
        # 沒有參數時執行批次轉換
        batch_convert()
    elif len(sys.argv) == 2 and sys.argv[1] == '--batch':
        # 明確指定批次轉換
        batch_convert()
    elif len(sys.argv) == 3:
        # 原有的單檔轉換功能
        xlsx_path, json_path = sys.argv[1], sys.argv[2]
        try:
            data = parse_xlsx(xlsx_path)
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f'成功轉換: {xlsx_path} -> {json_path}')
        except Exception as e:
            print(f'轉換失敗: {str(e)}')
            sys.exit(1)
    else:
        print('使用方式:')
        print('  python convert_excel_to_json.py                    # 批次轉換 output 資料夾中包含"比較"的 Excel 檔案')
        print('  python convert_excel_to_json.py --batch            # 批次轉換 output 資料夾中包含"比較"的 Excel 檔案')
        print('  python convert_excel_to_json.py input.xlsx output.json  # 轉換單一檔案')
        sys.exit(1)


if __name__ == '__main__':
    main()
