
# Forked from West Reservoir 
#%%
import sys
from datetime import datetime
import meteostat as ms
from meteostat import Point, daily, hourly
import matplotlib.pyplot as plt
import pandas as pd

#%%

# Set time period
start = datetime(2010, 1, 1)
end = datetime.today()

sDirBase = "/home/jeremy/projects/pond/meteo-data/"

# location = Point(49.2497, -123.1193, 70)
#location = Point(51.4545, 2.5879) # west Reservoir 
#location = Point(51.504829, -0.169077) # Serpentine
location = Point(51.563333, -0.156752) # Men's pond
stations = ms.stations.nearby(location, limit=4)


#%%
stations = ms.stations.nearby(location, radius=50000, limit=20)

fig, ax = plt.subplots(figsize=(8, 8))
ax.scatter(location.longitude, location.latitude, c="red", s=120, marker="*", label="Location")
ax.scatter(stations["longitude"], stations["latitude"], c="blue", s=40, label="Nearby stations")

for _, row in stations.iterrows():
    ax.annotate(row["name"], (row["longitude"], row["latitude"]), xytext=(5, 5), textcoords="offset points", fontsize=8)

ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.set_title("Location and nearby Meteostat stations")
ax.legend()
ax.grid(True, alpha=0.3)
plt.show()

#%%
# Fetch daily data from Meteostat
tsHist = daily(stations, start, end)
dfData = ms.interpolate(tsHist, location).fetch()
dfData = tsHist.fetch()
#%%
type(dfData)
type(tsHist)
#%%

#%%

with open(sDirBase + "dfWeather_daily.pkl", "wb") as f:
    dfData.to_pickle(f)

#%%

# Load the data from the daily pickle file
with open(sDirBase + "dfWeather_daily.pkl", "rb") as f:
    dfW = pd.read_pickle(f)

#%%

type(dfW)

#%%
dfW.head()
#%%
dfW["2010":].plot(kind="line", y="tmin", title="Daily Temperature (°C)", figsize=(12, 6))
#%%

# Fetch hourly data
dfWH = hourly(location, datetime(2025, 1, 1), end)
#%%
dfWH = dfWH.fetch()
#%%
with open(f"{sDirBase}/dfWh-menspond-2025-08.pkl", "wb") as f:
    dfWH.to_pickle(f)
#%%
dfWH["2025-08":]
# %%

with open(f"{sDirBase}/dfWeather_hourly_2025.pkl", "rb") as f:
    dfWH = pd.read_pickle(f)
