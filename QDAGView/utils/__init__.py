from typing import *
from itertools import groupby

def _group_consecutive_numbers_clever(numbers:Iterable[int])->Iterable[range]:
    from itertools import groupby
    from operator import itemgetter

    ranges = []

    for k, g in groupby(enumerate(numbers),lambda x:x[0]-x[1]):
        group = ( map(itemgetter(1), g) )
        group = list( map(int, group) )
        ranges.append(range(group[0],group[-1]+1))
    return ranges

def _group_consecutive_numbers_readable(numbers:list[int])->Iterable[range]:
    if not len(numbers)>0:
        return []

    first = last = numbers[0]
    for n in numbers[1:]:
        if n - 1 == last: # Part of the group, bump the end
            last = n
        else: # Not part of the group, yield current group and start a new
            yield range(first, last+1)
            first = last = n
    yield range(first, last+1) # Yield the last group


group_consecutive_numbers = _group_consecutive_numbers_readable