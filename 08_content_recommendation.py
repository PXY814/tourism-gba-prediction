import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import create_engine
import urllib.parse

# ======================
# 你的数据库连接
# ======================
params = urllib.parse.quote_plus(
    "DRIVER={SQL Server};"
    "SERVER=DESKTOP-MQV3VAF;"
    "DATABASE=tourism_gba;"
    "Trusted_Connection=yes"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")

# ======================
# 读取景点表 + 评论表 + 热度表的真实字段
# ======================
# 1. 景点基本信息
spot_df = pd.read_sql("""
    SELECT spot_id, name, cityname, typ, level, visit_min, price
    FROM scenic_spot
""", engine)

# 2. 评论情感和评分（取每个景点的平均值）
comment_df = pd.read_sql("""
    SELECT spot_id, AVG(score) as avg_score, AVG(sentiment) as avg_sentiment
    FROM comment
    GROUP BY spot_id
""", engine)

# 3. 热度数据（取每个景点的平均热度）
hot_df = pd.read_sql("""
    SELECT spot_id, AVG(hot_val) as avg_hot
    FROM hot_data
    GROUP BY spot_id
""", engine)

# ======================
# 合并数据（所有字段都是你表里真实存在的）
# ======================
df = spot_df.merge(comment_df, on="spot_id", how="left")
df = df.merge(hot_df, on="spot_id", how="left")

# 处理空值
df.fillna(0, inplace=True)

# ======================
# 构建特征：类型 + 城市 + 等级 + 评分 + 热度 + 价格 + 游玩时长
# ======================
# 1. 类别型特征独热编码
cat_features = pd.get_dummies(df[["cityname", "typ", "level"]])

# 2. 数值型特征
num_features = df[["avg_score", "avg_sentiment", "avg_hot", "visit_min", "price"]]

# 3. 合并所有特征
features = pd.concat([cat_features, num_features], axis=1)

# ======================
# 计算余弦相似度
# ======================
similarity = cosine_similarity(features)

# ======================
# 推荐函数：输入景点ID，返回相似景点
# ======================
def recommend(spot_id, topN=5):
    # 找到景点在DataFrame中的索引
    idx = df[df["spot_id"] == spot_id].index[0]
    # 取相似度最高的topN个（排除自己）
    similar_indices = similarity[idx].argsort()[::-1][1:topN+1]
    # 返回推荐结果
    return df.iloc[similar_indices][["spot_id", "name", "cityname", "typ", "avg_score", "avg_hot"]]

# ======================
# 测试推荐：输入景点1
# ======================
print("=== 景点推荐结果 ===")
print(recommend(spot_id=1))