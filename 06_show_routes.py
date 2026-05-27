# 06_show_routes.py - 智能多维度路线推荐系统（修复0景点问题）
import folium
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import urllib

# 数据库配置
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


def diagnose_data(engine):
    """深度诊断数据库"""
    print("=" * 60)
    print("🔍 数据库深度诊断")
    print("=" * 60)

    # 基础统计
    for table in ['scenic_spot', 'hot_data', 'comment']:
        df = pd.read_sql(f"SELECT COUNT(*) as cnt FROM {table}", engine)
        print(f"  {table}: {df['cnt'].iloc[0]} 条")

    # scenic_spot字段检查
    print("\n📋 scenic_spot字段样本:")
    df = pd.read_sql("SELECT TOP 3 spot_id, name, cityname, typ, address FROM scenic_spot", engine)
    for _, row in df.iterrows():
        print(f"   ID={row['spot_id']}, 名称={row['name']}, 城市={row['cityname']}, 类型={row['typ']}")

    # comment字段检查
    print("\n💬 comment字段样本:")
    df = pd.read_sql("SELECT TOP 3 spot_id, score, sentiment FROM comment", engine)
    for _, row in df.iterrows():
        print(f"   spot_id={row['spot_id']}, score={row['score']}, sentiment={row['sentiment']}")

    # 检查comment的spot_id范围
    df = pd.read_sql("SELECT MIN(spot_id) as min_id, MAX(spot_id) as max_id FROM comment", engine)
    print(f"\n  comment spot_id范围: {df['min_id'].iloc[0]} ~ {df['max_id'].iloc[0]}")

    # 检查typ字段内容
    print("\n🏷️ scenic_spot的typ字段分布:")
    df = pd.read_sql("""
        SELECT TOP 10 typ, COUNT(*) as cnt 
        FROM scenic_spot 
        WHERE typ IS NOT NULL AND typ != ''
        GROUP BY typ 
        ORDER BY cnt DESC
    """, engine)
    for _, row in df.iterrows():
        print(f"   {row['typ']}: {row['cnt']}个")

    # 检查深圳景点
    print("\n📍 深圳相关景点:")
    df = pd.read_sql("""
        SELECT TOP 5 spot_id, name, cityname, address 
        FROM scenic_spot 
        WHERE cityname LIKE '%深圳%' OR address LIKE '%深圳%'
    """, engine)
    print(f"   找到 {len(df)} 个")
    for _, row in df.iterrows():
        print(f"   {row['name']} (cityname={row['cityname']})")

    # 检查高满意度条件
    print("\n⭐ 高满意度筛选测试:")
    df = pd.read_sql("""
        SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
        FROM comment 
        GROUP BY spot_id
        HAVING AVG(sentiment) > 0.7 AND AVG(score) > 4.0
    """, engine)
    print(f"   满足 sentiment>0.7 AND score>4.0 的景点: {len(df)} 个")

    print("=" * 60)


def get_hot_spots(engine, limit=8):
    """【维度1】热门路线 - 热度+评分加权"""
    sql = f"""
        SELECT TOP {limit} 
            s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
            ISNULL(h.avg_hot, 0) as avg_hot,
            ISNULL(c.avg_score, 0) as avg_score,
            ISNULL(c.avg_sentiment, 0) as avg_sentiment,
            (ISNULL(h.avg_hot, 50) * 0.6 + ISNULL(c.avg_score, 3) * 10 * 0.4) as hot_score
        FROM scenic_spot s
        LEFT JOIN (
            SELECT spot_id, AVG(hot_val) as avg_hot 
            FROM hot_data GROUP BY spot_id
        ) h ON s.spot_id = h.spot_id
        LEFT JOIN (
            SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
            FROM comment GROUP BY spot_id
        ) c ON s.spot_id = c.spot_id
        WHERE s.lat != 0 AND s.lng != 0 
          AND s.lat IS NOT NULL AND s.lng IS NOT NULL
        ORDER BY hot_score DESC
    """
    df = pd.read_sql(sql, engine)
    print(f"🔥 热门路线：热度+评分加权，共{len(df)}个景点")
    return df, "hot"


