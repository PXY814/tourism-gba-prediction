# 05_2_sentiment_chart.py - 最终版：分析情感构成而非平均值
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from collections import Counter
from sqlalchemy import create_engine
import urllib

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


def get_sentiment_composition(engine):
    """
    核心改进：分析每个景点的情感构成（好评率/差评率/争议度）
    而不是只看平均情感
    """
    print("=" * 60)
    print("🔍 景点情感构成分析")
    print("=" * 60)

    sql = """
        SELECT 
            s.spot_id,
            s.name,
            COUNT(c.cid) as total,
            SUM(CASE WHEN c.sentiment >= 0.8 THEN 1 ELSE 0 END) as very_positive,
            SUM(CASE WHEN c.sentiment >= 0.6 AND c.sentiment < 0.8 THEN 1 ELSE 0 END) as positive,
            SUM(CASE WHEN c.sentiment >= 0.4 AND c.sentiment < 0.6 THEN 1 ELSE 0 END) as neutral,
            SUM(CASE WHEN c.sentiment >= 0.2 AND c.sentiment < 0.4 THEN 1 ELSE 0 END) as negative,
            SUM(CASE WHEN c.sentiment < 0.2 THEN 1 ELSE 0 END) as very_negative,
            AVG(c.sentiment) as avg_sentiment,
            STDEV(c.sentiment) as std_sentiment
        FROM scenic_spot s
        INNER JOIN comment c ON s.spot_id = c.spot_id
        WHERE c.sentiment IS NOT NULL
        GROUP BY s.spot_id, s.name
        HAVING COUNT(c.cid) >= 50
    """

    df = pd.read_sql(sql, engine)

    # 计算衍生指标
    df['positive_rate'] = (df['very_positive'] + df['positive']) / df['total'] * 100
    df['negative_rate'] = (df['very_negative'] + df['negative']) / df['total'] * 100
    df['controversy'] = df['std_sentiment']  # 争议度=标准差
    df['polarization'] = (df['very_positive'] + df['very_negative']) / df['total'] * 100  # 两极化程度

    print(f"\n📊 共分析 {len(df)} 个景点（≥50条评论）")
    print(f"\n情感构成示例：")
    for _, row in df.head(5).iterrows():
        print(f"  {row['name'][:10]:<10} | 好评{row['positive_rate']:.1f}% | "
              f"差评{row['negative_rate']:.1f}% | 争议{row['controversy']:.3f}")

    return df


def select_diverse_spots(df, n=10):
    """
    基于情感构成选择多样化景点（而非平均情感）
    """
    # 定义4种类型
    df['type'] = '普通'

    # 类型1：好评如潮（好评率>90%）
    mask = df['positive_rate'] > 90
    df.loc[mask, 'type'] = '好评如潮'

    # 类型2：争议景点（两极化>60%，标准差>0.35）
    mask = (df['polarization'] > 60) & (df['controversy'] > 0.35)
    df.loc[mask, 'type'] = '争议景点'

    # 类型3：差评较多（差评率>20%）
    mask = df['negative_rate'] > 20
    df.loc[mask, 'type'] = '差评较多'

    # 类型4：口碑分化（好评>50%且差评>15%）
    mask = (df['positive_rate'] > 50) & (df['negative_rate'] > 15) & (df['type'] == '普通')
    df.loc[mask, 'type'] = '口碑分化'

    # 从每种类型抽样
    selected = []
    for t in ['好评如潮', '争议景点', '差评较多', '口碑分化', '普通']:
        subset = df[df['type'] == t]
        if len(subset) > 0:
            n_sample = min(3 if t != '普通' else 2, len(subset))
            sample = subset.nlargest(n_sample, 'total')  # 选评论数多的
            selected.append(sample)
            print(f"  {t}: {len(subset)}个景点，选{n_sample}个")

    result = pd.concat(selected).reset_index(drop=True)
    print(f"\n✅ 最终选择 {len(result)} 个多样化景点")
    return result


