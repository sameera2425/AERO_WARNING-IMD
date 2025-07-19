import pandas as pd
import re

# Read warnings
ad_warn_df = pd.read_csv('AD_warn_DF.csv', dtype={'Issue date/time': str})

# Read extracted METAR features
with open('metar_extracted_features.txt', 'r') as f:
    metar_blocks = f.read().split('\nRow ')[1:]  # Split by each row block
    metar_blocks = ['Row ' + block for block in metar_blocks]

# Compile regex for TS/TSRA variants
TSRA_REGEX = re.compile(r'(TSRA|TS|FBL TSRA|MOD TSRA|HVY TSRA|MOD TS|FBL TS|HVY TS)', re.IGNORECASE)

results = []

for idx, row in ad_warn_df.iterrows():
    sl_no = idx + 1
    sig_wx = str(row.get('Significant Wx', ''))
    gust_val = str(row.get('Gust', ''))
    wind_dir_fcst = row.get('Wind dir (deg)', None)
    issue_time = str(row.get('Issue date/time', '')).zfill(6)
    true_false = 0
    remark = ''

    # Check for TS/TSRA and gust in warning
    has_tsra = bool(TSRA_REGEX.search(sig_wx))
    has_gust = bool(re.match(r'\d{2,3}KT', gust_val))

    # Find corresponding METAR block
    metar_block = next((b for b in metar_blocks if f'Row {sl_no}:' in b), None)
    metar_lines = metar_block.split('\n') if metar_block else []

    # If the block says FCST/OBS is OBS, skipping extraction
    if metar_block and 'FCST/OBS is OBS, skipping extraction.' in metar_block:
        true_false = 1
        # Elements logic for OBS rows (just reflect the warning forecast)
        if has_gust and has_tsra:
            elements = 'Gust & Thunderstorm warning'
        elif has_gust:
            elements = 'Gust warning'
        elif has_tsra:
            elements = 'Thunderstorm warning'
        else:
            elements = ''
        remark = 'OBS'
        results.append([sl_no, elements, issue_time, true_false, remark])
        continue

    found_gust = False
    found_dir = False
    found_cb = False
    gust_reported = ''
    dir_reported = ''
    cb_reported = ''
    tsra_reported = ''
    cb_cloud_group = ''

    for line in metar_lines:
        # Gust
        gust_match = re.search(r'Gust: (\d+)', line)
        if gust_match:
            metar_gust = int(gust_match.group(1))
            # Wind Dir
            dir_match = re.search(r'Wind Dir: (\d+)', line)
            if dir_match and wind_dir_fcst:
                metar_dir = int(dir_match.group(1))
                try:
                    fcst_dir = int(wind_dir_fcst)
                    if abs(metar_dir - fcst_dir) <= 30:
                        found_gust = True
                        found_dir = True
                        gust_reported = f'{metar_gust}KT'
                        dir_reported = f'{metar_dir}'
                except Exception:
                    pass
        # CB cloud detection from Clouds list
        clouds_match = re.search(r"Clouds: \[(.*?)\]", line)
        if clouds_match:
            clouds_list = [c.strip().strip("'") for c in clouds_match.group(1).split(',')]
            cb_groups = [c for c in clouds_list if 'CB' in c]
            if cb_groups:
                found_cb = True
                cb_reported = 'CB'
                cb_cloud_group = cb_groups[0]  # Take the first CB group found
        # TSRA
        if re.search(r'TSRA', line):
            tsra_reported = 'TSRA'

    # Elements logic for FCST rows (based on METAR evidence)
    elements = ''
    if found_gust and found_cb:
        elements = 'Gust & Thunderstorm warning'
    elif found_gust:
        elements = 'Gust warning'
    elif found_cb:
        elements = 'Thunderstorm warning'

    # If elements is still empty, use the original warning type from ad_warn_df
    if not elements:
        if has_gust and has_tsra:
            elements = 'Gust & Thunderstorm warning'
        elif has_gust:
            elements = 'Gust warning'
        elif has_tsra:
            elements = 'Thunderstorm warning'

    # Logic for true/false and remarks (unchanged)
    if has_gust and not has_tsra:
        if found_gust and found_dir:
            true_false = 1
            remark = f'Gust {gust_reported} Dir {dir_reported} matched'
            if cb_cloud_group:
                remark += f' {cb_cloud_group} found'
        else:
            remark = 'No gust/direction mismatch'
    elif has_gust and has_tsra:
        if found_gust and found_dir:
            true_false = 1
            remark = f'Gust {gust_reported} Dir {dir_reported} matched'
            if cb_cloud_group:
                remark += f' {cb_cloud_group} found'
        elif found_cb:
            true_false = 1
            remark = ''
            if cb_cloud_group:
                remark += f' {cb_cloud_group} found'
        else:
            remark = 'Missing CB or direction mismatch'
    elif has_tsra:
        if found_cb:
            true_false = 1
            remark = ''
            if cb_cloud_group:
                remark += f' {cb_cloud_group} found'
        else:
            remark = 'Missing CB or direction mismatch'
    else:
        remark = 'No significant weather matched'

    results.append([sl_no, elements, issue_time, true_false, remark])

# Output report
final_df = pd.DataFrame(results, columns=[
    'Sl. No.',
    'Elements (Thunderstorm/Surface wind & Gust)',
    'Warning issue Time',
    'true-1 / false-0',
    'Remarks'
])
final_df.to_csv('final_warning_report.csv', index=False)
print('Report saved as final_warning_report.csv')

# Calculate percentage correct
try:
    total = len(final_df)
    correct = final_df['true-1 / false-0'].sum()
    if total > 0:
        percent = (correct / total) * 100
        print(f'Aerodrome Warning : {percent:.0f} % accurate')
    else:
        print('No warnings to evaluate.')
except Exception as e:
    print('Could not calculate accuracy:', e) 