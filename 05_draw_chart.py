# 05_draw_chart.py - SQLAlchemy规范版
from sqlalchemy import create_engine
import pandas as pd
import matplotlib.pyplot as plt

# 配置
SERVER_NAME = "DESKTOP-MQV3VAF"
DATABASE_NAME = "tourism_gba"


# SQLAlchemy连接字符串（Windows身份验证）
def get_engine():
    conn_str = f"mssql+pyodbc://{SERVER_NAME}/{DATABASE_NAME}?trusted_connection=yes&driver=SQL+Server"
    return create_engine(conn_str)


# 绘制热度趋势图
def draw_hot_trend(spot_id=1):
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False

    engine = get_engine()

    # 1. 查询热度数据（无警告）
    df = pd.read_sql(f"""
        SELECT date, hot_val FROM hot_data
        WHERE spot_id={spot_id} ORDER BY date
    """, engine)

    if df.empty:
        print("× 暂无热度数据，请先运行 04_generate_data.py！")
        return

    # 2. 查询景点名称（无警告）
    name = pd.read_sql(f"SELECT name FROM scenic_spot WHERE spot_id={spot_id}", engine).iloc[0, 0]

    # 绘图
    df["date"] = pd.to_datetime(df["date"])
    plt.figure(figsize=(12, 5))
    plt.plot(df["date"], df["hot_val"], label="历史热度", color="#2f86eb", linewidth=2)
    plt.title(f"[{name}] 近90天热度变化", fontsize=14)
    plt.xlabel("日期")
    plt.ylabel("热度指数")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()
    print(" 热度趋势图已弹出！")


if __name__ == "__main__":
    draw_hot_trend(spot_id=1)