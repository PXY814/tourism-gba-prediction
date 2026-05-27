# 07_predict_trend.py - Prophet预测（处理强季节性+节假日）
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
    """
    中国主要法定节假日
    lower_window: 节前多少天开始影响（如春运提前3天）
    upper_window: 节后多少天仍有影响（如节后返程高峰）
    """
    holidays = pd.DataFrame({
        'holiday': 'spring_festival',
        'ds': pd.to_datetime([
            '2023-01-22', '2024-02-10', '2025-01-29',
            '2026-02-17', '2027-02-06'
        ]),
        'lower_window': -5,
        'upper_window': 10
    })

    labor_day = pd.DataFrame({
        'holiday': 'labor_day',
        'ds': pd.to_datetime([
            '2023-05-01', '2024-05-01', '2025-05-01',
            '2026-05-01', '2027-05-01'
        ]),
        'lower_window': -2,
        'upper_window': 3
    })

    national_day = pd.DataFrame({
        'holiday': 'national_day',
        'ds': pd.to_datetime([
            '2023-10-01', '2024-10-01', '2025-10-01',
            '2026-10-01', '2027-10-01'
        ]),
        'lower_window': -2,
        'upper_window': 7
    })

    # 其他小长假
    other_holidays = pd.DataFrame({
        'holiday': ['new_year', 'new_year', 'new_year', 'new_year', 'new_year',
                    'qingming', 'qingming', 'qingming', 'qingming', 'qingming',
                    'dragon_boat', 'dragon_boat', 'dragon_boat', 'dragon_boat', 'dragon_boat',
                    'mid_autumn', 'mid_autumn', 'mid_autumn', 'mid_autumn', 'mid_autumn'],
        'ds': pd.to_datetime([
            '2023-01-01', '2024-01-01', '2025-01-01', '2026-01-01', '2027-01-01',
            '2023-04-05', '2024-04-04', '2025-04-04', '2026-04-04', '2027-04-05',
            '2023-06-22', '2024-06-10', '2025-05-31', '2026-06-19', '2027-06-09',
            '2023-09-29', '2024-09-17', '2025-10-06', '2026-09-25', '2027-09-15'
        ]),
        'lower_window': -1,
        'upper_window': 2
    })

    all_holidays = pd.concat([holidays, labor_day, national_day, other_holidays], ignore_index=True)
    return all_holidays


