# 05_clean_dianping_joint_filter_v3.py - 修复版：增加粤港澳城市过滤
import pandas as pd
import numpy as np
import requests
import time
import os
import re
from collections import defaultdict

# ==================== 配置 ====================
GAODE_KEY = "c067a7d78f9ccb6f708344ca1f40f5e8"

GBA_CITIES = [
    {"name": "广州市", "adcode": "440100"},
    {"name": "深圳市", "adcode": "440300"},
    {"name": "珠海市", "adcode": "440400"},
    {"name": "佛山市", "adcode": "440600"},
    {"name": "惠州市", "adcode": "441300"},
    {"name": "东莞市", "adcode": "441900"},
    {"name": "中山市", "adcode": "442000"},
    {"name": "江门市", "adcode": "440700"},
    {"name": "肇庆市", "adcode": "441200"},
    {"name": "香港", "adcode": "810000"},
    {"name": "澳门", "adcode": "820000"}
]

# ========== 新增：粤港澳城市过滤关键词 ==========
GBA_CITY_KEYWORDS = [
    "广州", "深圳", "珠海", "佛山", "惠州", "东莞", "中山", "江门", "肇庆",
    "香港", "澳门", "粤港澳", "大湾区", "珠江", "越秀", "荔湾", "海珠",
    "天河", "白云", "黄埔", "番禺", "花都", "南沙", "从化", "增城",
    "罗湖", "福田", "南山", "宝安", "龙岗", "盐田", "龙华", "坪山", "光明",
    "香洲", "斗门", "金湾", "禅城", "南海", "顺德", "三水", "高明",
    "惠城", "惠阳", "博罗", "惠东", "龙门", "莞城", "东城", "南城", "万江",
    "石岐", "东区", "西区", "南区", "五桂山", "蓬江", "江海", "新会",
    "台山", "开平", "鹤山", "恩平", "端州", "鼎湖", "高要", "广宁", "怀集",
    "封开", "德庆", "四会", "尖沙咀", "铜锣湾", "中环", "旺角", "澳门半岛",
    "氹仔", "路环", "长隆", "白云山", "莲花山", "梧桐山", "西樵山", "罗浮山",
    "丹霞山", "鼎湖山", "七星岩", "惠州西湖", "松山湖", "红树林", "大梅沙",
    "小梅沙", "较场尾", "大鹏所城", "华侨城", "世界之窗", "欢乐谷"
]

# 明确排除的非粤港澳城市（防止误判）
EXCLUDE_CITIES = ["杭州", "上海", "北京", "南京", "成都", "西安", "武汉", "重庆",
                  "苏州", "宁波", "天津", "青岛", "大连", "厦门", "长沙", "郑州",
                  "济南", "福州", "合肥", "南昌", "昆明", "贵阳", "南宁", "海口",
                  "三亚", "哈尔滨", "沈阳", "长春", "石家庄", "太原", "兰州",
                  "银川", "西宁", "拉萨", "乌鲁木齐", "呼和浩特", "无锡", "常州",
                  "徐州", "南通", "扬州", "盐城", "淮安", "连云港", "泰州", "宿迁",
                  "镇江", "江阴", "宜兴", "常熟", "张家港", "昆山", "吴江", "太仓",
                  "溧阳", "丹阳", "扬中", "句容", "靖江", "泰兴", "兴化", "如皋",
                  "海门", "启东", "如东", "海安", "通州", "海门", "启东", "如皋",
                  "如东", "海安", "通州", "海门", "启东", "如皋", "如东", "海安",
                  "西湖", "断桥", "白堤", "苏堤", "雷峰塔", "灵隐寺", "三潭印月"]

RAW_RATINGS_FILE = r"C:\Users\LENGDA\PycharmProjects\pythonProject\travel\yf_dianping\ratings\ratings.csv"
CLEANED_DATA_DIR = r"C:\Users\LENGDA\PycharmProjects\pythonProject\travel\cleaned_data"
CLEANED_RATINGS_FILE = os.path.join(CLEANED_DATA_DIR, "cleaned_ratings_joint.csv")
GBA_SPOTS_CACHE = os.path.join(CLEANED_DATA_DIR, "gba_spots_cache.csv")


def ensure_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"创建目录: {directory}")


