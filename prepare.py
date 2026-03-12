"""
Prepares the provided CSV file and creates a SQLite database that fuel data queries
can be performed from
"""

import argparse
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

import pandas as pd
import numpy as np

parser = argparse.ArgumentParser("PFS Data Preparation")

parser.add_argument("fuel_data", type=str, help="The fuel CSV file to ingest")
parser.add_argument("postcode_data", type=str, help="The postcode CSV file to ingest")

args = parser.parse_args()

fuel_dataframe: pd.DataFrame = pd.read_csv(args.fuel_data, header=0)
postcode_dataframe: pd.DataFrame = pd.read_csv(args.postcode_data, header=0)

# Clean up for the fuel dataframe

# We start with conditions where QA/Test entries are in there. Using logical
# ORs (basically from numpy), we create a series of True/False entries, which
# we then use to filter out these results.
#
# Note that we return `True` if the result IS a QA entry, so we'll negate that
# to filter them out later on.
qa_results = (
    fuel_dataframe["forecourts.trading_name"].str.contains("preprod", case=False) | 
    fuel_dataframe["forecourts.trading_name"].str.contains("-new", case=False) |
    fuel_dataframe["forecourts.brand_name"].isnull() |
    fuel_dataframe["forecourts.brand_name"].str.contains("pre-prod", case=False)
)

# This contains the dataframe without QA entries
fuel_dataframe = fuel_dataframe[~qa_results]

def parse_datetime(input: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(input, "%b %d %Y %H:%M:%S GMT%z").astimezone(timezone.utc)
    except:
        return None

def clean_prices(dataframe: pd.DataFrame, fuel_type: str) -> pd.Series:
    # get the dates series, make sure they're all within the last two weeks
    # Date stamp format: Sat Mar 07 2026 15:19:14 GMT+0000 (Coordinated Universal Time)
    date_series = (
        dataframe[f"forecourts.price_submission_timestamp.{fuel_type}"]
            .str
            .extract(r"^[A-Za-z]{3} ([A-Za-z]{3} \d{2} \d{4} \d{2}:\d{2}:\d{2} GMT\+\d{4}).*$", expand=False)
            .rename(fuel_type)
            .apply(parse_datetime)
            # This treats the Not a Time values as False, which we want here
            # as we have timezone aware data, we need to make sure we are timezone aware here.
            .between(datetime.now(tz=timezone.utc) - timedelta(weeks = 2), datetime.now(tz=timezone.utc)) 
    )

    fuel_series = dataframe[f"forecourts.fuel_price.{fuel_type}"]

    # remove anything that is less than 0.5, then apply transformations
    # based on other value thresholds. First wins.
    return fuel_series.case_when(
        caselist=[
            (~date_series, np.nan), # nothing that's too old -- if the date series entry is false then we want to return not a number (basically Null)
            (fuel_series < 0.5, np.nan), # discard
            (fuel_series < 2.50, fuel_series * 100.0), # We have pounds, we want pence.
            (fuel_series < 50.0, fuel_series * 10.0), # Dimes is submitting something weird, so we correct that best we can
            (fuel_series > 1000.0, fuel_series / np.ceil(np.log10(fuel_series) - 3)), # We expect a number that is three whole digits, so we take it down this way
            (fuel_series > 500.0, fuel_series / 10.0)
        ]
    )


fuel_dataframe["E5"] = clean_prices(fuel_dataframe, "E5")
fuel_dataframe["E10"] = clean_prices(fuel_dataframe, "E10")
fuel_dataframe["B7S"] = clean_prices(fuel_dataframe, "B7S")
fuel_dataframe["B7P"] = clean_prices(fuel_dataframe, "B7P")
fuel_dataframe["B10"] = clean_prices(fuel_dataframe, "B10")
fuel_dataframe["HVO"] = clean_prices(fuel_dataframe, "HVO")

# now, we need to link this to the postcode data
# for this, I've used data from https://www.freemaptools.com/download-uk-postcode-lat-lng.htm
# but before that, the postcodes in the petrol CSV files aren't all that good either, so we do a quick patch up

pfs_postcode_series = fuel_dataframe["forecourts.location.postcode"].str.strip() 
fuel_dataframe["postcode"] = pfs_postcode_series.case_when(
    [
        # if no space is present, add a space. Otherwise, leave it as is
        (
            ~pfs_postcode_series.str.contains(" "), 
            pfs_postcode_series.str.slice(stop=-3).str.cat(pfs_postcode_series.str.slice(start=-3), sep=" ")
        )
    ]
)

# Before we merge with the postcode dataframe, we're going to only take the columns we want out of this
fuel_dataframe = fuel_dataframe.rename(columns={
    "forecourts.trading_name": "trading_name",
    "forecourts.brand_name": "brand_name"
})[["brand_name", "trading_name", "postcode", "E5", "E10", "B7S", "B7P", "B10", "HVO"]]

# Merge on the postcode column, which gives us latitude, and drop the ID column from the right
final_dataframe = pd.merge(
    fuel_dataframe, 
    postcode_dataframe,
    how="inner",
    on="postcode"
)[['brand_name', 'trading_name', 'postcode', 'E5', 'E10', 'B7S', 'B7P', 'B10', 'HVO', 'latitude', 'longitude']]

with open("fuel.parquet", mode="wb") as fuel_file:
    # We do it this way to ensure the file can be overwritten
    fuel_file.write(final_dataframe.to_parquet(path=None, index=False))

with open("postcode.parquet", mode="wb") as postcode_file:
    # axis 1 is columns, axis 0 is rows (and the default) -- drop is usually used to drop
    # specific rows by index
    postcode_file.write(postcode_dataframe.drop("id", axis=1).to_parquet(path=None, index=False))

print("Data preparation complete.")