# 05_3_hot_trend.py - 修复版：SQL Server日期运算
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import create_engine
import urllib
import matplotlib.dates as mdates

plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

SERVER_NAME = "DESKTOP-MQV3VAF"
DATABASE_NAME = "tourism_gba"


def get_engine():
    params = urllib.parse.quote_plus(
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE={DATABASE_NAME};"
        f"Trusted_Connection=yes;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


def get_hot_trend_data():
    """读取最近14天的真实热度数据"""
    try:
        engine = get_engine()

        # 先查数据库最新日期
        df_max = pd.read_sql("SELECT MAX(date) as max_date FROM hot_data", engine)
        max_date = df_max['max_date'].iloc[0]
        print(f"数据库最新日期: {max_date}")

        # 查询最近14天有数据的TOP5景点
        # 修复：用 DATEADD(day, -13, MAX(date)) 而不是 MAX(date) - 13
        sql = f"""
            SELECT TOP 5 
                s.spot_id,
                s.name,
                AVG(h.hot_val) as avg_hot
            FROM scenic_spot s
            INNER JOIN hot_data h ON s.spot_id = h.spot_id
            WHERE h.date >= DATEADD(day, -13, '{max_date}')
            GROUP BY s.spot_id, s.name
            ORDER BY avg_hot DESC
        """

        spots = pd.read_sql(sql, engine)

        if spots.empty:
            print("❌ 无热度数据！")
            return None

        print(f"✅ TOP5热门景点（最近14天）：")
        for _, row in spots.iterrows():
            print(f"  {row['name']}: 平均热度 {row['avg_hot']:.1f}")

        # 取这5个景点最近14天明细
        spot_ids = ",".join([str(int(sid)) for sid in spots['spot_id']])

        sql = f"""
            SELECT 
                h.spot_id,
                s.name,
                h.date,
                h.hot_val
            FROM hot_data h
            INNER JOIN scenic_spot s ON h.spot_id = s.spot_id
            WHERE h.spot_id IN ({spot_ids})
              AND h.date >= DATEADD(day, -13, '{max_date}')
            ORDER BY h.spot_id, h.date
        """

        df = pd.read_sql(sql, engine)
        df['date'] = pd.to_datetime(df['date'])

        # 验证天数
        for name, group in df.groupby('name'):
            days = len(group)
            print(f"  {name[:10]}: {days}天数据")

        return df

    except Exception as e:
        print(f"❌ 读取失败：{e}")
        return None


def generate_hot_trend_chart():
    df = get_hot_trend_data()
    if df is None:
        return

    plt.figure(figsize=(12, 6))
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6']

    for i, (name, group) in enumerate(df.groupby("name")):
        color = colors[i % len(colors)]
        plt.plot(group["date"], group["hot_val"],
                 marker="o", linewidth=2, label=name, color=color, markersize=5)

    plt.xlabel("日期", fontsize=12)
    plt.ylabel("热度值（0-100）", fontsize=12)
    plt.title("粤港澳大湾区热门景点14天热度趋势", fontsize=14, fontweight="bold")
    plt.legend(loc="upper right", fontsize=9)
    plt.grid(alpha=0.3)
    plt.xticks(rotation=30)

    # X轴格式：月-日，每2天一个刻度
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=2))

    plt.tight_layout()
    plt.savefig("粤港澳景点热度趋势图_14天.png", dpi=300, bbox_inches="tight")
    print("\n✅ 已保存：粤港澳景点热度趋势图_14天.png")

    # 统计
    print(f"\n📊 14天趋势统计：")
    for name, group in df.groupby("name"):
        print(f"  {name[:8]:<8} | 均值{group['hot_val'].mean():.1f} | "
              f"最大{group['hot_val'].max():.1f} | 最小{group['hot_val'].min():.1f}")


if __name__ == "__main__":
    generate_hot_trend_chart()