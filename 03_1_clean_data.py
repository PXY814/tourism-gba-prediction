# 03_1_clean_data.py - 最终修复版（兼容list类型+修正粤港澳城市）
import ast
import re

def load_raw_spots():
    """加载原始爬取数据"""
    try:
        with open("crawled_spots.txt", "r", encoding="utf-8") as f:
            raw_data = ast.literal_eval(f.read())
        print(f"加载原始数据：{len(raw_data)} 条")
        return raw_data
    except Exception as e:
        print(f"加载原始数据失败：{e}")
        return []

def safe_str(value):
    """安全转换为字符串（兼容list/None/其他类型）"""
    if isinstance(value, list):
        # 列表转字符串（取第一个元素，或拼接）
        return "".join([str(x).strip() for x in value]) if value else ""
    elif value is None:
        return ""
    else:
        return str(value).strip()

def clean_spots_data(raw_data):
    """核心清洗逻辑：兼容list类型+修正粤港澳城市+去重+过滤"""
    cleaned_data = []
    spot_unique = set()  # 去重集合（名称+城市）

    # 修正：粤港澳大湾区11城完整列表（包含特殊名称）
    gba_cities = [
        "广州市", "深圳市", "珠海市", "佛山市", "惠州市",
        "东莞市", "中山市", "江门市", "肇庆市",
        "香港", "香港特别行政区", "澳门", "澳门特别行政区"
    ]

    for idx, spot in enumerate(raw_data):
        try:
            # 1. 安全提取字段（兼容list/None）
            name = safe_str(spot.get("name")) or "未知景点"
            cityname = safe_str(spot.get("cityname")) or "未知城市"
            address = safe_str(spot.get("address")) or "地址未填写"
            location = safe_str(spot.get("location")) or "0,0"
            type_ = safe_str(spot.get("type")) or "未知类型"
            tel = safe_str(spot.get("tel")) or "无联系电话"
            biz_ext = spot.get("biz_ext", {}) or {}
            id_ = safe_str(spot.get("id")) or f"id_{idx}"

            # 2. 去重：名称+城市相同视为重复
            unique_key = f"{name}_{cityname}"
            if unique_key in spot_unique:
                continue
            spot_unique.add(unique_key)

            # 3. 过滤：只保留粤港澳景点（修正城市匹配）
            city_match = any(gba_city in cityname for gba_city in gba_cities)
            if not city_match:
                print(f"过滤非粤港澳景点：{name}（{cityname}）")
                continue

            # 过滤：名称过短（至少2个字符）
            if len(name) < 2:
                print(f"过滤无效名称景点：{name}")
                continue

            # 4. 经纬度格式化（容错）
            lng, lat = "0", "0"
            if "," in location:
                lng, lat = location.split(",", 1)  # 只分割一次，避免异常
            try:
                lng = round(float(safe_str(lng)), 6)
                lat = round(float(safe_str(lat)), 6)
                if lng == 0 and lat == 0:
                    print(f"过滤无效经纬度景点：{name}")
                    continue
                location = f"{lng},{lat}"
            except:
                print(f"经纬度解析失败：{name} | 原始值：{location}")
                continue

            # 5. 其他格式标准化
            tel = re.sub(r"[^0-9;-]", "", tel)  # 电话只保留数字和分隔符
            if ";" in type_:
                type_ = type_.split(";")[0]  # 类型简化
            level = safe_str(biz_ext.get("level")) or "无等级"

            # 6. 过滤重复经纬度
            loc_key = location
            if loc_key in [x["location"] for x in cleaned_data]:
                continue

            # 7. 组装清洗后的数据
            cleaned_spot = {
                "name": name,
                "cityname": cityname,
                "address": address,
                "location": location,
                "type": type_,
                "tel": tel,
                "level": level,
                "id": id_
            }
            cleaned_data.append(cleaned_spot)

        except Exception as e:
            print(f"第{idx}条数据清洗失败：{e} | 原始数据片段：{str(spot)[:50]}")
            continue

    # 按城市+名称排序
    cleaned_data.sort(key=lambda x: (x["cityname"], x["name"]))
    print(f"\n数据清洗完成：原始{len(raw_data)}条 → 清洗后{len(cleaned_data)}条")
    return cleaned_data

def save_cleaned_spots(cleaned_data):
    """保存清洗后的数据"""
    with open("cleaned_spots.txt", "w", encoding="utf-8") as f:
        f.write(str(cleaned_data))
    print(f"清洗后的数据已保存到 cleaned_spots.txt")

if __name__ == "__main__":
    raw_data = load_raw_spots()
    if raw_data:
        cleaned_data = clean_spots_data(raw_data)
        save_cleaned_spots(cleaned_data)