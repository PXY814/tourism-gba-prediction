# check_data_quality.py - 检查数据质量问题
import pandas as pd
import os
from collections import Counter

CLEANED_RATINGS_FILE = r"C:\Users\LENGDA\PycharmProjects\pythonProject\travel\cleaned_data\cleaned_ratings_joint.csv"


def check_city_distribution():
    """检查matched_spots的城市分布（是否匹配到非粤港澳城市）"""
    print("=" * 60)
    print("🔍 检查匹配景点的城市分布")
    print("=" * 60)

    df = pd.read_csv(CLEANED_RATINGS_FILE)

    # 提取城市信息（从matched_spots或address推断）
    print(f"\n清洗后总评论数: {len(df):,}")
    print(f"匹配景点数: {df['matched_spots'].nunique()}")

    # 检查matched_spots内容
    print(f"\n📊 Top 20 匹配景点及评论数:")
    top_spots = df['matched_spots'].value_counts().head(20)
    for spot, count in top_spots.items():
        print(f"  {spot}: {count:,}条")

    # 检查是否包含明显非粤港澳的景点
    non_gba_keywords = ['上海', '北京', '杭州', '南京', '成都', '西安', '武汉', '重庆']

    print(f"\n⚠️ 可能非粤港澳的匹配（关键词筛查）:")
    suspicious = []
    for spot in df['matched_spots'].unique():
        for keyword in non_gba_keywords:
            if keyword in str(spot):
                count = df[df['matched_spots'] == spot].shape[0]
                suspicious.append((spot, keyword, count))

    if suspicious:
        for spot, keyword, count in suspicious[:10]:
            print(f"  {spot} (含'{keyword}'): {count}条")
    else:
        print("  未发现明显非粤港澳城市关键词")

    # 检查"中山公园"的分布（这是个全国都有的公园）
    print(f"\n🔍 '中山公园'详细分析:")
    zhongshan = df[df['matched_spots'].str.contains('中山公园', na=False)]
    print(f"  总匹配数: {len(zhongshan):,}")

    # 检查这些评论的原始内容是否包含城市信息
    sample_comments = zhongshan['comment'].head(5).tolist()
    print(f"  样本评论:")
    for i, c in enumerate(sample_comments, 1):
        print(f"    {i}. {c[:60]}...")

    return df


def check_database_duplicates():
    """检查数据库是否有重复数据"""
    print("\n" + "=" * 60)
    print("🔍 检查数据库重复数据")
    print("=" * 60)

    try:
        from sqlalchemy import create_engine
        import urllib.parse

        params = urllib.parse.quote_plus(
            f"DRIVER={{SQL Server}};"
            f"SERVER=DESKTOP-MQV3VAF;"
            f"DATABASE=tourism_gba;"
            f"Trusted_Connection=yes;"
        )
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

        # 检查comment表总数
        df_total = pd.read_sql("SELECT COUNT(*) as cnt FROM comment", engine)
        total = df_total['cnt'].iloc[0]
        print(f"数据库comment表总数: {total:,}")

        # 检查去重后的数量（按content+spot_id）
        df_unique = pd.read_sql("""
            SELECT COUNT(*) as cnt FROM (
                SELECT DISTINCT spot_id, content FROM comment
            ) t
        """, engine)
        unique_count = df_unique['cnt'].iloc[0]
        print(f"去重后数量(spot_id+content): {unique_count:,}")

        if total != unique_count:
            print(f"⚠️ 发现重复: {total - unique_count:,} 条")

        # 检查各spot_id的评论数分布
        df_dist = pd.read_sql("""
            SELECT spot_id, COUNT(*) as cnt
            FROM comment
            GROUP BY spot_id
            ORDER BY cnt DESC
        """, engine)

        print(f"\n📊 各景点评论数分布:")
        print(df_dist.head(10))

        # 检查是否有spot_id为0或NULL
        df_null = pd.read_sql("""
            SELECT COUNT(*) as cnt FROM comment WHERE spot_id IS NULL OR spot_id = 0
        """, engine)
        print(f"\nspot_id为NULL或0: {df_null['cnt'].iloc[0]} 条")

        # 对比清洗文件和数据库的数量差异
        df_file = pd.read_csv(CLEANED_RATINGS_FILE)
        print(f"\n清洗文件数: {len(df_file):,}")
        print(f"数据库数: {total:,}")
        print(f"差异: {total - len(df_file):,}")

        if total > len(df_file):
            print(f"⚠️ 数据库比文件多 {total - len(df_file):,} 条，说明04_generate_data.py生成了额外数据")

    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")


def check_spot_id_mapping():
    """检查spot_id映射关系"""
    print("\n" + "=" * 60)
    print("🔍 检查spot_id映射（清洗文件 vs 数据库）")
    print("=" * 60)

    try:
        from sqlalchemy import create_engine
        import urllib.parse

        params = urllib.parse.quote_plus(
            f"DRIVER={{SQL Server}};"
            f"SERVER=DESKTOP-MQV3VAF;"
            f"DATABASE=tourism_gba;"
            f"Trusted_Connection=yes;"
        )
        engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

        # 数据库中的景点数
        df_db_spots = pd.read_sql("SELECT COUNT(*) as cnt FROM scenic_spot", engine)
        db_spots = df_db_spots['cnt'].iloc[0]
        print(f"数据库scenic_spot表: {db_spots} 个景点")

        # 清洗文件中的景点名
        df_file = pd.read_csv(CLEANED_RATINGS_FILE)
        file_spots = df_file['matched_spots'].nunique()
        print(f"清洗文件匹配景点: {file_spots} 个")

        print(f"\n差异: {file_spots - db_spots} 个景点未入库")
        print("原因: 03_save_to_sql.py可能只入库了部分景点，或spot_id分配不一致")

    except Exception as e:
        print(f"❌ 检查失败: {e}")


if __name__ == "__main__":
    check_city_distribution()
    check_database_duplicates()
    check_spot_id_mapping()

    print("\n" + "=" * 60)
    print("💡 建议")
    print("=" * 60)
    print("1. 如果'中山公园'等匹配到非粤港澳城市，需要在05_clean_dianping_joint_filter.py")
    print("   中添加城市过滤条件（如address必须含'广州/深圳/珠海等'）")
    print("2. 如果数据库重复，需要清空comment表重新运行04_generate_data.py")
    print("3. 论文数据建议以清洗文件12,829条为准，数据库26,011条含重复/模拟数据")