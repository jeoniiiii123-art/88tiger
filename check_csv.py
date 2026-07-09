import sys; sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
df = pd.read_csv('output/data.csv', encoding='utf-8-sig')
print('행수:', len(df))
print('날짜범위:', df['date'].min(), '~', df['date'].max())
for col in ['display_name','full_name','campaign']:
    has_quote = df[col].astype(str).str.contains('"').any()
    if has_quote:
        print(col, ': 따옴표 포함')
    has_nl = df[col].astype(str).str.contains('\n').any()
    if has_nl:
        print(col, ': 줄바꿈 포함')