def generate_sentiment_chart():
    engine = get_engine()
    df = get_sentiment_composition(engine)

    if df.empty:
        print("❌ 无数据")
        return

    # 选择多样化景点
    df_selected = select_diverse_spots(df, n=10)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # ========== 子图1：情感构成堆叠条形图（核心改进） ==========
    ax1 = axes[0, 0]

    # 准备堆叠数据
    categories = ['very_negative', 'negative', 'neutral', 'positive', 'very_positive']
    cat_labels = ['非常负面', '负面', '中性', '正面', '非常正面']
    colors_stack = ['#d62728', '#ff7f0e', '#ffbb78', '#2ca02c', '#1f77b4']

    bottom = np.zeros(len(df_selected))
    for cat, label, color in zip(categories, cat_labels, colors_stack):
        values = df_selected[cat] / df_selected['total'] * 100
        ax1.barh(df_selected['name'], values, left=bottom, label=label, color=color, alpha=0.8)
        bottom += values

    ax1.set_xlabel("评论占比 (%)", fontsize=11)
    ax1.set_title("景点评论情感构成分析", fontsize=13, fontweight="bold")
    ax1.legend(loc='lower right', fontsize=8)
    ax1.set_xlim(0, 100)

    # 添加类型标签
    for i, (_, row) in enumerate(df_selected.iterrows()):
        ax1.text(102, i, f"[{row['type']}]", va='center', fontsize=9, fontweight='bold')

    # ========== 子图2：好评率 vs 争议度散点图 ==========
    ax2 = axes[0, 1]

    type_colors = {
        '好评如潮': 'green',
        '争议景点': 'red',
        '差评较多': 'darkred',
        '口碑分化': 'orange',
        '普通': 'gray'
    }

    for t in df_selected['type'].unique():
        subset = df_selected[df_selected['type'] == t]
        ax2.scatter(subset['positive_rate'], subset['controversy'],
                    s=subset['total'] * 2, c=type_colors.get(t, 'gray'),
                    alpha=0.7, edgecolors='black', label=t)

    ax2.axhline(y=0.35, color='red', linestyle='--', alpha=0.5, label='高争议线')
    ax2.axvline(x=90, color='green', linestyle='--', alpha=0.5, label='高好评线')

    ax2.set_xlabel("好评率 (%)", fontsize=11)
    ax2.set_ylabel("争议度（标准差）", fontsize=11)
    ax2.set_title("好评率 vs 争议度（气泡=评论数）", fontsize=13, fontweight="bold")
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(alpha=0.3)

    # ========== 子图3：两极化程度对比 ==========
    ax3 = axes[1, 0]

    sorted_df = df_selected.sort_values('polarization', ascending=True)
    colors_bar = [type_colors.get(t, 'gray') for t in sorted_df['type']]

    bars = ax3.barh(sorted_df['name'], sorted_df['polarization'], color=colors_bar, alpha=0.8, edgecolor='black')
    ax3.set_xlabel("两极化程度 (%)", fontsize=11)
    ax3.set_title("景点评论两极化程度（极端好评+极端差评占比）", fontsize=13, fontweight="bold")
    ax3.grid(axis='x', alpha=0.3)

    for bar, val in zip(bars, sorted_df['polarization']):
        ax3.text(val + 1, bar.get_y() + bar.get_height() / 2,
                 f"{val:.1f}%", va='center', fontsize=9)

    # ========== 子图4：类型分布饼图 ==========
    ax4 = axes[1, 1]

    type_counts = df_selected['type'].value_counts()
    colors_pie = [type_colors.get(t, 'gray') for t in type_counts.index]

    wedges, texts, autotexts = ax4.pie(
        type_counts.values, labels=type_counts.index, colors=colors_pie,
        autopct='%1.1f%%', startangle=90, explode=[0.05] * len(type_counts)
    )

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(11)

    ax4.set_title("景点情感类型分布", fontsize=13, fontweight="bold")

    plt.suptitle("粤港澳大湾区景点评论情感构成分析", fontsize=16, fontweight="bold", y=0.98)
    plt.tight_layout()
    plt.savefig("粤港澳景点情感分析_构成版.png", dpi=300, bbox_inches="tight")
    print("\n✅ 已保存：粤港澳景点情感分析_构成版.png")

    # 统计
    print("\n📊 最终统计：")
    print(f"  分析景点数：{len(df_selected)}")
    print(f"  总评论数：{df_selected['total'].sum()}")

    print(f"\n📊 情感类型分布：")
    for t, count in type_counts.items():
        print(f"  {t}：{count}个景点（{count / len(df_selected) * 100:.1f}%）")

    print(f"\n📊 关键指标范围：")
    print(f"  好评率：[{df_selected['positive_rate'].min():.1f}% ~ {df_selected['positive_rate'].max():.1f}%]")
    print(f"  差评率：[{df_selected['negative_rate'].min():.1f}% ~ {df_selected['negative_rate'].max():.1f}%]")
    print(f"  争议度：[{df_selected['controversy'].min():.3f} ~ {df_selected['controversy'].max():.3f}]")


if __name__ == "__main__":
    generate_sentiment_chart()