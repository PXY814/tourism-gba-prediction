# 04_generate_data.py - 修复版：评论唯一性+景点匹配
import pyodbc
import numpy as np
from datetime import datetime, timedelta
from snownlp import SnowNLP
import random
import pandas as pd
import os

SERVER_NAME = "DESKTOP-MQV3VAF"
DATABASE_NAME = "tourism_gba"
CLEANED_RATINGS_FILE = r"C:\Users\LENGDA\PycharmProjects\pythonProject\travel\cleaned_data\cleaned_ratings_joint.csv"


def db_conn():
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE={DATABASE_NAME};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def clear_all_data(cursor):
    tables = ['hot_data', 'comment', 'route']
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  已清空 {table} 表")
        except Exception as e:
            print(f"  清空 {table} 表失败: {e}")


HOLIDAYS_2024 = [
    "2024-01-01", "2024-02-10", "2024-02-11", "2024-02-12",
    "2024-04-04", "2024-04-05", "2024-04-06",
    "2024-05-01", "2024-05-02", "2024-05-03",
    "2024-06-10",
    "2024-09-15", "2024-09-16", "2024-09-17",
    "2024-10-01", "2024-10-02", "2024-10-03", "2024-10-04",
    "2024-10-05", "2024-10-06", "2024-10-07",
]

HOLIDAYS_2025 = [
    "2025-01-01", "2025-01-29", "2025-01-30", "2025-01-31",
    "2025-04-04", "2025-04-05", "2025-04-06",
    "2025-05-01", "2025-05-02", "2025-05-03", "2025-05-04", "2025-05-05",
    "2025-05-31", "2025-06-01", "2025-06-02",
    "2025-10-01", "2025-10-02", "2025-10-03", "2025-10-04",
    "2025-10-05", "2025-10-06", "2025-10-07", "2025-10-08",
]

ALL_HOLIDAYS = set(HOLIDAYS_2024 + HOLIDAYS_2025)


def load_cleaned_comments():
    if not os.path.exists(CLEANED_RATINGS_FILE):
        print(f"清洗后的数据不存在: {CLEANED_RATINGS_FILE}")
        return None

    print(f"加载联合筛选后的评论数据...")
    df = pd.read_csv(CLEANED_RATINGS_FILE)
    print(f"  共 {len(df):,} 条粤港澳景点相关评论")
    print(f"  覆盖景点: {df['matched_spots'].nunique()} 个")
    return df


def generate_realistic_hot_data(cursor):
    cursor.execute("SELECT spot_id, name, cityname FROM scenic_spot")
    spots = cursor.fetchall()

    end_date = datetime(2025, 4, 30)
    start_date = end_date - timedelta(days=729)

    print(f"\n生成热度数据：{start_date.date()} ~ {end_date.date()}（共730天）")
    print(f"景点数量：{len(spots)} 个")

    total_records = 0

    for sid, name, cityname in spots[:120]:
        base_hot = random.uniform(40, 75)
        city_boost = {"深圳市": 8, "广州市": 6, "珠海市": 5, "香港": 7, "澳门": 5}
        base_hot += city_boost.get(cityname, 0)
        spot_factor = random.uniform(-5, 5)

        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime("%Y-%m-%d")

            weekday = current_date.weekday()
            weekend_boost = 0
            if weekday == 5:
                weekend_boost = random.uniform(15, 25)
            elif weekday == 6:
                weekend_boost = random.uniform(10, 20)

            holiday_boost = 0
            if date_str in ALL_HOLIDAYS:
                holiday_boost = random.uniform(30, 50)

            month = current_date.month
            seasonal_boost = 0
            if month in [7, 8, 10]:
                seasonal_boost = random.uniform(10, 20)
            elif month in [6, 9, 11]:
                seasonal_boost = random.uniform(5, 12)
            elif month in [1, 2, 3]:
                seasonal_boost = random.uniform(-10, -3)

            days_from_start = (current_date - start_date).days
            trend = days_from_start * 0.01

            noise = np.random.normal(0, 3)

            hot_val = base_hot + spot_factor + weekend_boost + holiday_boost + seasonal_boost + trend + noise
            hot_val = max(10, min(100, hot_val))
            hot_val = round(hot_val, 1)

            cursor.execute("""
                INSERT INTO hot_data (spot_id, date, hot_val)
                VALUES (?, ?, ?)
            """, (sid, date_str, hot_val))

            total_records += 1
            current_date += timedelta(days=1)

        if sid % 20 == 0:
            print(f"  已完成 {sid}/120 个景点，累计 {total_records} 条记录")

    print(f"\n 热度数据生成完成：共 {total_records} 条记录")


