# 01_create_db.py - 新增cityname字段
import pyodbc

# 配置（按你的环境改）
SERVER_NAME = "DESKTOP-MQV3VAF"
DATABASE_NAME = "tourism_gba"

def create_db_and_tables():
    # 1. 创建数据库
    master_conn = pyodbc.connect(
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE=master;"
        f"Trusted_Connection=yes;"
    )
    master_conn.autocommit = True
    cursor = master_conn.cursor()
    cursor.execute(f"IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = '{DATABASE_NAME}') CREATE DATABASE {DATABASE_NAME}")
    print(" 数据库创建成功（如果不存在）")
    cursor.close()
    master_conn.close()

    # 2. 创建表（新增cityname字段）
    conn_str = (
        f"DRIVER={{SQL Server}};"
        f"SERVER={SERVER_NAME};"
        f"DATABASE={DATABASE_NAME};"
        f"Trusted_Connection=yes;"
    )
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()

    # 景点表（新增cityname字段）
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'scenic_spot')
        CREATE TABLE scenic_spot (
            spot_id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(100),
            cityname NVARCHAR(50),  -- 新增城市名字段
            address NVARCHAR(255),
            lat DECIMAL(12,6),
            lng DECIMAL(12,6),
            typ NVARCHAR(100),
            level NVARCHAR(20),
            visit_min INT,
            price INT
        )
    """)

    # 热度表
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'hot_data')
        CREATE TABLE hot_data (
            id INT IDENTITY(1,1) PRIMARY KEY,
            spot_id INT,
            date DATE,
            hot_val FLOAT
        )
    """)

    # 评论表
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'comment')
        CREATE TABLE comment (
            cid INT IDENTITY(1,1) PRIMARY KEY,
            spot_id INT,
            content NVARCHAR(MAX),
            score FLOAT,
            sentiment FLOAT
        )
    """)

    # 路线表
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'route')
        CREATE TABLE route (
            route_id INT IDENTITY(1,1) PRIMARY KEY,
            route_name NVARCHAR(255),
            spot_ids NVARCHAR(255),
            days INT,
            total_min INT,
            hot_score FLOAT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print(" 所有表创建成功（含cityname字段）！")

if __name__ == "__main__":
    create_db_and_tables()