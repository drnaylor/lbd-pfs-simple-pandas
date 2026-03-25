import string
from typing import TypeVar, NamedTuple, Optional

from hypothesis import given, strategies as st, settings, HealthCheck
import pandas as pd
import pytest

from calculate import Arguments, parse_args, VALID_FUEL_TYPES, filter_fuel_types, LatLong, get_lat_long, add_distance_based_columns

from .utils import Postcode, postcode

E = TypeVar("E", bound=BaseException, default=BaseException)

@given(
        postcode(),
        st.sampled_from(['E5', 'E10', 'B7S', 'B7P', 'B10', 'HVO', 'e5', 'e10', 'b7s', 'b7p', 'b10', 'hvo']), 
        st.floats(min_value=0.0, max_value=10000.0), 
        st.floats(min_value=0.0, max_value=10000.0)
)
def test_valid_parse_args(postcode: Postcode, fuel_type: str, mpg: float, litres: float):
    input_postcode, output_postcode = postcode
    # given the provided arguments in the right order
    # when we parse them
    sut = parse_args([input_postcode, fuel_type, str(mpg), str(litres)])
    # then ensure the arguments object contains the results
    assert Arguments(output_postcode, fuel_type.strip().upper(), mpg, litres) == sut


def filter_postcode(input: str):
    i = input.strip()
    return len(i) > 3 and i[-3] not in string.digits

@given(
        st.text(alphabet=string.ascii_letters + string.digits + " ", min_size=4, max_size=8).filter(filter_postcode),
        st.sampled_from(['E5', 'E10', 'B7S', 'B7P', 'B10', 'HVO', 'e5', 'e10', 'b7s', 'b7p', 'b10', 'hvo']), 
        st.floats(min_value=0.0, max_value=10000.0), 
        st.floats(min_value=0.0, max_value=10000.0)
)
def test_invalid_postcode_raises_valuerror(postcode, fuel_type, mpg, litres):
    with pytest.raises(ValueError) as ex:
        parse_args([postcode, fuel_type, str(mpg), str(litres)])
    
    assert str(ex.value) == f"Postcode {postcode} is not in a valid format"


@given(
        postcode().map(lambda x: x.input),
        st.text(alphabet=string.ascii_letters + string.digits, min_size=2, max_size=3).filter(lambda x: x.upper() not in ['E5', 'E10', 'B7S', 'B7P', 'B10', 'HVO']), 
        st.floats(min_value=0.0, max_value=10000.0), 
        st.floats(min_value=0.0, max_value=10000.0)
)
def test_invalid_fueltype_raises_valuerror(postcode, fuel_type, mpg, litres):
    with pytest.raises(ValueError) as ex:
        parse_args([postcode, fuel_type, str(mpg), str(litres)])

    assert str(ex.value) == f"Fuel type must be one of {", ".join(['E5', 'E10', 'B7S', 'B7P', 'B10', 'HVO'])}, but {fuel_type} was specified"

@st.composite
def create_fuel_data_frame(draw) -> dict[str, Optional[float]]:
    return {
        ft: draw(st.one_of(st.none(), st.floats(min_value=1.0, max_value=9999.99))) for ft in VALID_FUEL_TYPES
    }

@pytest.fixture(scope="function")
def fuel_df():
    from random import randint, randrange

    # generates a set of dictionaries to add to a dataframe
    records = [
        {
            ft: None if randint(0, 4) == 0 else float(randrange(100, 20099)) / 100.0 for ft in VALID_FUEL_TYPES
        }
        for _ in range(10000)
    ]

    return pd.DataFrame.from_records(records)


@pytest.mark.parametrize(argnames="fuel_type", argvalues=VALID_FUEL_TYPES)
def test_filter_fuel_types_returns_appropriate_rows(fuel_df, fuel_type):
    # Given the fuel dataframe
    # When we filter it
    sut = filter_fuel_types(fuel_df, fuel_type)
    # Then make sure the appropriate column does not have any Nones (which are NaNs in the dataframe)
    assert not sut[fuel_type].hasnans


@pytest.fixture
def postcode_sample() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "postcode": ["AB1 2CD", "AB2 2CD", "AB3 2CD", "AB45 2CD", "BA6 2CD"],
            "latitude": [0, 1, 2, 3, 4],
            "longitude": [4, 3, 2, 1, 0]
        }
    )

@pytest.mark.parametrize("postcode, output", 
                          [["AB1 2CD", LatLong(0, 4)], 
                           ["AB2 2CD", LatLong(1, 3)], 
                           ["AB3 2CD", LatLong(2, 2)],
                           ["AB45 2CD", LatLong(3, 1)],
                           ["BA6 2CD", LatLong(4, 0)]]) 
def test_get_lat_long(postcode_sample, postcode, output):
    sut = get_lat_long(postcode_sample, postcode)
    assert sut == output


@given(postcode=st.text(alphabet=string.ascii_letters + string.digits, max_size=8))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture]) # We don't need the fixture to change, so this is fine
def test_get_lat_long_throws_when_postcode_does_not_exist(postcode_sample, postcode):
    with pytest.raises(ValueError) as exc:
        get_lat_long(postcode_sample, postcode)

    assert str(exc.value) == f"Postcode {postcode} does not exist"


def test_add_distance_based_columns_returns_additional_columns():
    input_df = pd.DataFrame.from_records(
        [
            {"latitude": 0.0, "longitude": 0.0, "E5": 0.0, "E10": 129.9},
            {"latitude": 1.0, "longitude": 0.0, "E5": 0.0, "E10": 130.9},
            {"latitude": 1.0, "longitude": 1.0, "E5": 0.0, "E10": 131.9},
            {"latitude": -1.0, "longitude": 1.0, "E5": 0.0, "E10": 132.9}
        ]
    )

    expected_df = pd.DataFrame.from_records(
        [
            {"latitude": 0.0, "longitude": 0.0, "E5": 0.0, "E10": 129.9, "distance": 0.0, "total_fuel_cost": 1299.0, "total_cost_of_driving": 0.0, "full_cost": 1299.0},
            {"latitude": 1.0, "longitude": 0.0, "E5": 0.0, "E10": 130.9, "distance": 111.2, "total_fuel_cost": 1309.0, "total_cost_of_driving": 914.0, "full_cost": 2223.0},
            {"latitude": 1.0, "longitude": 1.0, "E5": 0.0, "E10": 131.9, "distance": 157.25, "total_fuel_cost": 1319.0, "total_cost_of_driving": 1302.0, "full_cost": 2621.0},
            {"latitude": -1.0, "longitude": 1.0, "E5": 0.0, "E10": 132.9, "distance": 157.25, "total_fuel_cost": 1329.0, "total_cost_of_driving": 1312.0, "full_cost": 2641.0}
        ]
    )

    args = Arguments(
        postcode="a",
        fuel_type="E10",
        mpg=45, # 1 km/l
        litres=10
    )
    result_df = add_distance_based_columns(input_df, args, LatLong(0.0, 0.0))
    # to accounr for floating point number arithmetic, we round the result df columns
    result_df["distance"] = result_df["distance"].round(2)
    result_df["total_fuel_cost"] = result_df["total_fuel_cost"].round(0)
    result_df["total_cost_of_driving"] = result_df["total_cost_of_driving"].round(0)
    result_df["full_cost"] = result_df["full_cost"].round(0)

    assert expected_df.equals(result_df)

    