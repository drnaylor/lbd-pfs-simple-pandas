from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, strategies as st

from prepare import remove_qa_entries, parse_datetime, clean_prices, clean_fuel_postcodes

from .utils import Postcode, postcode

def test_removal_of_qa_entries():
    input_df = pd.DataFrame.from_dict(
        {
            "forecourts.trading_name": [
                "prod",
                "prod",
                "prod",
                "prod",
                "prod",
                "prod-new",
                "preprod",
                "supermarket-preprod",
                "SuperMarket-PreProd"
            ],
            "forecourts.brand_name": [
                "prod",
                None,
                "pre-prod",
                "services-pre-prod-1",
                "services-pre-pRod-1",
                "prod",
                "prod",
                "prod",
                "prod",
            ]
        }
    )

    expected_df = pd.DataFrame.from_dict(
                {
            "forecourts.trading_name": [
                "prod"
            ],
            "forecourts.brand_name": [
                "prod",
            ]
        }
    )

    sut = remove_qa_entries(input_df)
    assert sut.equals(expected_df)


GMT_TIMEZONE = ZoneInfo("Europe/London")

@given(st.datetimes(min_value=datetime(2025, 1, 1, 0, 0, 0), max_value=datetime(2027, 12, 31, 23, 59, 59)))
def test_parse_datetime(date: datetime):
    # format the date in a way we're expecting it to be formatted.
    # we also don't want the microsecond
    tz_aware_time = date.replace(microsecond=0, tzinfo=GMT_TIMEZONE)
    date_string = tz_aware_time.strftime("%b %d %Y %H:%M:%S GMT%z")
    result = parse_datetime(date_string)
    assert result is not None
    assert result == tz_aware_time.astimezone(timezone.utc)


@given(st.text(max_size=200))
def test_parse_datetime_returns_none_when_invalid_datetime_strings_are_provided(s):
    assert parse_datetime(s) is None


@given(
    st.lists(
        st.tuples(
            st.datetimes(min_value=datetime.now() - timedelta(weeks=3), max_value=datetime.now()),
            st.floats(min_value=0.1, max_value=10000.0, allow_nan=False, allow_infinity=False, allow_subnormal=False).map(lambda x: round(x, 1))
        ),
        min_size=10,
        max_size=100
    )
)
def test_clean_prices_returns_values_in_range(input: list[tuple[datetime, float]]):
    """
    Tests that the clean prices function returns results in the expected range.

    Note that this test DOES NOT test each specific value is correct, but that the data frame
    that is returned conforms to the overall specification. In this case, what we check is:

    * any entry over 2 weeks old returns NaN and so won't be counted in these calculations
    * all prices are within the range 25p and 999.99p (i.e. reasonable transfromations have
      taken place)

    This allows us to ensure that the data is in the right form, though it doesn't check all of
    the values are transformed correctly.
    """
    # because hypothesis doesn't like timezone aware datetimes, we need to set it here
    input = list(
        map(lambda tup: (tup[0].replace(tzinfo=timezone.utc), tup[1]), input)
    )
    input_df = pd.DataFrame(
        map(lambda x: (x[0].strftime("%a %b %d %Y %H:%M:%S GMT+0000"), x[1]), input), 
        columns=["forecourts.price_submission_timestamp.E10", "forecourts.fuel_price.E10"]
    )
    output_series: pd.Series = clean_prices(input_df, "E10")

    # get the number of input entries that were set within the last two weeks.
    expected_valid_prices = len(list(filter(lambda x: (x[0] > datetime.now(tz=timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(weeks=2)) and (x[1] >= 0.5), input)))

    assert output_series.dropna().count() == expected_valid_prices, f"Expected number of prices {expected_valid_prices} does not match output series count {output_series.count()}"
    
    # There is potential for prices to be low for HVO, so 25p is the benchmark we use for that.
    # TODO: is this really reasonable?
    assert output_series.dropna().between(25.0, 999.99).all()


@given(st.lists(st.floats(min_value=0.001, max_value=0.4999), min_size=1, max_size=100))
def test_clean_prices_specific_values_nan(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.isna().all(), "Some entries are not NaN"


@given(st.lists(st.floats(min_value=0.5, max_value=2.49999), min_size=1, max_size=100))
def test_clean_prices_specific_values_to_2_50(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.equals(input_df["forecourts.fuel_price.E10"] * 100.0)


@given(st.lists(st.floats(min_value=2.5, max_value=49.9999), min_size=1, max_size=100))
def test_clean_prices_specific_values_to_50_00(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.equals(input_df["forecourts.fuel_price.E10"] * 10.0)


@given(st.lists(st.floats(min_value=50.0, max_value=500.0), min_size=1, max_size=100))
def test_clean_prices_specific_values_to_500_00(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.equals(input_df["forecourts.fuel_price.E10"])


@given(st.lists(st.floats(min_value=500.0001, max_value=1000.0), min_size=1, max_size=100))
def test_clean_prices_specific_values_to_1000_00(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.equals(input_df["forecourts.fuel_price.E10"] / 10.0)


@given(st.lists(st.floats(min_value=1000.0001, max_value=9999.99), min_size=1, max_size=100))
def test_clean_prices_specific_values_to_10000_00(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.equals(input_df["forecourts.fuel_price.E10"] / 10.0)


@given(st.lists(st.floats(min_value=10000.0001, max_value=99999.99), min_size=1, max_size=100))
def test_clean_prices_specific_values_to_100000_00(input_value):
    input_df = pd.DataFrame(
        [{ 
            "forecourts.price_submission_timestamp.E10":  datetime.now(tz=timezone.utc).strftime("%a %b %d %Y %H:%M:%S GMT+0000"), 
            "forecourts.fuel_price.E10": x
        } for x in input_value]
    )

    output_series = clean_prices(input_df, "E10")
    assert output_series.equals(input_df["forecourts.fuel_price.E10"] / 100.0)



@given(st.lists(postcode(), min_size=1, max_size=1000))
def test_clean_fuel_postcodes(postcodes: list[Postcode]):
    input_df = pd.DataFrame(
        {
            "forecourts.location.postcode": [x.input for x in postcodes]
        }
    )

    d = {
           "forecourts.location.postcode": [x.input for x in postcodes],
           "postcode": [x.output for x in postcodes]
        }

    expected_df = pd.DataFrame(d)

    output_df = clean_fuel_postcodes(input_df)
    assert output_df.equals(expected_df)
 