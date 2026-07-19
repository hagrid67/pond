# Scratch script for interactive use only.
#%%
import sys
import pandas as pd
#sys.path.insert(0, '/home/jeremy/projects/pond')

from pond.metoffice import load_latest_data

#%%
# Load the latest weather data
dfW = load_latest_data()

# Display the dataframe
dfW2 = dfW[["screenTemperature", "uvIndex"]]
dfW2.columns=["Temp (°C)", "UV"]
pd.options.display.float_format = '{:.1f}'.format
print(dfW2)

