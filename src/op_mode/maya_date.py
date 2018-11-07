#!/usr/bin/env python3
#
# Copyright (c) 2013, 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys

class MayaDate(object):
    """ Converts number of days since UNIX epoch
        to the Maya calendar date.

        Ancient Maya people used three independent calendars for
        different purposes.

        The long count calendar is for recording historical events.
        It represents the number of days passed
        since some date in the past the Maya believed is the day
        our world was created.

        Tzolkin calendar is for religious purposes, it has
        two independent cycles of 13 and 20 days, where 13 day
        cycle days are numbered, and 20 day cycle days are named.

        Haab calendar is for agriculture and daily life, it's a
        365 day calendar with 18 months 20 days each, and 5
        nameless days.

        The smallest unit of the long count calendar is one day (kin).
    """

    """ The long count calendar uses five different base 18 or base 20
        cycles. Modern scholars write long count calendar dates in a dot separated format
        from longest to shortest cycle,
            <baktun>.<katun>.<tun>.<winal>.<kin>
        for example, "13.0.0.9.2".

        Classic version actually used by the ancient Maya wraps around
        every 13th baktun, but modern historians often use longer cycles
        such as piktun = 20 baktun.

    """
    kin    = 1
    winal  = 20      # 20 kin
    tun    = 360     # 18 winal
    katun  = 7200    # 20 tun
    baktun = 144000  # 20 katun

    """ Tzolk'in date is composed of two independent cycles.
        Dates repeat every 260 days, 13 Ajaw is considered the end
        of tzolk'in.

        Every day of the 20 day cycle has unique name, we number
        them from zero so it's easier to map the remainder to day:
    """
    tzolkin_days = { 0: "Imix'",
                     1: "Ik'",
                     2: "Ak'b'al",
                     3: "K'an",
                     4: "Chikchan",
                     5: "Kimi",
                     6: "Manik'",
                     7: "Lamat",
                     8: "Muluk",
                     9: "Ok",
                    10: "Chuwen",
                    11: "Eb'",
                    12: "B'en",
                    13: "Ix",
                    14: "Men",
                    15: "Kib'",
                    16: "Kab'an",
                    17: "Etz'nab'",
                    18: "Kawak",
                    19: "Ajaw" }

    """ As said above, haab (year) has 19 months. Only 18 are
        true months of 20 days each, the remaining 5 days  called "wayeb"
        do not really belong to any month, but we think of them as a pseudo-month
        for convenience.

        Also, note that days of the month are actually numbered from 0, not from 1,
        it's not for technical reasons.
    """
    haab_months = { 0: "Pop",
                    1: "Wo'",
                    2: "Sip",
                    3: "Sotz'",
                    4: "Sek",
                    5: "Xul",
                    6: "Yaxk'in'",
                    7: "Mol",
                    8: "Ch'en",
                    9: "Yax",
                   10: "Sak'",
                   11: "Keh",
                   12: "Mak",
                   13: "K'ank'in",
                   14: "Muwan'",
                   15: "Pax",
                   16: "K'ayab",
                   17: "Kumk'u",
                   18: "Wayeb'" }

    """ Now we need to map the beginning of UNIX epoch
        (Jan 1 1970 00:00 UTC) to the beginning of the long count
        calendar (0.0.0.0.0, 4 Ajaw, 8 Kumk'u).

        The problem with mapping the long count calendar to
        any other is that its start date is not known exactly.

        The most widely accepted hypothesis suggests it was
        August 11, 3114 BC gregorian date. In this case UNIX epoch
        starts on 12.17.16.7.5, 13 Chikchan, 3 K'ank'in

        It's known as Goodman-Martinez-Thompson (GMT) correlation
        constant.
    """
    start_days = 1856305

    """ Seconds in day, for conversion from timestamp """
    seconds_in_day = 60 * 60 * 24

    def __init__(self, timestamp):
        if timestamp is None:
            self.days = self.start_days
        else:
            self.days = self.start_days + (int(timestamp) // self.seconds_in_day)

    def long_count_date(self):
        """ Returns long count date string """
        days = self.days

        cur_baktun = days // self.baktun
        days = days % self.baktun

        cur_katun = days // self.katun
        days = days % self.katun

        cur_tun = days // self.tun
        days = days % self.tun

        cur_winal = days // self.winal
        days = days % self.winal

        cur_kin = days

        longcount_string = "{0}.{1}.{2}.{3}.{4}".format( cur_baktun, 
                                                cur_katun,
                                                cur_tun,
                                                cur_winal,
                                                cur_kin )
        return(longcount_string)

    def tzolkin_date(self):
        """ Returns tzolkin date string """
        days = self.days

        """ The start date is not the beginning of both cycles,
            it's 4 Ajaw. So we need to add 4 to the 13 days cycle day,
            and substract 1 from the 20 day cycle to get correct result.
        """
        tzolkin_13 = (days + 4) % 13
        tzolkin_20 = (days - 1) % 20

        tzolkin_string = "{0} {1}".format(tzolkin_13, self.tzolkin_days[tzolkin_20])

        return(tzolkin_string)

    def haab_date(self):
        """ Returns haab date string.

            The time start on 8 Kumk'u rather than 0 Pop, which is
            17 days before the new haab, so we need to substract 17
            from the current date to get correct result.
        """
        days = self.days

        haab_day = (days - 17) % 365
        haab_month = haab_day // 20
        haab_day_of_month = haab_day % 20

        haab_string =  "{0} {1}".format(haab_day_of_month, self.haab_months[haab_month])

        return(haab_string)

    def date(self):
        return("{0}, {1}, {2}".format( self.long_count_date(), self.tzolkin_date(), self.haab_date() ))

if __name__ == '__main__':
    try:
        timestamp = sys.argv[1]
    except:
        print("Please specify timestamp in the argument")
        sys.exit(1)

    maya_date = MayaDate(timestamp)
    print(maya_date.date())
