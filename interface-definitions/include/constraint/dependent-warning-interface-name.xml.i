<!-- include start from constraint/dependent-warning-interface-name.xml.i -->
<constraint>
  <regex>(bond|br|dum|en|ersp|eth|gnv|ifb|ipoe|lan|l2tp|l2tpeth|macsec|peth|ppp|pppoe|pptp|sstp|sstpc|tun|veth|vpptap|vpptun|vti|vtun|vxlan|wg|wlan|wwan)[0-9]+(.\d+)?|pod-[-_a-zA-Z0-9]{1,11}|lo</regex>
  <validator name="interface-exists"/>
</constraint>
<dependency kind="interface" alert="warning"/>
<!-- include end -->
