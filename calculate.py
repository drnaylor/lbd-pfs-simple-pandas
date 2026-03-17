"""
Calculates cheapest fuel station based on postcode, MPG and amount to fill by

Assumes that `postcode.parquet` and `fuel.parquet` exist.
"""

import argparse
from typing import cast, NamedTuple

import pandas as pd
from haversine import haversine, Unit


Arguments = NamedTuple("Arguments", [("postcode", str), ("fuel_type", str), ("mpg", float), ("litres", float)])

def parse_args() -> Arguments:
    parser = argparse.ArgumentParser()
    parser.add_argument("postcode", type=str)
    parser.add_argument("fuel_type", type=str)
    parser.add_argument("mpg", type=float)
    parser.add_argument("litres", type=float)

    args: argparse.Namespace = parser.parse_args()

    fuel_type: str = args.fuel_type.strip().upper()
    fuel_types = ["E5", "E10", "B7S", "B7P", "B10", "HVO"]
    if fuel_type not in fuel_types:
        raise ValueError(f"Fuel type must be one of {", ".join(fuel_types)}, but {fuel_type} was specified")
    
    # We check that the postcode is valid, but we also ensure that we put a space in if necessary
    postcode_arg: str = args.postcode.strip().upper()
    if " " not in postcode_arg:
        postcode_arg = " ".join([postcode_arg[:-3], postcode_arg[-3:]])

    return Arguments(postcode_arg, fuel_type, args.mpg, args.litres)

def read_files() -> tuple[pd.DataFrame, pd.DataFrame]:
    # get the data files into memory
    return (pd.read_parquet("fuel.parquet"), pd.read_parquet("postcode.parquet"))

def filter_fuel_types(fuel_prices: pd.DataFrame, fuel_type: str) -> pd.DataFrame:
    return fuel_prices[fuel_prices[fuel_type].notna()]

def get_lat_long(postcode_df: pd.DataFrame, postcode: str) -> tuple[float, float]:
    # We need to reset the index as it isn't "row number", it's intended to be a static identifier
    # However, we can't easily mix "at" and "iat" later (for getting single values out), so it's easier to just do this.
    postcode_row: pd.DataFrame = postcode_df[postcode_df["postcode"] == postcode][["latitude", "longitude"]].head(1).reset_index()
    if postcode_row.empty:
        raise ValueError(f"Postcode {postcode} does not exist")

    # The following are floats.
    return cast(tuple[float, float], (postcode_row.at[0, "latitude"], postcode_row.at[0, "longitude"]))

def distance_in_km(latlong: pd.Series, home_latlong: tuple[float, float]) -> float:
    """
    A function to be passed to the pandas Series apply function.

    Parameters:
        latlong: A Pandas series that should contain two elements, latitude then longitude, in that order
    
    Returns:
        float: The haversine formula calculated distance between 
    """
    return haversine(latlong, home_latlong, unit=Unit.KILOMETERS)


def add_distance_based_columns(fuel_prices: pd.DataFrame, args: Arguments, home_latlong: tuple[float, float]) -> pd.DataFrame:
    fuel_prices["distance"] = fuel_prices[["latitude", "longitude"]].apply(distance_in_km, axis=1, home_latlong=home_latlong)
    fuel_prices["total_fuel_cost"] = fuel_prices[args.fuel_type] * float(args.litres)
    fuel_prices["total_cost_of_driving"] = 282.5 * fuel_prices["distance"] / float(args.mpg) # cost in pence
    fuel_prices["full_cost"] = fuel_prices["total_fuel_cost"] + fuel_prices["total_cost_of_driving"]
    return fuel_prices


def display(fuel_prices: pd.DataFrame, fuel_type: str) -> None:
    display_frame = fuel_prices[["brand_name", "trading_name", "postcode", fuel_type, "distance", "total_fuel_cost", "total_cost_of_driving", "full_cost"]].sort_values(by="full_cost", ascending=True).rename(
        columns={
            "brand_name": "Brand Name",
            "trading_name": "Trading Name",
            "postcode": "Postcode",
            "distance": "Distance to forecourt (km)",
            fuel_type: "Price per litre (pence)",
            "total_fuel_cost": "Total cost of fuel (pence)",
            "total_cost_of_driving": "Straight line driving cost (pence)",
            "full_cost": "Total cost (pence)"
        }
    )

    print("Cheapest 10 forecourts")
    print("-----")
    print(display_frame.head(10).to_string(index=False))


if __name__ == "__main__":
    args = parse_args()
    fuel_df, postcode_df = read_files()
    fuel_df = filter_fuel_types(fuel_df, args.fuel_type)
    home_latlong = get_lat_long(postcode_df, args.postcode)
    fuel_df = add_distance_based_columns(fuel_df, args, home_latlong)
    display(fuel_df, args.fuel_type)