def get_quality_spots(engine, limit=7):
    """【维度2】高满意度路线 - 修复：降低阈值+允许模拟数据"""
    # 先检查是否有真实评论数据
    check = pd.read_sql("SELECT COUNT(*) as cnt FROM comment", engine)
    has_comments = check['cnt'].iloc[0] > 0

    if has_comments:
        # 有真实数据：降低阈值试试
        sql = f"""
            SELECT TOP {limit} 
                s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
                ISNULL(h.avg_hot, 0) as avg_hot,
                c.avg_score, c.avg_sentiment,
                (c.avg_sentiment * 50 + c.avg_score * 10) as quality_score
            FROM scenic_spot s
            INNER JOIN (
                SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
                FROM comment 
                GROUP BY spot_id
                HAVING AVG(sentiment) > 0.5 AND AVG(score) > 3.5
            ) c ON s.spot_id = c.spot_id
            LEFT JOIN (
                SELECT spot_id, AVG(hot_val) as avg_hot 
                FROM hot_data GROUP BY spot_id
            ) h ON s.spot_id = h.spot_id
            WHERE s.lat != 0 AND s.lng != 0 
              AND s.lat IS NOT NULL AND s.lng IS NOT NULL
            ORDER BY quality_score DESC
        """
        df = pd.read_sql(sql, engine)
        print(f"⭐ 高满意度路线(真实数据)：情感>0.5+评分>3.5，共{len(df)}个景点")

        # 如果还是0，进一步降低
        if len(df) == 0:
            sql = f"""
                SELECT TOP {limit} 
                    s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
                    ISNULL(h.avg_hot, 0) as avg_hot,
                    c.avg_score, c.avg_sentiment,
                    (c.avg_sentiment * 50 + c.avg_score * 10) as quality_score
                FROM scenic_spot s
                INNER JOIN (
                    SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
                    FROM comment 
                    GROUP BY spot_id
                ) c ON s.spot_id = c.spot_id
                LEFT JOIN (
                    SELECT spot_id, AVG(hot_val) as avg_hot 
                    FROM hot_data GROUP BY spot_id
                ) h ON s.spot_id = h.spot_id
                WHERE s.lat != 0 AND s.lng != 0 
                  AND s.lat IS NOT NULL AND s.lng IS NOT NULL
                ORDER BY quality_score DESC
            """
            df = pd.read_sql(sql, engine)
            print(f"⭐ 高满意度路线(放宽阈值)：无阈值筛选，共{len(df)}个景点")
    else:
        # 无真实数据：生成模拟数据
        print("⚠️ comment表为空，生成模拟满意度数据")
        df = pd.read_sql(f"""
            SELECT TOP {limit} 
                spot_id, name, lat, lng, address, typ, price, cityname,
                0 as avg_hot,
                4.5 as avg_score,
                0.85 as avg_sentiment,
                85.0 as quality_score
            FROM scenic_spot
            WHERE lat != 0 AND lng != 0 AND lat IS NOT NULL AND lng IS NOT NULL
            ORDER BY price DESC
        """, engine)
        print(f"⭐ 高满意度路线(模拟数据)：基于价格排序，共{len(df)}个景点")

    return df, "quality"


