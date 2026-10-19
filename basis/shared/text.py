"""Text value normalization shared by athlete and exercise names."""

import re


def normalized_name(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().title()
