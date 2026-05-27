# 03_save_to_sql.py - 最终修复版：字段名统一为 "type"
import pyodbc
import numpy as np
import ast

SERVER_NAME = "DESKTOP-MQV3VAF"
DATABASE_NAME = "tourism_gba"


def db_conn():
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE={DATABASE_NAME};"
        f"Trusted_Connection=yes;"
    )
    return pyodbc.connect(conn_str)


def load_crawled_spots():
    try:
        with open("cleaned_spots.txt", "r", encoding="utf-8") as f:
            data = f.read()
            spots = ast.literal_eval(data)
            print(f"解析出清洗后景点数量：{len(spots)} 个")
            return spots
    except Exception as e:
        print(f"读取失败：{str(e)}")
        return []


def clear_database_tables(cursor):
    tables = ['comment', 'hot_data', 'route']
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  已清空 {table} 表")
        except Exception as e:
            print(f"  清空 {table} 表失败: {e}")


def save_spots_to_sqlserver(spots):
    if not spots:
        print("没有可入库的景点数据！")
        return

    conn = db_conn()
    cursor = conn.cursor()

    print("\n清空旧数据...")
    clear_database_tables(cursor)

    count = 0
    fail_count = 0

    for idx, p in enumerate(spots):
        try:
            name = p.get("name", "") or ""
            cityname = p.get("cityname", "") or ""
            address = p.get("address", "") or ""
            location = p.get("location", "0,0") or "0,0"

            # 关键修复：字段名统一为 "type"
            typ = p.get("type", "") or ""

            level = p.get("level", "") or ""

            try:
                lng, lat = location.split(",")
                lat = float(lat.strip()) if lat.strip() else 0.0
                lng = float(lng.strip()) if lng.strip() else 0.0
            except:
                lat, lng = 0.0, 0.0

            visit_min = int(np.random.randint(40, 180))
            price = int(np.random.choice([0, 20, 40, 60, 80, 120, 150]))

            cursor.execute("""
                INSERT INTO scenic_spot
                (name, cityname, address, lat, lng, typ, level, visit_min, price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, cityname, address, lat, lng, typ, level, visit_min, price))
            count += 1

        except Exception as e:
            fail_count += 1
            if idx < 3:
                print(f"第{idx + 1}个失败：{str(e)}")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"\n入库成功：{count} 条，失败：{fail_count} 条")


if __name__ == "__main__":
    spots = load_crawled_spots()
    save_spots_to_sqlserver(spots)