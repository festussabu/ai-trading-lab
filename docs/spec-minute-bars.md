Goal: download 1-minute price bars for SPY for one trading day
from Alpaca's paper API (IEX feed) and save them to data/bars/SPY_<date>.csv.

- Use the alpaca-py library. Read keys from environment variables.
- One function to fetch, one to save. Record the data source in the file.
- Clear error if keys are missing or the API fails.
- Out of scope: other tickers, live streaming, trading, AWS.