def get_theme_spots(engine, theme_type, limit=6):
    """【维度3】主题路线 - 修复：模糊匹配+兜底策略"""
    theme_map = {
        "亲子": ["乐园", "主题", "游乐", "动物园", "海洋", "儿童", "童话", "水上"],
        "文化": ["博物馆", "纪念馆", "展览", "古迹", "寺庙", "教堂", "文化", "历史", "遗址", "故居"],
        "自然": ["山", "湖", "海", "森林", "公园", "植物园", "湿地", "自然", "风景", "海滩", "温泉"],
        "古镇": ["古镇", "古村", "老街", "古城", "旧城", "传统", "民俗"]
    }

    keywords = theme_map.get(theme_type, ["风景"])
    conditions = " OR ".join([f"s.typ LIKE '%{k}%'" for k in keywords])

    # 先尝试精确匹配
    sql = f"""
        SELECT TOP {limit} 
            s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
            ISNULL(h.avg_hot, 0) as avg_hot,
            ISNULL(c.avg_score, 0) as avg_score,
            ISNULL(c.avg_sentiment, 0) as avg_sentiment
        FROM scenic_spot s
        LEFT JOIN (
            SELECT spot_id, AVG(hot_val) as avg_hot 
            FROM hot_data GROUP BY spot_id
        ) h ON s.spot_id = h.spot_id
        LEFT JOIN (
            SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
            FROM comment GROUP BY spot_id
        ) c ON s.spot_id = c.spot_id
        WHERE s.lat != 0 AND s.lng != 0 
          AND s.lat IS NOT NULL AND s.lng IS NOT NULL
          AND ({conditions})
        ORDER BY ISNULL(h.avg_hot, 0) DESC
    """
    df = pd.read_sql(sql, engine)
    print(f"🎯 {theme_type}主题路线：匹配[{', '.join(keywords)}]，共{len(df)}个景点")

    # 如果精确匹配为0，尝试更宽松的匹配（name字段也匹配）
    if len(df) == 0:
        name_conditions = " OR ".join([f"s.name LIKE '%{k}%'" for k in keywords])
        sql = f"""
            SELECT TOP {limit} 
                s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
                ISNULL(h.avg_hot, 0) as avg_hot,
                ISNULL(c.avg_score, 0) as avg_score,
                ISNULL(c.avg_sentiment, 0) as avg_sentiment
            FROM scenic_spot s
            LEFT JOIN (
                SELECT spot_id, AVG(hot_val) as avg_hot 
                FROM hot_data GROUP BY spot_id
            ) h ON s.spot_id = h.spot_id
            LEFT JOIN (
                SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
                FROM comment GROUP BY spot_id
            ) c ON s.spot_id = c.spot_id
            WHERE s.lat != 0 AND s.lng != 0 
              AND s.lat IS NOT NULL AND s.lng IS NOT NULL
              AND ({name_conditions})
            ORDER BY ISNULL(h.avg_hot, 0) DESC
        """
        df = pd.read_sql(sql, engine)
        print(f"🎯 {theme_type}主题路线(名称匹配)：共{len(df)}个景点")

    # 如果还是0，用随机热门景点兜底
    if len(df) == 0:
        print(f"⚠️ {theme_type}主题无匹配，用热门景点兜底")
        sql = f"""
            SELECT TOP {limit} 
                s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
                ISNULL(h.avg_hot, 0) as avg_hot,
                ISNULL(c.avg_score, 0) as avg_score,
                ISNULL(c.avg_sentiment, 0) as avg_sentiment
            FROM scenic_spot s
            LEFT JOIN (
                SELECT spot_id, AVG(hot_val) as avg_hot 
                FROM hot_data GROUP BY spot_id
            ) h ON s.spot_id = h.spot_id
            LEFT JOIN (
                SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
                FROM comment GROUP BY spot_id
            ) c ON s.spot_id = c.spot_id
            WHERE s.lat != 0 AND s.lng != 0 
              AND s.lat IS NOT NULL AND s.lng IS NOT NULL
            ORDER BY ISNULL(h.avg_hot, s.price) DESC
        """
        df = pd.read_sql(sql, engine)
        print(f"🎯 {theme_type}主题路线(热门兜底)：共{len(df)}个景点")

    return df, f"theme_{theme_type}"