def predict_and_evaluate(spot_id=1, forecast_days=14, recent_days=90, tail_days=30):
    """
    Prophet完整预测流程：
    1. 读取数据
    2. 数据预处理（Prophet格式 ds, y）
    3. 训练测试划分
    4. Prophet模型训练（含节假日）
    5. 测试集验证
    6. 未来预测
    7. 评估（MAE, RMSE, MAPE）
    8. 可视化（4子图优化版）
    """
    print("=" * 60)
    print(f"景点 {spot_id} 热度预测分析（Prophet版）")
    print("=" * 60)

    # 1. 读取数据
    df = pd.read_sql(f"""
        SELECT date, AVG(hot_val) as hot_val 
        FROM hot_data 
        WHERE spot_id = {spot_id}
        GROUP BY date
        ORDER BY date
    """, engine)

    if len(df) < 60:
        print(f"警告：数据量仅 {len(df)} 天，建议至少730天数据！")
        print("请先运行 04_generate_data.py 生成更长时间的数据\n")

    # 2. 数据预处理
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.asfreq('D')
    df['hot_val'] = df['hot_val'].interpolate()

    # Prophet要求格式：ds（日期）, y（数值）
    prophet_df = df.reset_index().rename(columns={'date': 'ds', 'hot_val': 'y'})

    print(f"\n数据概况：")
    print(f"  时间范围：{prophet_df['ds'].min().date()} ~ {prophet_df['ds'].max().date()}")
    print(f"  数据天数：{len(prophet_df)} 天")
    print(f"  热度均值：{prophet_df['y'].mean():.2f}")
    print(f"  热度标准差：{prophet_df['y'].std():.2f}")
    print(f"  热度范围：{prophet_df['y'].min():.2f} ~ {prophet_df['y'].max():.2f}")

    # 3. 划分训练集和测试集
    train_df = prophet_df[:-forecast_days].copy()
    test_df = prophet_df[-forecast_days:].copy()

    print(f"\n数据划分：")
    print(f"  训练集：{len(train_df)} 天 ({train_df['ds'].iloc[0].date()} ~ {train_df['ds'].iloc[-1].date()})")
    print(f"  测试集：{len(test_df)} 天 ({test_df['ds'].iloc[0].date()} ~ {test_df['ds'].iloc[-1].date()})")

    # 4. 训练Prophet模型
    print(f"\n训练Prophet模型...")
    holidays = get_china_holidays()

    model = Prophet(
        yearly_seasonality=True,  # 年周期（淡旺季）
        weekly_seasonality=True,  # 周周期（周末效应）
        daily_seasonality=False,  # 日周期（不需要）
        holidays=holidays,  # 中国节假日
        changepoint_prior_scale=0.05,  # 趋势变化灵敏度（越小越平滑）
        seasonality_prior_scale=10.0,  # 季节性强度
        holidays_prior_scale=10.0,  # 节假日效应强度
        interval_width=0.95  # 置信区间95%
    )

    # 可以添加自定义季节性（如月度模式）
    # model.add_seasonality(name='monthly', period=30.5, fourier_order=5)

    model.fit(train_df)
    print(f"  模型训练完成！")

    # 5. 测试集验证
    print(f"\n在测试集上验证...")

    # 构造测试集日期框
    future_test = model.make_future_dataframe(periods=forecast_days)
    forecast_test = model.predict(future_test)

    # 提取测试集预测
    pred_test = forecast_test[-forecast_days:]['yhat'].values
    test_real = test_df['y'].values

    mae = mean_absolute_error(test_real, pred_test)
    rmse = np.sqrt(mean_squared_error(test_real, pred_test))
    mape = np.mean(np.abs((test_real - pred_test) / test_real)) * 100

    print(f"\n测试集评估指标：")
    print(f"  MAE:  {mae:.4f}")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  MAPE: {mape:.2f}%")

    # 6. 未来预测（用全部历史数据重新训练）
    print(f"\n预测未来 {forecast_days} 天...")

    final_model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        holidays=holidays,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
        holidays_prior_scale=10.0,
        interval_width=0.95
    )
    final_model.fit(prophet_df)

    future = final_model.make_future_dataframe(periods=forecast_days)
    future_forecast = final_model.predict(future)

    # 提取未来预测
    future_pred = future_forecast[-forecast_days:].copy()
    future_dates = future_pred['ds']
    future_mean = future_pred['yhat'].values
    future_lower = future_pred['yhat_lower'].values
    future_upper = future_pred['yhat_upper'].values

    print(f"\n未来{forecast_days}天预测结果：")
    for date, val, low, high in zip(future_dates, future_mean, future_lower, future_upper):
        marker = " [周末]" if date.weekday() >= 5 else ""
        print(f"  {date.strftime('%Y-%m-%d')}{marker}: {val:.2f} (CI: {low:.1f}~{high:.1f})")

    # ============================
    # 7. 可视化（4子图优化版）
    # ============================

    # 准备局部数据
    recent_data = prophet_df.iloc[-recent_days:].copy()
    history_tail = prophet_df.iloc[-tail_days:].copy()

    # 计算合理的Y轴范围
    y_min = min(recent_data['y'].min(), test_real.min(), future_mean.min()) - 5
    y_max = max(recent_data['y'].max(), test_real.max(), future_mean.max()) + 5

    fig = plt.figure(figsize=(16, 12))

    # --- 子图1：验证图（最近90天放大）---
    ax1 = plt.subplot(2, 2, 1)

    # 训练集最近部分
    train_recent = train_df.iloc[-(recent_days - forecast_days):].copy()
    ax1.plot(train_recent['ds'], train_recent['y'],
             label='训练集（近期）', color='#2f86eb', linewidth=1.5, alpha=0.8)

    # 测试集真实值
    ax1.plot(test_df['ds'], test_real,
             label='测试集（真实）', color='green', linewidth=2.5, marker='o', markersize=4)

    # 测试集预测值
    ax1.plot(test_df['ds'], pred_test,
             label='测试集（预测）', color='red', linewidth=2, linestyle='--',
             marker='s', markersize=4)

    # 分隔线
    ax1.axvline(x=train_df['ds'].iloc[-1], color='gray', linestyle=':',
                alpha=0.7, linewidth=1.5)

    ax1.set_title(f'景点{spot_id} Prophet验证（局部放大）',
                  fontsize=12, fontweight='bold')
    ax1.set_xlabel('日期')
    ax1.set_ylabel('热度指数')
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(alpha=0.3)
    ax1.set_ylim(y_min, y_max)

    # 评估指标文本框
    textstr = f'MAE={mae:.2f}\nRMSE={rmse:.2f}\nMAPE={mape:.1f}%'
    ax1.text(0.02, 0.98, textstr, transform=ax1.transAxes, fontsize=10,
             verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))

    # --- 子图2：预测衔接图（历史尾部 + 未来预测）---
    ax2 = plt.subplot(2, 2, 2)

    ax2.plot(history_tail['ds'], history_tail['y'],
             label=f'历史热度（最近{tail_days}天）',
             color='#2f86eb', linewidth=2, marker='o', markersize=3)

    ax2.plot(future_dates, future_mean,
             label='未来预测', color='red', linewidth=2.5, marker='D', markersize=5)

    # 置信区间
    ax2.fill_between(future_dates, future_lower, future_upper,
                     alpha=0.25, color='red', label='95%置信区间')

    # 衔接处的垂直线
    ax2.axvline(x=prophet_df['ds'].iloc[-1], color='gray', linestyle=':',
                alpha=0.7, linewidth=1.5)

    ax2.set_title(f'热度趋势衔接预测（最近{tail_days}天 + 未来{forecast_days}天）',
                  fontsize=12, fontweight='bold')
    ax2.set_xlabel('日期')
    ax2.set_ylabel('热度指数')
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(alpha=0.3)

    # 自适应Y轴
    local_y_min = min(history_tail['y'].min(), future_lower.min()) - 3
    local_y_max = max(history_tail['y'].max(), future_upper.max()) + 3
    ax2.set_ylim(local_y_min, local_y_max)

    # --- 子图3：仅14天预测放大对比（最关键！）---
    ax3 = plt.subplot(2, 2, 3)

    # 测试集真实值
    ax3.plot(test_df['ds'], test_real,
             label='测试集真实值', color='green', linewidth=2.5, marker='o', markersize=6)

    # 测试集预测
    ax3.plot(test_df['ds'], pred_test,
             label='测试集预测', color='orange', linewidth=2, linestyle='--',
             marker='s', markersize=5)

    # 未来预测
    ax3.plot(future_dates, future_mean,
             label='未来预测', color='red', linewidth=2.5, marker='D', markersize=6)

    # 未来置信区间
    ax3.fill_between(future_dates, future_lower, future_upper,
                     alpha=0.3, color='red')

    # 分隔线
    ax3.axvline(x=train_df['ds'].iloc[-1], color='blue', linestyle='-.',
                alpha=0.5, label='训练/测试分界')

    ax3.set_title(f'{forecast_days}天预测细节放大对比',
                  fontsize=12, fontweight='bold')
    ax3.set_xlabel('日期')
    ax3.set_ylabel('热度指数')
    ax3.legend(loc='best', fontsize=9)
    ax3.grid(alpha=0.3)
    ax3.set_ylim(local_y_min, local_y_max)
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=30, ha='right')

    # --- 子图4：残差分析 ---
    ax4 = plt.subplot(2, 2, 4)

    residuals = test_real - pred_test
    colors = ['green' if r > 0 else 'red' for r in residuals]  # 预测偏高/偏低

    ax4.bar(range(len(residuals)), residuals, color=colors, alpha=0.7)
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax4.set_title('测试集残差（真实值 - 预测值）\n绿色=预测偏低，红色=预测偏高',
                  fontsize=12, fontweight='bold')
    ax4.set_xlabel('天数')
    ax4.set_ylabel('残差')
    ax4.grid(alpha=0.3, axis='y')

    # 残差统计
    res_text = (f'残差均值: {residuals.mean():.2f}\n'
                f'残差标准差: {residuals.std():.2f}\n'
                f'最大正残差: {residuals.max():.2f}\n'
                f'最大负残差: {residuals.min():.2f}')
    ax4.text(0.98, 0.98, res_text, transform=ax4.transAxes, fontsize=10,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

    plt.tight_layout()
    plt.savefig(f"景点{spot_id}_热度预测Prophet优化版.png", dpi=300, bbox_inches="tight")
    print(f"\n 图表已保存: 景点{spot_id}_热度预测Prophet优化版.png")
    plt.show()

    # 额外：Prophet组件分解图（趋势+季节性+节假日）
    print(f"\n生成Prophet组件分解图...")
    fig_comp = final_model.plot_components(future_forecast)
    fig_comp.set_size_inches(12, 10)
    plt.tight_layout()
    plt.savefig(f"景点{spot_id}_Prophet组件分解.png", dpi=300, bbox_inches="tight")
    print(f"  组件分解图已保存: 景点{spot_id}_Prophet组件分解.png")
    plt.show()

    return {
        'spot_id': spot_id,
        'mae': mae,
        'rmse': rmse,
        'mape': mape
    }


if __name__ == "__main__":
    results = []
    for spot_id in [1, 2, 3]:
        try:
            result = predict_and_evaluate(spot_id=spot_id, forecast_days=14, recent_days=90)
            results.append(result)
            print("\n" + "=" * 60 + "\n")
        except Exception as e:
            print(f"景点{spot_id}预测失败: {e}")
            import traceback

            traceback.print_exc()

    if results:
        print("\n" + "=" * 60)
        print("多景点预测结果汇总（Prophet）")
        print("=" * 60)
        for r in results:
            print(f"景点{r['spot_id']}: MAE={r['mae']:.2f}, RMSE={r['rmse']:.2f}, MAPE={r['mape']:.1f}%")