#!/usr/bin/env python3
"""
从 GeoNames cities15000.txt 生成离线城市搜索库 data/cities.json
输出格式: [{name, full, lat, lng, country, py}, ...]
  - name: 短名 (中文优先，否则 ASCII)
  - full: 展示名 (国家 - 省/州 - 城市)
  - lat / lng: 经纬度
  - country: 国家名
  - py: 拼音/ASCII (用于搜索)
"""
import csv
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

GEONAMES_FILE = "/tmp/cities15000.txt"
OUTPUT_FILE = os.path.join(PROJECT_DIR, "data", "cities.json")

# GeoNames country codes → 中文名
COUNTRY_ZH = {}

# 下载 countryInfo.txt 获取国家名
COUNTRY_INFO = "/tmp/countryInfo.txt"

import re
import urllib.request

def download_country_info():
    """下载 GeoNames 国家信息表"""
    if os.path.exists(COUNTRY_INFO) and os.path.getsize(COUNTRY_INFO) > 1000:
        return
    url = "https://download.geonames.org/export/dump/countryInfo.txt"
    urllib.request.urlretrieve(url, COUNTRY_INFO)

def load_country_zh():
    """从 countryInfo 中提取 country_code → 中文名(列16) 或英文名(列4)"""
    download_country_info()
    with open(COUNTRY_INFO, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue
            code = parts[0]
            name_en = parts[4]
            COUNTRY_ZH[code] = name_en

    # 手动补充常用国家中文名
    zh_map = {
        "CN": "中国", "JP": "日本", "KR": "韩国", "US": "美国", "GB": "英国",
        "FR": "法国", "DE": "德国", "IT": "意大利", "ES": "西班牙", "AU": "澳大利亚",
        "CA": "加拿大", "RU": "俄罗斯", "BR": "巴西", "IN": "印度", "TH": "泰国",
        "VN": "越南", "SG": "新加坡", "MY": "马来西亚", "ID": "印度尼西亚",
        "PH": "菲律宾", "NZ": "新西兰", "MX": "墨西哥", "AR": "阿根廷",
        "EG": "埃及", "ZA": "南非", "TR": "土耳其", "AE": "阿联酋",
        "SA": "沙特阿拉伯", "PT": "葡萄牙", "NL": "荷兰", "BE": "比利时",
        "SE": "瑞典", "NO": "挪威", "DK": "丹麦", "FI": "芬兰", "CH": "瑞士",
        "AT": "奥地利", "PL": "波兰", "CZ": "捷克", "GR": "希腊", "IE": "爱尔兰",
        "HU": "匈牙利", "RO": "罗马尼亚", "UA": "乌克兰", "IL": "以色列",
        "KP": "朝鲜", "MN": "蒙古", "MM": "缅甸", "KH": "柬埔寨",
        "LA": "老挝", "NP": "尼泊尔", "LK": "斯里兰卡", "PK": "巴基斯坦",
        "BD": "孟加拉国", "KZ": "哈萨克斯坦", "UZ": "乌兹别克斯坦",
        "TW": "中国台湾", "HK": "中国香港", "MO": "中国澳门",
        "PE": "秘鲁", "CL": "智利", "CO": "哥伦比亚", "CU": "古巴",
        "QA": "卡塔尔", "KW": "科威特", "JO": "约旦", "LB": "黎巴嫩",
        "IR": "伊朗", "IQ": "伊拉克", "NG": "尼日利亚", "KE": "肯尼亚",
        "ET": "埃塞俄比亚", "TZ": "坦桑尼亚", "MA": "摩洛哥",
        "HR": "克罗地亚", "RS": "塞尔维亚", "BG": "保加利亚", "SK": "斯洛伐克",
        "SI": "斯洛文尼亚", "LT": "立陶宛", "LV": "拉脱维亚", "EE": "爱沙尼亚",
    }
    for code, zh in zh_map.items():
        COUNTRY_ZH[code] = zh

def has_chinese(s):
    return bool(re.search(r'[\u4e00-\u9fff]', s))

def has_non_cjk_non_ascii(s):
    """检测是否含有日文假名/韩文等非中文的 Unicode 字符"""
    return bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', s))

def pick_chinese_name(alternatenames):
    """从 alternatenames 逗号分隔列表中选取一个中文名"""
    if not alternatenames:
        return None
    names = alternatenames.split(",")
    for n in names:
        n = n.strip()
        if has_chinese(n) and not has_non_cjk_non_ascii(n):
            return n
    return None

CN_PROVINCE_ZH = {
    "01": "安徽", "02": "浙江", "03": "江西", "04": "江苏", "05": "吉林",
    "06": "青海", "07": "福建", "08": "黑龙江", "09": "河南", "10": "河北",
    "11": "湖南", "12": "湖北", "13": "新疆", "14": "西藏", "15": "甘肃",
    "16": "广西", "18": "贵州", "19": "辽宁", "20": "内蒙古", "21": "宁夏",
    "22": "北京", "23": "上海", "24": "山西", "25": "山东", "26": "陕西",
    "28": "天津", "29": "云南", "30": "广东", "31": "海南", "32": "四川",
    "33": "重庆",
}

def download_cn_admin():
    """下载中国行政区划数据 (admin1/admin2)"""
    admin1_file = "/tmp/admin1CodesASCII.txt"
    if not os.path.exists(admin1_file):
        urllib.request.urlretrieve(
            "https://download.geonames.org/export/dump/admin1CodesASCII.txt",
            admin1_file
        )
    admin1 = {}
    with open(admin1_file, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                code = parts[0]
                name = parts[1]
                # 中国省份用中文
                if code.startswith("CN."):
                    cn_code = code.split(".")[1]
                    zh = CN_PROVINCE_ZH.get(cn_code)
                    if zh:
                        name = zh
                admin1[code] = name
    return admin1

def build_cities():
    load_country_zh()
    admin1_map = download_cn_admin()

    cities = []
    seen = set()

    with open(GEONAMES_FILE, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) < 15:
                continue
            geonameid = row[0]
            name = row[1]            # 地名
            asciiname = row[2]       # ASCII 名
            alternatenames = row[3]  # 别名列表
            lat = row[4]
            lng = row[5]
            feature_class = row[6]
            feature_code = row[7]
            country_code = row[8]
            admin1_code = row[10]
            population = int(row[14]) if row[14] else 0

            # 选中文名
            zh_name = pick_chinese_name(alternatenames)
            display_name = zh_name or name

            # 中国条目必须有中文名
            if country_code == "CN" and not zh_name:
                continue

            # 国家中文名
            country_zh = COUNTRY_ZH.get(country_code, country_code)

            # 省/州
            admin1_key = f"{country_code}.{admin1_code}"
            admin1_name = admin1_map.get(admin1_key, "")
            # 尝试从 admin1 别名中取中文
            admin1_display = admin1_name

            # 构建展示名: 国家 - 省/州 - 城市
            parts = []
            if country_zh:
                parts.append(country_zh)
            if admin1_display and admin1_display != display_name:
                parts.append(admin1_display)
            if display_name not in parts:
                parts.append(display_name)
            full = " - ".join(parts)

            # 去重键
            dedup_key = f"{round(float(lat), 3)},{round(float(lng), 3)}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            cities.append({
                "n": display_name,
                "f": full,
                "la": round(float(lat), 4),
                "ln": round(float(lng), 4),
                "c": country_zh,
                "p": asciiname.lower(),
            })

    # 按国家 → 名称排序
    cities.sort(key=lambda x: (x["c"], x["f"]))
    return cities