def fetch_gba_spots_from_gaode():
    """获取粤港澳大湾区景点列表"""
    print("=" * 70)
    print("正在通过高德地图API获取粤港澳大湾区景点...")
    print("=" * 70)

    all_spots = []

    for city in GBA_CITIES:
        city_name = city["name"]
        adcode = city["adcode"]
        print(f"\n正在获取 → {city_name}")

        url = "https://restapi.amap.com/v3/place/text"

        for page in range(1, 5):
            params = {
                "key": GAODE_KEY,
                "keywords": "旅游景点",
                "types": "风景名胜|景点公园|文化古迹|自然公园|博物馆|主题公园",
                "city": adcode,
                "offset": 25,
                "page": page,
                "output": "json",
                "extensions": "all"
            }

            try:
                res = requests.get(url, params=params, timeout=15)
                data = res.json()

                if data.get("pois"):
                    for poi in data["pois"]:
                        spot_info = {
                            "name": poi.get("name", ""),
                            "city": city_name,
                            "type": poi.get("type", ""),
                        }
                        all_spots.append(spot_info)

                time.sleep(0.3)
            except Exception as e:
                print(f"  第{page}页失败: {e}")

        print(f"  {city_name}: {len([s for s in all_spots if s['city'] == city_name])} 个景点")

    print(f"\n总计获取: {len(all_spots)} 个景点")

    ensure_dir(CLEANED_DATA_DIR)
    df_spots = pd.DataFrame(all_spots)
    df_spots.to_csv(GBA_SPOTS_CACHE, index=False, encoding='utf-8-sig')
    print(f"景点列表已缓存: {GBA_SPOTS_CACHE}")

    return all_spots


def load_gba_spots():
    """加载景点列表"""
    if os.path.exists(GBA_SPOTS_CACHE):
        print("从缓存加载景点列表...")
        df = pd.read_csv(GBA_SPOTS_CACHE)
        print(f"  加载完成: {len(df)} 个景点")
        return df.to_dict('records')
    else:
        return fetch_gba_spots_from_gaode()


def extract_core_keywords(spot_list):
    """
    提取核心关键词（优化版）
    只保留景点完整名称和核心词，去掉2-3字的碎片
    """
    print("\n正在提取核心关键词...")

    keyword_to_spots = defaultdict(list)

    for spot in spot_list:
        name = spot.get("name", "").strip()
        if not name or len(name) < 3:
            continue

        # 1. 完整名称（最高优先级）
        keyword_to_spots[name].append(name)

        # 2. 去掉常见后缀后的核心名称
        suffixes = ["风景区", "旅游区", "景区", "公园", "游乐园", "乐园",
                    "博物馆", "纪念馆", "展览馆", "美术馆",
                    "古镇", "古城", "老街", "古村",
                    "寺庙", "寺", "庙", "教堂"]

        core_name = name
        for suffix in suffixes:
            if name.endswith(suffix) and len(name) > len(suffix) + 1:
                core_name = name[:-len(suffix)]
                keyword_to_spots[core_name].append(name)
                break

        # 3. 只保留4字以上的核心词（避免太短的碎片匹配太多）
        if len(core_name) >= 4:
            keyword_to_spots[core_name].append(name)

    # 去重
    final_keywords = {}
    for kw, spots in keyword_to_spots.items():
        unique_spots = list(set(spots))
        # 只保留匹配景点数 <= 3 的关键词（避免太通用的词）
        if len(unique_spots) <= 3 and len(kw) >= 3:
            final_keywords[kw] = unique_spots

    print(f"  提取了 {len(final_keywords)} 个核心关键词")

    # 显示示例
    print(f"\n关键词示例（Top 20）:")
    sorted_kws = sorted(final_keywords.items(), key=lambda x: len(x[1]), reverse=True)
    for kw, spots in sorted_kws[:20]:
        print(f"  '{kw}' → {spots}")

    return final_keywords


