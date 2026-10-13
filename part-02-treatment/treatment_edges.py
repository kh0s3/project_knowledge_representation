import pandas as pd
from pathlib import Path

input_file = '../dataset/edges_semiconductor_trade.csv'

output_folder = Path('./output') # output_folder.mkdir(parents=True, exist_ok=True)
output_csv = output_folder / 'edges_semiconductor_trade_ag.csv'
output_txt = output_folder / 'report_treatment_edge.txt'

df = pd.read_csv(input_file)

iso_codes_to_drop = [
    '_X', 'X1', 'E19', 'A59', 'O19', 'A79', 'F19', 
    'ATA', 'BVT', 'HMD', 'IOT', 'ATF', 'UMI'
]

# filtering, keep only the rows where BOTH the exporter AND importer are valid (Meaning neither of them are in the drop list)
df_filtered = df[~df['exporter_iso'].isin(iso_codes_to_drop)]
df_filtered = df_filtered[~df_filtered['importer_iso'].isin(iso_codes_to_drop)]

group_columns = [
    'year', 
    'tier',
    'exporter_iso', 
    'exporter_name', 
    'importer_iso', 
    'importer_name'
]

# performing the aggregation
df_aggregated = df_filtered.groupby(group_columns, as_index=False)['trade_value_usd'].sum()

df_aggregated = df_aggregated.sort_values(
    by=['year','exporter_iso', 'importer_iso', 'tier']
)

df_aggregated.to_csv(output_csv, index=False)

summary_text = (
    f"\nEdges Semiconductor Trade Aggregation Report\n\n"
    f"Old dataset row count: {len(df):,}\n"
    f"New aggregated row count: {len(df_aggregated):,}\n"
    f"Successfully saved to {output_csv}\n"
)
output_txt.write_text(summary_text)
print(summary_text)