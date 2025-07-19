import requests
from urllib.parse import quote
from app.config import UPPER_AIR_DATA_DIR 
import os
from werkzeug.utils import secure_filename


def fetch_upper_air_data(datetime_str: str, station_id: str, src: str = 'UNKNOWN', data_type: str = 'TEXT:CSV') -> str:
    """
    Fetch upper air sounding data from University of Wyoming's weather site.

    Args:
        datetime_str (str): DateTime in format "YYYY-MM-DD HH:MM:SS"
        station_id (str): 5-digit WMO station ID (e.g. "43003")
        src (str): Source (default is 'UNKNOWN')
        data_type (str): Format type (default is 'TEXT:CSV')

    Returns:
        str: Raw upper air data as plain text

    Raises:
        Exception: If data not available or fetch fails
    """
    base_url = "https://weather.uwyo.edu/wsgi/sounding"
    datetime_encoded = quote(datetime_str)
    full_url = f"{base_url}?datetime={datetime_encoded}&id={station_id}&src={src}&type={data_type}"

    print(f"[DEBUG] Called fetch_upper_air_data with datetime_str={datetime_str}, station_id={station_id}")
    print(f"[DEBUG] Fetching from URL: {full_url}")
    response = requests.get(full_url)

    print(f"[DEBUG] Response status: {response.status_code}")
    print(f"[DEBUG] Response first 100 chars: {response.text[:100]}")

    if response.status_code == 200:
        if '<html>' in response.text.lower():
            raise Exception("HTML page received: likely no data available for this datetime/station.")
        # Save to file
        download_dir = os.path.join(UPPER_AIR_DATA_DIR, 'downloads')
        os.makedirs(download_dir, exist_ok=True)
        dt = datetime_str.replace(":", "").replace("-", "").replace(" ", "_")
        filename = secure_filename(f"upper_air_{station_id}_{dt}.csv")
        file_path = os.path.join(download_dir, filename)
        print(f"[DEBUG] Saving to: {file_path}")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"[INFO] Data saved to {file_path}")
        return file_path
    else:
        raise Exception(f"Failed to fetch data. HTTP Status Code: {response.status_code}")
    
import pandas as pd
def interpolate_temperature_only(actual_df, forecast_df):
    results = []

    for _, forecast_row in forecast_df.iterrows():
        forecast_alt = forecast_row["Altitude (m)"]

        # Get two actual levels above and below
        below = actual_df[actual_df["geopotential height_m"] <= forecast_alt]
        above = actual_df[actual_df["geopotential height_m"] >= forecast_alt]

        if below.empty or above.empty:
            continue  # Skip if interpolation not possible

        lower = below.iloc[-1]
        upper = above.iloc[0]

        h1, h2 = lower["geopotential height_m"], upper["geopotential height_m"]
        print(f"[DEBUG] Lower level: {h1} m, Upper level: {h2} m for forecast altitude {forecast_alt} m")
        t1, t2 = lower["temperature_C"], upper["temperature_C"]

        # Interpolate temperature
        interp_temp = ((h2 - forecast_alt) * t1 + (forecast_alt - h1) * t2) / (h2 - h1)
        print(f"[DEBUG] Interpolated temperature at {forecast_alt} m: {interp_temp:.2f} C")

        # For other parameters, take the closer one (nearest actual level)
        if abs(h1 - forecast_alt) <= abs(h2 - forecast_alt):
            nearest_row = lower
        else:
            nearest_row = upper

        results.append({
            **forecast_row.to_dict(),
            "interp_temperature_C": interp_temp,
            "actual_wind_speed_m/s": nearest_row["wind speed_m/s"],
            "actual_wind_direction": nearest_row.get("wind direction_degree")
        })

    return pd.DataFrame(results)
