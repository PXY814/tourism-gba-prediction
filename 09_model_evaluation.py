# 09_model_evaluation.py
# 功能：景点热度预测模型评估（MAE、RMSE、MAPE）
# 更新：连接数据库读取真实数据，对接 Prophet 预测结果，自动生成评估报告

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
import urllib.parse
from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings

warnings.filterwarnings("ignore")

# ===========================
# 修复中文显示
# ===========================
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# ======================
# 数据库连接
# ======================
params = urllib.parse.quote_plus(
    "DRIVER={SQL Server};"
    "SERVER=DESKTOP-MQV3VAF;"
    "DATABASE=tourism_gba;"
    "Trusted_Connection=yes"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}")


# ============================
# 中国法定节假日配置（2023-2027）
# ============================
def get_china_holidays():
    holidays = pd.DataFrame({
        'holiday': 'spring_festival',
        'ds': pd.to_datetime([
            '2023-01-21', '2024-02-09', '2025-01-28', '2026-02-16'
        ]),
        'lower_window': -5,
        'upper_window': 10
    })

    labor_day = pd.DataFrame({
        'holiday': 'labor_day',
        'ds': pd.to_datetime([
            '2023-05-01', '2024-05-01', '2025-05-01', '2026-05-01'
        ]),
        'lower_window': -1,
        'upper_window': 2
    })

    national_day = pd.DataFrame({
        'holiday': 'national_day',
        'ds': pd.to_datetime([
            '2023-10-01', '2024-10-01', '2025-10-01', '2026-10-01'
        ]),
        'lower_window': -2,
        'upper_window': 3
    })

    other_holidays = pd.DataFrame({
        'holiday': ['new_year', 'new_year', 'new_year', 'new_year',
                    'qingming', 'qingming', 'qingming', 'qingming',
                    'dragon_boat', 'dragon_boat', 'dragon_boat', 'dragon_boat',
                    'mid_autumn', 'mid_autumn', 'mid_autumn', 'mid_autumn'],
        'ds': pd.to_datetime([
            '2023-01-01', '2024-01-01', '2025-01-01', '2026-01-01',
            '2023-04-05', '2024-04-04', '2025-04-04', '2026-04-04',
            '2023-06-22', '2024-06-10', '2025-05-31', '2026-06-19',
            '2023-09-29', '2024-09-17', '2025-10-06', '2026-09-25'
        ]),
        'lower_window': -1,
        'upper_window': 1
    })

    all_holidays = pd.concat([holidays, labor_day, national_day, other_holidays], ignore_index=True)
    return all_holidays


def train_prophet_model(df, forecast_days=14):
    """
    训练 Prophet 模型并返回预测结果
    """
    prophet_df = df.reset_index().rename(columns={'date': 'ds', 'hot_val': 'y'})

    # 划分训练集和测试集
    train_df = prophet_df[:-forecast_days].copy()
    test_df = prophet_df[-forecast_days:].copy()

    # 训练模型
    holidays = get_china_holidays()
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        holidays=holidays,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
        holidays_prior_scale=10.0,
        interval_width=0.95
    )
    model.fit(train_df)

    # 预测
    future = model.make_future_dataframe(periods=forecast_days)
    forecast = model.predict(future)

    # 提取测试集预测
    pred_test = forecast[-forecast_days:]['yhat'].values
    test_real = test_df['y'].values
    test_dates = test_df['ds'].values

    return test_real, pred_test, test_dates, train_df, test_df, model, forecast


