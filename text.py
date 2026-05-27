import os

# 测试路径
path = r"C:\Users\LENGDA\PycharmProjects\pythonProject\travel\yf_dianping\ratings\ratings.csv"

print(f"路径字符串: {path}")
print(f"文件存在: {os.path.exists(path)}")
if os.path.exists(path):
    print(f"文件大小: {os.path.getsize(path) / 1024 / 1024:.1f} MB")