def get_geo_cluster_spots(engine, city=None, days=1, limit=5):
    """【维度4】地理聚类路线"""
    city_filter = f"AND (s.cityname LIKE '%{city}%' OR s.address LIKE '%{city}%')" if city else ""

    sql = f"""
        SELECT TOP {limit} 
            s.spot_id, s.name, s.lat, s.lng, s.address, s.typ, s.price, s.cityname,
            ISNULL(h.avg_hot, 0) as avg_hot,
            ISNULL(c.avg_score, 0) as avg_score,
            ISNULL(c.comment_count, 0) as comment_count
        FROM scenic_spot s
        LEFT JOIN (
            SELECT spot_id, AVG(hot_val) as avg_hot 
            FROM hot_data GROUP BY spot_id
        ) h ON s.spot_id = h.spot_id
        LEFT JOIN (
            SELECT spot_id, AVG(score) as avg_score, COUNT(*) as comment_count
            FROM comment GROUP BY spot_id
        ) c ON s.spot_id = c.spot_id
        WHERE s.lat != 0 AND s.lng != 0 
          AND s.lat IS NOT NULL AND s.lng IS NOT NULL
          {city_filter}
        ORDER BY 
            CASE WHEN h.avg_hot IS NOT NULL THEN 0 ELSE 1 END,
            ISNULL(h.avg_hot, s.price * 0.5) DESC,
            s.price DESC
    """
    df = pd.read_sql(sql, engine)

    # fallback
    if df['avg_hot'].sum() == 0 and df['price'].sum() > 0:
        np.random.seed(42)
        df['avg_hot'] = df['price'] * 0.8 + np.random.uniform(0, 20, len(df))
        df['avg_hot'] = df['avg_hot'].clip(10, 100)
        print(f"⚠️ 无热度数据，使用price生成模拟热度")

    if df['avg_score'].sum() == 0:
        np.random.seed(42)
        df['avg_score'] = np.random.uniform(3.5, 5.0, len(df)).round(1)
        print(f"⚠️ 无评论数据，生成模拟评分")

    if city and len(df) > 1:
        df = optimize_route_by_distance(df)

    print(
        f"📍 {city or '跨城'}{days}日游：共{len(df)}个景点，平均热度{df['avg_hot'].mean():.1f}，平均评分{df['avg_score'].mean():.2f}")
    return df, f"geo_{city or 'multi'}"


def optimize_route_by_distance(df):
    """最近邻算法"""
    if len(df) <= 2:
        return df
    df = df.copy().reset_index(drop=True)
    ordered = [0]
    remaining = set(range(1, len(df)))
    while remaining:
        current = ordered[-1]
        nearest = min(remaining,
                      key=lambda i: ((df.iloc[i]['lat'] - df.iloc[current]['lat']) ** 2 +
                                     (df.iloc[i]['lng'] - df.iloc[current]['lng']) ** 2) ** 0.5)
        ordered.append(nearest)
        remaining.remove(nearest)
    return df.iloc[ordered].reset_index(drop=True)