def evaluate_model(spot_id=1, forecast_days=14):
    """
    完整的模型评估流程：
    1. 读取数据
    2. 训练 Prophet 模型
    3. 计算评估指标（MAE、RMSE、MAPE）
    4. 可视化对比
    5. 输出评估报告
    """
    print("=" * 60)
    print(f"景点 {spot_id} 热度预测模型评估")
    print("=" * 60)

    # 1. 读取数据
    df = pd.read_sql(f"""
        SELECT date, AVG(hot_val) as hot_val 
        FROM hot_data 
        WHERE spot_id = {spot_id}
        GROUP BY date
        ORDER BY date
    """, engine)

    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.asfreq('D')
    df['hot_val'] = df['hot_val'].interpolate()

    print(f"\n数据概况：")
    print(f"  时间范围：{df.index.min().date()} ~ {df.index.max().date()}")
    print(f"  数据天数：{len(df)} 天")
    print(f"  热度均值：{df['hot_val'].mean():.2f}")
    print(f"  热度标准差：{df['hot_val'].std():.2f}")

    # 2. 训练模型并预测
    print(f"\n训练 Prophet 模型（测试集：最近{forecast_days}天）...")
    test_real, pred_test, test_dates, train_df, test_df, model, forecast = train_prophet_model(df, forecast_days)

    # 3. 计算评估指标
    mae = mean_absolute_error(test_real, pred_test)
    rmse = np.sqrt(mean_squared_error(test_real, pred_test))
    mape = np.mean(np.abs((test_real - pred_test) / test_real)) * 100

    # 额外指标
    mse = mean_squared_error(test_real, pred_test)
    residuals = test_real - pred_test
    residual_mean = residuals.mean()
    residual_std = residuals.std()

    print(f"\n{'=' * 40}")
    print("模型评估指标")
    print(f"{'=' * 40}")
    print(f"MAE  (平均绝对误差):     {mae:.4f}")
    print(f"RMSE (均方根误差):       {rmse:.4f}")
    print(f"MSE  (均方误差):         {mse:.4f}")
    print(f"MAPE (平均绝对百分比误差): {mape:.2f}%")
    print(f"{'=' * 40}")
    print(f"残差均值: {residual_mean:.4f}")
    print(f"残差标准差: {residual_std:.4f}")
    print(f"最大正残差: {residuals.max():.4f}")
    print(f"最大负残差: {residuals.min():.4f}")

    # 4. 评估等级判断
    print(f"\n{'=' * 40}")
    print("模型质量评级")
    print(f"{'=' * 40}")
    if mape < 10:
        grade = "优秀 (高精度)"
        desc = "预测结果非常可靠，可直接用于业务决策"
    elif mape < 20:
        grade = "良好 (可接受)"
        desc = "预测结果较为准确，可用于常规分析"
    elif mape < 50:
        grade = "一般 (需改进)"
        desc = "预测结果存在偏差，建议结合其他方法验证"
    else:
        grade = "较差 (不可靠)"
        desc = "预测误差过大，不建议用于实际决策"

    print(f"MAPE = {mape:.2f}% → 评级: {grade}")
    print(f"说明: {desc}")

    # 5. 可视化
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 子图1：真实值 vs 预测值对比
    ax1 = axes[0, 0]
    x = range(len(test_real))
    ax1.plot(x, test_real, 'g-o', label='真实值', linewidth=2, markersize=6)
    ax1.plot(x, pred_test, 'r--s', label='预测值', linewidth=2, markersize=5)
    ax1.set_title('测试集：真实值 vs 预测值', fontsize=12, fontweight='bold')
    ax1.set_xlabel('天数')
    ax1.set_ylabel('热度指数')
    ax1.legend()
    ax1.grid(alpha=0.3)

    # 添加指标文本框
    textstr = f'MAE={mae:.2f}\nRMSE={rmse:.2f}\nMAPE={mape:.1f}%'
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # 子图2：残差分析
    ax2 = axes[0, 1]
    colors = ['green' if r > 0 else 'red' for r in residuals]
    ax2.bar(x, residuals, color=colors, alpha=0.7)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax2.set_title('残差分布（真实值 - 预测值）', fontsize=12, fontweight='bold')
    ax2.set_xlabel('天数')
    ax2.set_ylabel('残差')
    ax2.grid(alpha=0.3, axis='y')

    # 子图3：散点图（真实值 vs 预测值）
    ax3 = axes[1, 0]
    ax3.scatter(test_real, pred_test, c='blue', alpha=0.6, s=80, edgecolors='black')

    # 完美预测线 y=x
    min_val = min(test_real.min(), pred_test.min()) - 2
    max_val = max(test_real.max(), pred_test.max()) + 2
    ax3.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='完美预测线 (y=x)')

    ax3.set_title('真实值 vs 预测值散点图', fontsize=12, fontweight='bold')
    ax3.set_xlabel('真实热度值')
    ax3.set_ylabel('预测热度值')
    ax3.legend()
    ax3.grid(alpha=0.3)

    # 子图4：残差直方图
    ax4 = axes[1, 1]
    ax4.hist(residuals, bins=10, color='steelblue', alpha=0.7, edgecolor='black')
    ax4.axvline(x=0, color='red', linestyle='--', linewidth=2, label='零误差线')
    ax4.axvline(x=residual_mean, color='green', linestyle='-', linewidth=2, label=f'残差均值 ({residual_mean:.2f})')
    ax4.set_title('残差分布直方图', fontsize=12, fontweight='bold')
    ax4.set_xlabel('残差')
    ax4.set_ylabel('频数')
    ax4.legend()
    ax4.grid(alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(f"景点{spot_id}_模型评估报告.png", dpi=300, bbox_inches="tight")
    print(f"\n 评估图表已保存: 景点{spot_id}_模型评估报告.png")
    plt.show()

    # 6. 详细对比表
    print(f"\n{'=' * 60}")
    print("测试集详细对比")
    print(f"{'=' * 60}")
    print(f"{'日期':<12} {'真实值':>8} {'预测值':>8} {'残差':>8} {'误差%':>8}")
    print("-" * 60)
    for date, true, pred in zip(test_dates, test_real, pred_test):
        residual = true - pred
        pct_error = abs(residual / true) * 100
        marker = " [周末]" if pd.Timestamp(date).weekday() >= 5 else ""
        print(f"{str(date)[:10]}{marker:<8} {true:>8.2f} {pred:>8.2f} {residual:>8.2f} {pct_error:>7.2f}%")

    return {
        'spot_id': spot_id,
        'mae': mae,
        'rmse': rmse,
        'mse': mse,
        'mape': mape,
        'residual_mean': residual_mean,
        'residual_std': residual_std,
        'grade': grade
    }


if __name__ == "__main__":
    results = []
    for spot_id in [1, 2, 3]:
        try:
            result = evaluate_model(spot_id=spot_id, forecast_days=14)
            results.append(result)
            print("\n" + "=" * 60 + "\n")
        except Exception as e:
            print(f"景点{spot_id}评估失败: {e}")
            import traceback

            traceback.print_exc()

    # 汇总报告
    if results:
        print("\n" + "=" * 60)
        print("多景点模型评估汇总")
        print("=" * 60)
        for r in results:
            print(f"景点{r['spot_id']}: MAE={r['mae']:.2f}, RMSE={r['rmse']:.2f}, MAPE={r['mape']:.1f}% → {r['grade']}")