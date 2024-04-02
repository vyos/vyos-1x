'''Copyright (c) 2013, Dmitry Voronin
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
'''

# coding=utf8

#  Split range to ranges that has its unique pattern.
#  Example for 12-345:
#
#  12- 19: 1[2-9]
#  20- 99: [2-9]\d
# 100-299: [1-2]\d{2}
# 300-339: 3[0-3]\d
# 340-345: 34[0-5]

def range_to_regex(inpt_range):
    if isinstance(inpt_range, str):
        range_list = inpt_range.split('-')
        # Check input arguments
        if len(range_list) == 2:
            # The first element in range must be higher then the second
            if int(range_list[0]) < int(range_list[1]):
                return regex_for_range(int(range_list[0]), int(range_list[1]))

    return None

def bounded_regex_for_range(min_, max_):
    return r'\b({})\b'.format(regex_for_range(min_, max_))

def regex_for_range(min_, max_):
    """
    > regex_for_range(12, 345)
    '1[2-9]|[2-9]\d|[1-2]\d{2}|3[0-3]\d|34[0-5]'
    """
    positive_subpatterns = []
    negative_subpatterns = []

    if min_ < 0:
        min__ = 1
        if max_ < 0:
            min__ = abs(max_)
        max__ = abs(min_)

        negative_subpatterns = split_to_patterns(min__, max__)
        min_ = 0

    if max_ >= 0:
        positive_subpatterns = split_to_patterns(min_, max_)

    negative_only_subpatterns = ['-' + val for val in negative_subpatterns if val not in positive_subpatterns]
    positive_only_subpatterns = [val for val in positive_subpatterns if val not in negative_subpatterns]
    intersected_subpatterns = ['-?' + val for val in negative_subpatterns if val in positive_subpatterns]

    subpatterns = negative_only_subpatterns + intersected_subpatterns + positive_only_subpatterns
    return '|'.join(subpatterns)


def split_to_patterns(min_, max_):
    subpatterns = []

    start = min_
    for stop in split_to_ranges(min_, max_):
        subpatterns.append(range_to_pattern(start, stop))
        start = stop + 1

    return subpatterns


def split_to_ranges(min_, max_):
    stops = {max_}

    nines_count = 1
    stop = fill_by_nines(min_, nines_count)
    while min_ <= stop < max_:
        stops.add(stop)

        nines_count += 1
        stop = fill_by_nines(min_, nines_count)

    zeros_count = 1
    stop = fill_by_zeros(max_ + 1, zeros_count) - 1
    while min_ < stop <= max_:
        stops.add(stop)

        zeros_count += 1
        stop = fill_by_zeros(max_ + 1, zeros_count) - 1

    stops = list(stops)
    stops.sort()

    return stops


def fill_by_nines(integer, nines_count):
    return int(str(integer)[:-nines_count] + '9' * nines_count)


def fill_by_zeros(integer, zeros_count):
    return integer - integer % 10 ** zeros_count


def range_to_pattern(start, stop):
    pattern = ''
    any_digit_count = 0

    for start_digit, stop_digit in zip(str(start), str(stop)):
        if start_digit == stop_digit:
            pattern += start_digit
        elif start_digit != '0' or stop_digit != '9':
            pattern += '[{}-{}]'.format(start_digit, stop_digit)
        else:
            any_digit_count += 1

    if any_digit_count:
        pattern += r'\d'

    if any_digit_count > 1:
        pattern += '{{{}}}'.format(any_digit_count)

    return pattern