def fast_filter_comments(raw_file, keyword_map):
    """
    快速筛选评论（修复版：增加粤港澳城市过滤）
    """
    print("\n" + "=" * 70)
    print("开始快速筛选景点相关评论（含城市过滤）...")
    print("=" * 70)

    # 大类关键词（快速预过滤）
    broad_keywords = ["景区", "景点", "风景区", "公园", "游乐园", "博物馆",
                      "古镇", "寺庙", "山", "湖", "海", "门票", "游览", "游玩",
                      "风景", "景色", "导游", "参观"]
    broad_pattern = re.compile('|'.join(re.escape(kw) for kw in broad_keywords), re.IGNORECASE)

    # 核心关键词（精确匹配）
    core_keywords = list(keyword_map.keys())
    # 按长度排序，长的优先（避免短词覆盖）
    core_keywords.sort(key=len, reverse=True)
    core_pattern = re.compile('|'.join(re.escape(kw) for kw in core_keywords))

    # 城市过滤正则
    gba_pattern = re.compile('|'.join(re.escape(kw) for kw in GBA_CITY_KEYWORDS))
    exclude_pattern = re.compile('|'.join(re.escape(kw) for kw in EXCLUDE_CITIES))

    print(f"大类关键词: {len(broad_keywords)} 个")
    print(f"核心关键词: {len(core_keywords)} 个")
    print(f"粤港澳城市关键词: {len(GBA_CITY_KEYWORDS)} 个")
    print(f"排除城市: {len(EXCLUDE_CITIES)} 个")

    chunk_size = 100000
    matched_comments = []
    total_processed = 0
    total_matched = 0
    broad_matched = 0
    city_filtered = 0  # 城市过滤统计
    exclude_filtered = 0  # 排除城市统计
    match_stats = defaultdict(int)

    start_time = time.time()

    for chunk_idx, chunk in enumerate(pd.read_csv(raw_file, chunksize=chunk_size)):
        total_processed += len(chunk)
        chunk = chunk[chunk['comment'].notna()]

        for _, row in chunk.iterrows():
            comment = str(row['comment'])

            # 步骤1：快速预过滤（大类关键词）
            if not broad_pattern.search(comment):
                continue

            broad_matched += 1

            # ========== 新增：步骤1.5 城市过滤 ==========
            # 检查是否包含明确排除的城市（如杭州、上海）
            if exclude_pattern.search(comment):
                exclude_filtered += 1
                continue

            # 检查是否包含粤港澳城市关键词
            if not gba_pattern.search(comment):
                city_filtered += 1
                continue

            # 步骤2：精确匹配核心关键词
            match = core_pattern.search(comment)
            if match:
                matched_kw = match.group(0)
                related_spots = keyword_map.get(matched_kw, [])

                matched_comments.append({
                    'userId': row.get('userId', row.get('user_id', 0)),
                    'restId': row.get('restId', row.get('restaurantId', row.get('restaurant_id', 0))),
                    'rating': row.get('rating', 0),
                    'rating_env': row.get('rating_env', 0),
                    'rating_flavor': row.get('rating_flavor', 0),
                    'rating_service': row.get('rating_service', 0),
                    'timestamp': row.get('timestamp', 0),
                    'comment': comment,
                    'matched_keyword': matched_kw,
                    'matched_spots': ','.join(related_spots[:3])
                })
                total_matched += 1
                match_stats[matched_kw] += 1

        # 显示进度
        elapsed = time.time() - start_time
        speed = total_processed / elapsed if elapsed > 0 else 0
        print(f"  已处理 {total_processed:,} 条 | 大类匹配 {broad_matched:,} | "
              f"城市过滤 {city_filtered:,} | 排除城市 {exclude_filtered:,} | "
              f"精确匹配 {total_matched:,} | 速度 {speed:,.0f} 条/秒", end='\r')

    print(f"\n\n筛选完成!")
    print(f"  原始数据: {total_processed:,} 条")
    print(f"  大类过滤后: {broad_matched:,} 条 ({broad_matched / total_processed * 100:.2f}%)")
    print(f"  城市过滤排除: {city_filtered:,} 条 ({city_filtered / total_processed * 100:.2f}%)")
    print(f"  明确排除城市: {exclude_filtered:,} 条 ({exclude_filtered / total_processed * 100:.2f}%)")
    print(f"  精确匹配: {total_matched:,} 条 ({total_matched / total_processed * 100:.2f}%)")

    # Top匹配关键词
    print(f"\nTop 20 匹配关键词:")
    top_keywords = sorted(match_stats.items(), key=lambda x: x[1], reverse=True)[:20]
    for kw, count in top_keywords:
        print(f"  '{kw}': {count} 条")

    return matched_comments


def save_cleaned_data(matched_comments):
    """保存清洗后的数据"""
    if not matched_comments:
        print("\n未找到匹配的评论")
        return None

    ensure_dir(CLEANED_DATA_DIR)

    df = pd.DataFrame(matched_comments)
    df.to_csv(CLEANED_RATINGS_FILE, index=False, encoding='utf-8-sig')

    print(f"\n清洗后的数据已保存!")
    print(f"  路径: {CLEANED_RATINGS_FILE}")
    print(f"  大小: {os.path.getsize(CLEANED_RATINGS_FILE) / 1024:.1f} KB")
    print(f"  记录数: {len(df):,} 条")

    print(f"\n评分分布:")
    print(df['rating'].value_counts().sort_index())

    return df


if __name__ == "__main__":
    print("=" * 70)
    print("联合筛选（修复版v3）：高德景点 + 大众点评评论 + 粤港澳城市过滤")
    print("=" * 70)

    # 1. 获取景点列表
    print("\n【第一步】获取高德地图景点列表")
    print("-" * 70)
    spot_list = load_gba_spots()

    if not spot_list:
        print("无法获取景点列表")
        exit(1)

    # 2. 提取核心关键词
    print("\n【第二步】提取核心关键词")
    print("-" * 70)
    keyword_map = extract_core_keywords(spot_list)

    # 3. 快速筛选
    print("\n【第三步】快速筛选评论（含城市过滤）")
    print("-" * 70)
    matched_comments = fast_filter_comments(RAW_RATINGS_FILE, keyword_map)

    # 4. 保存
    print("\n【第四步】保存清洗后的数据")
    print("-" * 70)
    df_cleaned = save_cleaned_data(matched_comments)

    if df_cleaned is not None:
        print("\n" + "=" * 70)
        print("清洗完成！")
        print("=" * 70)
        print(f"\n输出文件: {CLEANED_RATINGS_FILE}")