def add_cn_districts():
    """追加中国县/区级数据（从 GeoNames CN 数据）"""
    cn_file = "/tmp/CN.zip"
    cn_txt = "/tmp/CN.txt"
    if not os.path.exists(cn_txt):
        urllib.request.urlretrieve(
            "https://download.geonames.org/export/dump/CN.zip", cn_file
        )
        import zipfile
        with zipfile.ZipFile(cn_file, "r") as z:
            z.extractall("/tmp/")

    admin1_map = download_cn_admin()
    districts = []
    seen = set()

    with open(cn_txt, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        for row in reader:
            if len(row) < 15:
                continue
            feature_code = row[7]
            # ADM2 = 地级市, ADM3 = 县/区
            if feature_code not in ("ADM2", "ADM3", "PPLA2", "PPLA3"):
                continue
            name = row[1]
            asciiname = row[2]
            alternatenames = row[3]
            lat = row[4]
            lng = row[5]
            admin1_code = row[10]

            zh_name = pick_chinese_name(alternatenames)
            if not zh_name:
                continue
            admin1_key = f"CN.{admin1_code}"
            province = admin1_map.get(admin1_key, "")

            parts = ["中国"]
            if province and province != zh_name:
                parts.append(province)
            if zh_name not in parts:
                parts.append(zh_name)
            full = " - ".join(parts)

            dedup_key = f"{round(float(lat), 3)},{round(float(lng), 3)}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            districts.append({
                "n": zh_name,
                "f": full,
                "la": round(float(lat), 4),
                "ln": round(float(lng), 4),
                "c": "中国",
                "p": asciiname.lower(),
            })

    return districts

def main():
    print("Loading cities15000...")
    cities = build_cities()
    print(f"  → {len(cities)} cities from cities15000")

    print("Loading CN districts...")
    cn_districts = add_cn_districts()
    print(f"  → {len(cn_districts)} CN districts")

    # 合并去重
    seen = set()
    merged = []
    for c in cities:
        key = f"{c['la']},{c['ln']}"
        if key not in seen:
            seen.add(key)
            merged.append(c)
    for c in cn_districts:
        key = f"{c['la']},{c['ln']}"
        if key not in seen:
            seen.add(key)
            merged.append(c)

    merged.sort(key=lambda x: (x["c"], x["f"]))
    print(f"  → {len(merged)} total after merge")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"Written to {OUTPUT_FILE} ({size_kb:.0f} KB)")

if __name__ == "__main__":
    main()
