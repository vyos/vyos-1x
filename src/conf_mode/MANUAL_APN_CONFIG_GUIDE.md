# MANUAL APN CONFIGURATION GUIDE
# Based on your Rogers SIM and staff's APN library results

## BASIC DATA APN CONFIGURATION (Required)
# This is what you need for internet access

[Current Basic Config]
apn=ltemobile.apn
username=
password=
auth_type=none
pdp_type=ipv4v6

## ENHANCED APN CONFIGURATION (From your staff's library)
# This is what your Android APN library found for your Rogers SIM

[Primary Rogers APN - Recommended]
apn_name=ltemobile.apn
apn_type=default,ia,mms,supl
protocol=ipv4v6
roaming_protocol=ipv4v6

# MMS Configuration (if needed for messaging)
mmsc=http://mms.gprs.rogers.com
mms_proxy=mmsproxy.rogers.com
mms_proxy_port=80

[Alternative Rogers APNs - Fallback Options]
# Your library found these additional Rogers APNs:

# Option 2: Chatr (Rogers subsidiary)
apn_name=chatrweb.apn
mmsc=http://mms.chatrwireless.com
mms_proxy=mmsproxy.chatrwireless.com
mms_proxy_port=80

# Option 3: Rogers Core Application
apn_name=rogers-core-appl1.apn
mmsc=http://mms.gprs.rogers.com
mms_proxy=mmsproxy.rogers.com
mms_proxy_port=80

## WHAT YOU NEED TO KNOW FOR MANUAL CONFIG:

1. **Basic Internet Access:**
   - APN: ltemobile.apn (primary)
   - Protocol: ipv4v6 (modern dual-stack)
   - No username/password needed for Rogers

2. **MMS Support (if you need messaging):**
   - Same APN can handle both data and MMS
   - MMS requires additional proxy settings
   - Rogers MMSC: http://mms.gprs.rogers.com

3. **Your Current vs Optimal:**
   - Current: nxtgenphone (generic)
   - Optimal: ltemobile.apn (Rogers-specific)

## MODEMEMAGER COMMANDS FOR MANUAL SETUP:

# Create connection with proper Rogers APN
mmcli -m 0 --simple-connect="apn=ltemobile.apn,ip-type=ipv4v6"

# For MMS (if your system supports it):
# Additional bearer with MMS proxy settings would be created

## KEY DIFFERENCES:

**Data Only:** Just need APN name
**Data + MMS:** Need APN + MMS proxy configuration
**Your System:** Can auto-discover all of this with your staff's library!

## RECOMMENDATION:
Use your staff's APN library for automatic configuration rather than manual - 
it found 9 Rogers APNs with complete MMS settings!