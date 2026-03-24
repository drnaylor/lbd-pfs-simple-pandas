"""
Calculates cheapest fuel station based on postcode, MPG and amount to fill by

Assumes that `postcode.parquet` and `fuel.parquet` exist.
"""

import argparse
import re
from typing import cast, NamedTuple, Optional

import pandas as pd
from haversine import haversine, Unit

class Arguments(NamedTuple):
    postcode: str
    fuel_type: str
    mpg: float
    litres: float


class Dataframes(NamedTuple):
    fuel: pd.DataFrame
    postcode: pd.DataFrame


class LatLong(NamedTuple):
    latitude: float
    longitude: float


VALID_FUEL_TYPES = ["E5", "E10", "B7S", "B7P", "B10", "HVO"]

def parse_args(to_parse: Optional[list[str]] = None) -> Arguments:
    """
    Uses argparse to parse the command line and does basic validation
    checks on the inputs.

    Returns:
        An Arguments named tuple with the passed in, cleaned, arguments
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("postcode", type=str)
    parser.add_argument("fuel_type", type=str)
    parser.add_argument("mpg", type=float)
    parser.add_argument("litres", type=float)

    args: argparse.Namespace = parser.parse_args(args = to_parse)

    fuel_type: str = args.fuel_type.strip().upper()
    if fuel_type not in VALID_FUEL_TYPES:
        raise ValueError(f"Fuel type must be one of {", ".join(VALID_FUEL_TYPES)}, but {args.fuel_type} was specified")
    
    # We check that the postcode is valid, but we also ensure that we put a space in if necessary
    postcode_arg: str = args.postcode.strip().upper()
    if " " not in postcode_arg:
        postcode_arg = " ".join([postcode_arg[:-3], postcode_arg[-3:]])

    if re.match(r"[A-Z]{1,2}\d{1,2} \d[A-Z]{2}", postcode_arg):
        return Arguments(postcode_arg, fuel_type, args.mpg, args.litres)
    else:
        raise ValueError(f"Postcode {args.postcode} is not in a valid format")


def read_files() -> Dataframes:
    """
    Reads the cleaned parquet files and returns a tuple of two data frames

    Returns:
        A Dataframes containing the dataframes
    """
    return Dataframes(fuel=pd.read_parquet("fuel.parquet"), postcode=pd.read_parquet("postcode.parquet"))


def filter_fuel_types(fuel_prices: pd.DataFrame, fuel_type: str) -> pd.DataFrame:
    """
    Removes any entry from the fuel prices dataframes that
    does not have a price for the given fuel type

    Parameters:
        fuel_prices: The fuel prices dataframe
        fuel_type: The fuel type that is being investigated

    Returns:
        A dataframe
    """
    return fuel_prices[fuel_prices[fuel_type].notna()]


def get_lat_long(postcode_df: pd.DataFrame, postcode: str) -> LatLong:
    """
    Gets the latitude and logitude associated with a postcode

    Parameters:
        postcode_df: The dataframe containing postcodes, latitudes and longitudes
        postcode: The postcode to get the lat/long for

    Returns:
        A LatLong with the latitude and longitude

    Raises:
        ValueError if the postcode does not exist in the postcode dataframe
    """
    # We need to reset the index as it isn't "row number", it's intended to be a static identifier
    # However, we can't easily mix "at" and "iat" later (for getting single values out), so it's easier to just do this.
    postcode_row: pd.DataFrame = postcode_df[postcode_df["postcode"] == postcode][["latitude", "longitude"]].head(1).reset_index()
    if postcode_row.empty:
        raise ValueError(f"Postcode {postcode} does not exist")

    # The following are floats.
    return LatLong(latitude=cast(float, postcode_row.at[0, "latitude"]), longitude=cast(float, postcode_row.at[0, "longitude"]))


def distance_in_km(latlong: pd.Series, home_latlong: LatLong) -> float:
    """
    A function to be passed to the pandas Series apply function.

    Parameters:
        latlong: A Pandas series that should contain two elements, latitude then longitude, in that order
    
    Returns:
        float: The haversine formula calculated distance between 
    """
    return haversine(latlong, home_latlong, unit=Unit.KILOMETERS)


def add_distance_based_columns(fuel_prices: pd.DataFrame, args: Arguments, home_latlong: LatLong) -> pd.DataFrame:
    """
    Adds columns that enable the calculation of the cheapest fuel prices

    Parameters:
        fuel_prices: The fuel prices dataframe
        args: The script's input arguments
        home_latlong: The LatLong containing the latitude and longitude to measure distances from

    Returns:
        A dataframe with distance, total_fuel_cost, total_cost_of_driving and full_cost columns added
    """
    fuel_prices["distance"] = fuel_prices[["latitude", "longitude"]].apply(distance_in_km, axis=1, home_latlong=home_latlong)
    fuel_prices["total_fuel_cost"] = fuel_prices[args.fuel_type] * float(args.litres)
    # (1 / mpg) * 2.825 * l * dist
    fuel_prices["total_cost_of_driving"] = 2.825 * fuel_prices["distance"] * fuel_prices[args.fuel_type] / float(args.mpg) 
    fuel_prices["full_cost"] = fuel_prices["total_fuel_cost"] + fuel_prices["total_cost_of_driving"]
    return fuel_prices


def display(fuel_prices: pd.DataFrame, fuel_type: str) -> None:
    """
    Creates a dataframe that displays the cheapest 10 forecourts by fuel_type and distance to travel

    Parameters:
        fuel_prices: A dataframe with fuel price and distance based data
        fuel_type: A string representing the type of fuel
    """
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