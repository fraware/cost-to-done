"""Half-open interval normalization (starter)."""


def normalize(intervals):
    result = []
    for start, end in sorted(intervals):
        if result and start < result[-1][1]:
            result[-1] = (result[-1][0], end)
        else:
            result.append((start, end))
    return result
