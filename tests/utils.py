from hypothesis import strategies as st
from typing import NamedTuple

import string

class Postcode(NamedTuple):
    input: str
    output: str

@st.composite
def postcode(draw):
    geographic = draw(st.text(alphabet=string.ascii_letters, min_size=1, max_size=2))
    outward = draw(st.text(alphabet=string.digits, min_size=1, max_size=2))
    inward_n = draw(st.text(alphabet=string.digits, min_size=1, max_size=1))
    inward_suffix = draw(st.text(alphabet=string.ascii_letters, min_size=2, max_size=2))
    space = draw(st.one_of(st.just(" "), st.just("")))

    return Postcode(
        input=f"{geographic}{outward}{space}{inward_n}{inward_suffix}",
        output=f"{geographic}{outward} {inward_n}{inward_suffix}".upper(),
    )