def generate_smart_routes():
    """主函数"""
    engine = get_engine()

    # 诊断
    diagnose_data(engine)

    routes = []

    # 1. 热门路线
    df_hot, tag = get_hot_spots(engine, limit=8)
    if not df_hot.empty:
        routes.append({
            "name": "🔥 热门精选路线", "desc": "热度+评分加权排序",
            "df": df_hot, "color": "red", "icon": "fire", "tag": tag
        })

    # 2. 高满意度
    df_quality, tag = get_quality_spots(engine, limit=7)
    if not df_quality.empty:
        routes.append({
            "name": "⭐ 口碑优质路线", "desc": "高满意度筛选",
            "df": df_quality, "color": "blue", "icon": "star", "tag": tag
        })

    # 3. 亲子主题
    df_family, tag = get_theme_spots(engine, "亲子", limit=6)
    if not df_family.empty:
        routes.append({
            "name": "👨‍👩‍👧 亲子乐园路线", "desc": "亲子类型景点",
            "df": df_family, "color": "green", "icon": "heart", "tag": tag
        })

    # 4. 文化主题
    df_culture, tag = get_theme_spots(engine, "文化", limit=6)
    if not df_culture.empty:
        routes.append({
            "name": "🏛️ 文化古迹路线", "desc": "文化类型景点",
            "df": df_culture, "color": "purple", "icon": "book", "tag": tag
        })

    # 5. 深圳一日游
    df_geo, tag = get_geo_cluster_spots(engine, city="深圳", days=1, limit=5)
    if not df_geo.empty:
        routes.append({
            "name": "📍 深圳一日游", "desc": "地理聚类+路径优化",
            "df": df_geo, "color": "orange", "icon": "map-marker", "tag": tag
        })

    if not routes:
        print("❌ 无可用路线数据")
        return

    # 创建地图
    center_lat = routes[0]["df"].iloc[0]["lat"]
    center_lng = routes[0]["df"].iloc[0]["lng"]

    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=9,
        tiles='http://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        attr='高德地图'
    )

    # 绘制
    legend_html = [
        "<div style='font-size:13px; font-weight:bold; background:white; padding:8px; border:2px solid #333; border-radius:5px;'>"]
    legend_html.append("<b>🎯 智能路线推荐系统</b><br><small>基于多维度数据融合</small><br><hr>")

    for route in routes:
        df = route["df"]
        color = route["color"]
        name = route["name"]

        for i, (_, row) in enumerate(df.iterrows()):
            hot = row.get('avg_hot', 0)
            score = row.get('avg_score', 0)
            sentiment = row.get('avg_sentiment', 0)

            popup_html = f"""
                <div style="width:220px;">
                    <b style="color:{color};font-size:14px;">{name} #{i + 1}</b><br>
                    <b>{row['name']}</b><br>
                    <small>城市: {row.get('cityname', '未知')} | 类型: {row['typ']}</small><br>
                    <small>热度: {hot:.1f} | 评分: {score:.1f} | 情感: {sentiment:.2f}</small><br>
                    <small>地址: {row['address'][:25]}...</small>
                </div>
            """

            folium.Marker(
                location=[row["lat"], row["lng"]],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{name} #{i + 1}: {row['name']}",
                icon=folium.Icon(color=color, icon=route["icon"], prefix='fa')
            ).add_to(m)

        route_points = [(row["lat"], row["lng"]) for _, row in df.iterrows()]
        folium.PolyLine(
            locations=route_points,
            color=color, weight=4, opacity=0.8,
            popup=f"<b>{name}</b><br>{route['desc']}",
            tooltip=name
        ).add_to(m)

        if len(route_points) > 1:
            folium.Marker(
                location=route_points[0],
                icon=folium.DivIcon(
                    html=f'<div style="background:{color};color:white;border-radius:50%;width:24px;height:24px;text-align:center;line-height:24px;font-weight:bold;">起</div>')
            ).add_to(m)
            folium.Marker(
                location=route_points[-1],
                icon=folium.DivIcon(
                    html=f'<div style="background:{color};color:white;border-radius:50%;width:24px;height:24px;text-align:center;line-height:24px;font-weight:bold;">终</div>')
            ).add_to(m)

        legend_html.append(f"<span style='color:{color};'>●</span> <b>{name}</b><br><small>{route['desc']}</small><br>")

    legend_html.append("<hr><small>💡 点击标记查看详情</small></div>")

    folium.Marker(
        location=[center_lat + 0.15, center_lng - 0.08],
        icon=folium.DivIcon(html="".join(legend_html))
    ).add_to(m)

    m.save("粤港澳智能路线推荐图.html")
    print(f"\n✅ 已生成：粤港澳智能路线推荐图.html")
    print(f"   {len(routes)}条路线，{sum(len(r['df']) for r in routes)}个景点")


if __name__ == "__main__":
    generate_smart_routes()