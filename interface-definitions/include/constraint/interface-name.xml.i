<!-- include start from constraint/interface-name.xml.in -->
<regex>(bond|br|dum|en|ersp|eth|gnv|ifb|lan|l2tp|l2tpeth|macsec|peth|ppp|pppoe|pptp|sstp|tun|veth|vti|vtun|vxlan|wg|wlan|wwan)[0-9]+(.\d+)?|lo</regex>
<validator name="file-path --lookup-path /sys/class/net --directory"/>
<!-- include end -->
