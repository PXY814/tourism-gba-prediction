# 02_crawl_spots_enhanced.py - 增强版高德API调用（获取真实POI详情+周边数据）
import requests
import time
import json

# 高德Key（你的Key）
GAODE_KEY = "YOUR_GAODE_KEY_HERE"  # 请替换为你的高德Key

# 粤港澳城市列表（含adcode，用于精确查询）
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

crawled_spots = []
crawled_details = []  # 存储详细POI信息

def crawl_gba_spots():
    """爬取景点基础列表"""
    global crawled_spots
    url = "https://restapi.amap.com/v3/place/text"
    print("正在爬取：粤港澳大湾区旅游景点\n")

    for city in GBA_CITIES:
        city_name = city["name"]
        adcode = city["adcode"]
        print(f"正在获取 → {city_name} (adcode: {adcode})")

        # 分页获取，每页25条，获取2页（50条/城市）
        for page in range(1, 3):
            params = {
                "key": GAODE_KEY,
                "keywords": "旅游景点",
                "types": "风景名胜|景点公园|文化古迹|自然公园|博物馆|主题公园",
                "city": adcode,  # 使用adcode更精确
                "offset": 25,
                "page": page,
                "output": "json",
                "extensions": "all"  # 获取详细信息
            }
            try:
                res = requests.get(url, params=params, timeout=15)
                data = res.json()
                if data.get("pois"):
                    crawled_spots.extend(data["pois"])
                    print(f"  第{page}页: 获取 {len(data['pois'])} 条")
                else:
                    print(f"  第{page}页: 无数据")
                time.sleep(0.5)  # 控制频率，避免限流
            except Exception as e:
                print(f"{city_name} 第{page}页获取失败：{e}")

    print(f"\n 爬取完成，共获取景点：{len(crawled_spots)} 个")
    return crawled_spots


def get_poi_detail(poi_id):
    """获取POI详细信息（热度、评分、营业时间等）"""
    url = "https://restapi.amap.com/v3/place/detail"
    params = {
        "key": GAODE_KEY,
        "id": poi_id,
        "output": "json"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        if data.get("pois") and len(data["pois"]) > 0:
            return data["pois"][0]
        return None
    except Exception as e:
        print(f"获取详情失败 {poi_id}: {e}")
        return None


def enrich_spot_details():
    """为所有景点获取详细信息"""
    global crawled_details
    print("\n正在获取景点详细信息（热度、评分、营业时间等）...")

    for i, spot in enumerate(crawled_spots[:100]):  # 前100个获取详情
        poi_id = spot.get("id")
        if poi_id:
            detail = get_poi_detail(poi_id)
            if detail:
                crawled_details.append(detail)
            time.sleep(0.3)
        if (i + 1) % 20 == 0:
            print(f"  已处理 {i+1}/{min(len(crawled_spots), 100)} 个景点")

    print(f" 详细信息获取完成：{len(crawled_details)} 个")
    return crawled_details


def get_around_pois(location, radius=3000, types="餐饮|酒店|停车场"):
    """获取景点周边POI（用于分析配套设施）"""
    url = "https://restapi.amap.com/v3/place/around"
    params = {
        "key": GAODE_KEY,
        "location": location,
        "radius": radius,
        "types": types,
        "offset": 10,
        "page": 1,
        "output": "json"
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        return data.get("pois", [])
    except Exception as e:
        print(f"周边查询失败: {e}")
        return []


if __name__ == "__main__":
    # 1. 爬取基础列表
    crawl_gba_spots()

    # 2. 获取详细信息
    enrich_spot_details()

    # 3. 保存数据
    with open("crawled_spots.txt", "w", encoding="utf-8") as f:
        f.write(str(crawled_spots))
    with open("crawled_details.txt", "w", encoding="utf-8") as f:
        f.write(str(crawled_details))

    print("\n 所有数据已保存！")
    print("  - crawled_spots.txt: 景点基础列表")
    print("  - crawled_details.txt: 景点详细信息")