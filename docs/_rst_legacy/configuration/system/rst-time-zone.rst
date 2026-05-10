.. _timezone:

#########
Time Zone
#########

Time Zone setting is very important as e.g all your logfile entries will be
based on the configured zone. Without proper time zone configuration it will
be very difficult to compare logfiles from different systems.

.. cfgcmd:: set system time-zone <timezone>

   Specify the systems `<timezone>` as the Region/Location that best defines
   your location. For example, specifying US/Pacific sets the time zone to US
   Pacific time.

   Command completion can be used to list available time zones. The adjustment
   for daylight time will take place automatically based on the time of year.