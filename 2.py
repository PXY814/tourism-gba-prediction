# check_field_name.py - 检查清洗后数据的字段名
import ast

with open("cleaned_spots.txt", "r", encoding="utf-8") as f:
    data = ast.literal_eval(f.read())

print("字段列表:", list(data[0].keys()))
print("\n第一条数据示例:")
for k, v in data[0].items():
    print(f"  {k}: {v}")