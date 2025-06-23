import json
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta
import sys

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


def main():
    if len(sys.argv) != 3:
        print('Usage: python convert_excel_to_json.py input.xlsx output.json')
        sys.exit(1)
    xlsx_path, json_path = sys.argv[1], sys.argv[2]
    data = parse_xlsx(xlsx_path)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
