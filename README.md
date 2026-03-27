# Opencast Learn by Doing March 2026: Fuel Finder

This is a fairly simple data preparation and querying tool for the March 2026 Learn by Doing challenge for Opencast.

If you want to see a more Data Engineering-like solution, see https://github.com/drnaylor/databricks-lbd-fuel-prices which uses Databricks Free Edition.

## Requirements

You can simply install `uv` which will handle all dependencies, including Python itself, for you. See https://docs.astral.sh/uv/getting-started/installation/ for how to install it.

This solution uses the following software and packages:

* Python 3.14+ (it'll probably work on earlier versions but that's the version installed on my Mac!)
* pandas 3.0.1
* numpy 2.4.3
* haversine 2.9
* pyarrow 23

## Running this solution

You'll need to get two pieces of data:

* the latest fuel finder CSV file, from https://www.developer.fuel-finder.service.gov.uk/access-latest-fuelprices
* full UK postcode data that includes latitude and longitude, e.g. https://www.freemaptools.com/download-uk-postcode-lat-lng.htm (other sources exist!)

Place them in this directory. You may want to rename them for simplicity.

Once you've done that, there are two scripts to run, the one-time `prepare` script and the `calculate` script.

Perhaps unsurprisingly, we start with the `prepare` script. which is run as follows:

```bash
uv run ./prepare.py <fuel finder csv filename> <postcode_csv_filename>
```

This will create two parquet files in this directory, containing the cleaned data. You can now run the calculate script to find the cheapest forecourts given:

* the postcode you're travelling from (e.g. "NE6 2HL")
* the fuel type the vehicle takes (E5, E10, B7S, B7P, B10 or HVO)
* the fuel consumption rate of the vehicle, in miles per gallon
* the amount of fuel required, in litres

Run the calculation using:

```bash
uv run ./calculate.py "<postcode travelling from>" <fuel_type> <mpg> <litres>
```

So, for a car that takes E10, travelling from Opencast HQ at NE6 2HL, with an average mpg of 35 and looking to fill the tank with 45 litres,  you would run:

```bash
uv run ./calculate.py "NE6 2HL" E10 35 45
```

which will return a pandas dataframe sorted with the 10 cheapest stations, based on the straight line distance to the station, e.g.:

```
      Brand Name                                 Trading Name Postcode  Price per litre (pence)  Distance to forecourt (km)  Total cost of fuel (pence)  Straight line driving cost (pence)  Total cost (pence)
COSTCO WHOLESALE                   COSTCO WHOLESALE GATESHEAD NE11 9DH                    130.9                    5.090913                      5890.5                           41.090944         5931.590944
            ESSO                                  MFG SWALLOW  NE8 4BL                    131.9                    1.934572                      5935.5                           15.614763         5951.114763
     SAINSBURY'S                  SAINSBURYS HEATON NEWCASTLE  NE7 7JW                    132.9                    3.002806                      5980.5                           24.236935         6004.736935
            ESSO                             RONTEC TOWN HALL NE33 5QX                    132.9                    9.930768                      5980.5                           80.155484         6060.655484
       MORRISONS                   MFG MORRISONS KILLINGWORTH NE12 6YT                    133.9                    7.447002                      6025.5                           60.107946         6085.607946
           TESCO NORTH SHIELDS EXTRA - PETROL FILLING STATION NE29 7UJ                    133.9                    7.712091                      6025.5                           62.247596         6087.747596
            GULF                     RIDGEWAY SERVICE STATION NE34 8AQ                    133.9                   10.698568                      6025.5                           86.352723         6111.852723
     SAINSBURY'S                  SAINSBURYS SUNDERLAND NORTH  SR5 3JG                    133.9                   11.828512                      6025.5                           95.472993         6120.972993
              BP                                 RONTEC BYKER  NE6 1JN                    135.9                    0.814725                      6115.5                            6.575996         6122.075996
       MORRISONS     MFG MORRISONS NEWCASTLE UPON TYNE  BYKER  NE6 1EJ                    135.9                    0.819110                      6115.5                            6.611386         6122.111386
```