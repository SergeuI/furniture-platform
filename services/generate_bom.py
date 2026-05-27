from collections import defaultdict


def generate_bom(details):

    result = defaultdict(int)

    for item in details:

        name = item["name"]

        qty = item.get("qty", 1)

        result[name] += qty

    return dict(result)