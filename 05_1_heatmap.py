# 05_1_heatmap.py - 修复底图空白问题（高德地图）
import pandas as pd
import folium
from folium.plugins import HeatMap
from sqlalchemy import create_engine
import urllib

# 数据库配置（和你的SSMS完全一致）
SERVER_NAME = "DESKTOP-MQV3VAF"
DATABASE_NAME = "tourism_gba"


def get_spot_coords():
    """用SQLAlchemy连接数据库，读取真实景点数据"""
    try:
        # 构建ODBC连接字符串（适配SQLAlchemy）
        params = urllib.parse.quote_plus(
            f"DRIVER={{SQL Server}};"
            f"SERVER={SERVER_NAME};"
            f"DATABASE={DATABASE_NAME};"
            f"Trusted_Connection=yes;"
        )
        # 创建SQLAlchemy引擎（消除pandas警告）
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

        # 查询所有景点数据
        sql = "SELECT spot_id, name, address, lat, lng, price FROM scenic_spot"
        df = pd.read_sql(sql, engine)

        # 数据清洗（仅保留有效数据）
        print(f" 数据库中共读取到 {len(df)} 条景点数据")
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

        # 过滤无效数据（lat/lng≠0、非空）
        valid_df = df[
            (df["lat"] != 0) &
            (df["lng"] != 0) &
            (df["lat"].notna()) &
            (df["lng"].notna()) &
            (df["price"].notna())
            ].copy()

        if len(valid_df) > 0:
            # 计算热度权重（归一化到0-10）
            valid_df["weight"] = (valid_df["price"] / valid_df["price"].max()) * 10
            print(f" 筛选出 {len(valid_df)} 条有效景点数据")
        else:
            print(" 无有效经纬度数据！请检查scenic_spot表的lat/lng字段")

        return valid_df

    except Exception as e:
        print(f" 数据库连接/查询失败：{e}")
        return pd.DataFrame()


def generate_heatmap():
    """生成热力图（修复底图空白+无警告）"""
    df = get_spot_coords()
    if df.empty:
        print(" 无有效数据，终止生成热力图")
        return

    # 基于真实数据的中心点（更精准）
    avg_lat = df["lat"].mean()
    avg_lng = df["lng"].mean()

    # 核心修改：替换为国内高德地图底图（解决空白问题）
    m = folium.Map(
        location=[avg_lat, avg_lng],
        zoom_start=10,
        # 替换OpenStreetMap为高德地图瓦片
        tiles='http://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        attr='高德地图'  # 标注底图来源
    )

    # 热力数据（删除废弃的max_val参数）
    heat_data = [[row["lat"], row["lng"], row["weight"]] for _, row in df.iterrows()]
    HeatMap(
        heat_data,
        min_opacity=0.3,
        radius=15,
        blur=10,
        gradient={0.2: 'blue', 0.4: 'cyan', 0.6: 'yellow', 0.8: 'orange', 1.0: 'red'}
    ).add_to(m)

    # 给所有有效景点添加标记（点击可看详情）
    for _, row in df.iterrows():
        folium.Marker(
            location=[row["lat"], row["lng"]],
            popup=f"""
                <b>景点名称：{row['name']}</b><br>
                地址：{row['address'][:20]}...<br>
                热度值：{row['weight']:.1f}
            """,
            icon=folium.Icon(color="darkred", icon="map-marker")
        ).add_to(m)

    # 保存热力图文件
    m.save("粤港澳景点热力图.html")
    print(" 热力图已生成：粤港澳景点热力图.html")


if __name__ == "__main__":
    generate_heatmap()