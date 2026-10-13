import pandas as pd
from pathlib import Path

nodes_input_file = '../dataset/nodes_countries.csv'
edges_input_file = './output/edges_semiconductor_trade_ag.csv'

output_folder = Path('./output') # output_folder.mkdir(parents=True, exist_ok=True)
output_nodes_file = output_folder / 'nodes_countries_up.csv' 

iso_codes_to_drop = [
    '_X', 'X1', 'E19', 'A59', 'O19', 'A79', 'F19', 
    'ATA', 'BVT', 'HMD', 'IOT', 'ATF', 'UMI'
]

df_nodes = pd.read_csv(nodes_input_file)
df_nodes = df_nodes[~df_nodes['country_iso'].isin(iso_codes_to_drop)]

df_edges = pd.read_csv(edges_input_file)

# calculate new exports: group by exporter_iso and summ all trade values
df_exports = df_edges.groupby('exporter_iso', as_index=False)['trade_value_usd'].sum()
# rename columns so we can cleanly merge them with the nodes dataframe
df_exports = df_exports.rename(columns={
    'exporter_iso': 'country_iso', 
    'trade_value_usd': 'new_total_export_usd'
})

# calculate new imports: group by importer_iso and sum all trade values
df_imports = df_edges.groupby('importer_iso', as_index=False)['trade_value_usd'].sum()
# rename columns so we can cleanly merge them with the nodes dataframe
df_imports = df_imports.rename(columns={
    'importer_iso': 'country_iso', 
    'trade_value_usd': 'new_total_import_usd'
})

# merge the newly calculated totals back into the main nodes dataframe
# we use how='left' to keep all countries in df_nodes, even if they have no trade in the edges file
df_nodes = df_nodes.merge(df_exports, on='country_iso', how='left')
df_nodes = df_nodes.merge(df_imports, on='country_iso', how='left')

# if a country had no exports or no imports, the merge will put NaN (Not a Number). 
# we need to fill those empty spaces with 0.
df_nodes['new_total_export_usd'] = df_nodes['new_total_export_usd'].fillna(0)
df_nodes['new_total_import_usd'] = df_nodes['new_total_import_usd'].fillna(0)

# overwrite the old columns with the new math
df_nodes['total_export_usd'] = df_nodes['new_total_export_usd']
df_nodes['total_import_usd'] = df_nodes['new_total_import_usd']
df_nodes['net_trade_balance_usd'] = df_nodes['total_export_usd'] - df_nodes['total_import_usd']

# clean up by dropping the temporary columns we created during the merge
df_nodes = df_nodes.drop(columns=['new_total_export_usd', 'new_total_import_usd'])

df_nodes.to_csv(output_nodes_file, index=False)

print(f"\n Successfully updated nodes trade values.")
print(f"Saved to {output_nodes_file}\n")