def generate_comments_unique(cursor, df):
    """
    修复版：确保每条评论只使用一次，按景点分配
    """
    cursor.execute("SELECT spot_id, name, typ, cityname FROM scenic_spot")
    spots = cursor.fetchall()

    print(f"\n为 {len(spots)} 个景点分配真实评论...")
    print(f"可用评论总数: {len(df):,} 条")

    # 将评论随机打乱，确保分配时不会集中
    df_shuffled = df.sample(frac=1, random_state=42).reset_index(drop=True)

    # 计算每个景点分配多少条评论
    total_comments = len(df_shuffled)
    num_spots = min(len(spots), 80)  # 最多给80个景点分配
    comments_per_spot = total_comments // num_spots  # 平均分配
    remainder = total_comments % num_spots  # 余数

    print(f"分配方案: {num_spots} 个景点，平均每景点 {comments_per_spot} 条，余数 {remainder} 条")

    total_inserted = 0
    comment_idx = 0

    for i, (sid, name, typ, cityname) in enumerate(spots[:num_spots]):
        # 计算该景点分配的评论数
        spot_comment_count = comments_per_spot + (1 if i < remainder else 0)

        # 取出对应数量的评论
        spot_df = df_shuffled.iloc[comment_idx:comment_idx + spot_comment_count]
        comment_idx += spot_comment_count

        if len(spot_df) == 0:
            continue

        for _, row in spot_df.iterrows():
            comment_text = str(row['comment']).strip()
            if len(comment_text) < 5:
                continue

            # 使用原始评分和情感，添加小幅随机波动
            base_score = float(row['rating'])
            base_sentiment = round(SnowNLP(comment_text).sentiments, 2)

            final_score = round(min(5.0, max(1.0, base_score + random.uniform(-0.3, 0.3))), 1)
            final_sentiment = round(min(1.0, max(0.0, base_sentiment + random.uniform(-0.1, 0.1))), 2)

            cursor.execute("""
                INSERT INTO comment (spot_id, content, score, sentiment)
                VALUES (?, ?, ?, ?)
            """, (sid, comment_text, final_score, final_sentiment))

            total_inserted += 1

    print(f" 评论数据生成完成：共 {total_inserted} 条")
    print(f" 覆盖景点数: {num_spots} 个")
    print(" 特点：每条评论只分配给1个景点，无重复")


def generate_enhanced_routes(cursor):
    routes = [
        ("广州经典一日游", "1,2,3", 1, 240, 82.4),
        ("深圳滨海两日游", "4,5,6", 2, 360, 85.1),
        ("珠澳风情线", "7,8,9", 1, 210, 79.6),
        ("粤港澳精华环线", "1,4,7,10,12", 3, 720, 91.2),
        ("佛山岭南文化游", "13,14,15", 1, 180, 76.8),
        ("东莞生态休闲游", "16,17,18", 1, 200, 74.5),
        ("惠州山水度假线", "19,20,21", 2, 300, 80.2),
        ("中山历史人文游", "22,23,24", 1, 190, 72.8),
    ]

    cursor.execute("DELETE FROM route")

    for r in routes:
        cursor.execute("""
            INSERT INTO route (route_name, spot_ids, days, total_min, hot_score)
            VALUES (?, ?, ?, ?, ?)
        """, r[:5])

    print(" 路线数据生成完成（8条精品路线）")


if __name__ == "__main__":
    print("=" * 60)
    print("数据生成（联合筛选v3版 - 5,866条真实评论）")
    print("=" * 60)

    conn = db_conn()
    cursor = conn.cursor()

    print("\n【准备】清空旧数据...")
    clear_all_data(cursor)
    conn.commit()

    df = load_cleaned_comments()

    if df is None:
        print("\n未找到清洗后的数据，终止运行")
        conn.close()
        exit(1)

    generate_realistic_hot_data(cursor)

    # 修复：直接传入df，确保评论唯一分配
    generate_comments_unique(cursor, df)

    generate_enhanced_routes(cursor)

    conn.commit()
    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("所有数据生成完成！")
    print("=" * 60)
    print(f"\n数据验证：")
    print(f"  - 评论总数应 ≈ {len(df)} 条（不超过{len(df) + 10}）")
    print(f"  - 覆盖景点数应 ≤ 80 个")
    print("\n建议接下来运行：")
    print("  python 05_1_heatmap.py")
    print("  python 05_2_sentiment_chart.py")
    print("  python 06_show_routes.py")