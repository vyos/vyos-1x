<!-- include start from policy/community-value-list.xml.i -->
<completionHelp>
    <list>
      local-as
      no-advertise
      no-export
      internet
      graceful-shutdown
      accept-own
      route-filter-translated-v4
      route-filter-v4
      route-filter-translated-v6
      route-filter-v6
      llgr-stale
      no-llgr
      accept-own-nexthop
      blackhole
      no-peer
    </list>
</completionHelp>
<valueHelp>
    <format>&lt;AS:VAL&gt;</format>
    <description>Community number in &lt;0-65535:0-65535&gt; format</description>
</valueHelp>
<valueHelp>
    <format>local-as</format>
    <description>Well-known communities value NO_EXPORT_SUBCONFED 0xFFFFFF03</description>
</valueHelp>
<valueHelp>
    <format>no-advertise</format>
    <description>Well-known communities value NO_ADVERTISE 0xFFFFFF02</description>
</valueHelp>
<valueHelp>
    <format>no-export</format>
    <description>Well-known communities value NO_EXPORT 0xFFFFFF01</description>
</valueHelp>
<valueHelp>
    <format>internet</format>
    <description>Well-known communities value 0</description>
</valueHelp>
<valueHelp>
    <format>graceful-shutdown</format>
    <description>Well-known communities value GRACEFUL_SHUTDOWN 0xFFFF0000</description>
</valueHelp>
<valueHelp>
    <format>accept-own</format>
    <description>Well-known communities value ACCEPT_OWN 0xFFFF0001</description>
</valueHelp>
<valueHelp>
    <format>route-filter-translated-v4</format>
    <description>Well-known communities value ROUTE_FILTER_TRANSLATED_v4 0xFFFF0002</description>
</valueHelp>
<valueHelp>
    <format>route-filter-v4</format>
    <description>Well-known communities value ROUTE_FILTER_v4 0xFFFF0003</description>
</valueHelp>
<valueHelp>
    <format>route-filter-translated-v6</format>
    <description>Well-known communities value ROUTE_FILTER_TRANSLATED_v6 0xFFFF0004</description>
</valueHelp>
<valueHelp>
    <format>route-filter-v6</format>
    <description>Well-known communities value ROUTE_FILTER_v6 0xFFFF0005</description>
</valueHelp>
<valueHelp>
    <format>llgr-stale</format>
    <description>Well-known communities value LLGR_STALE 0xFFFF0006</description>
</valueHelp>
<valueHelp>
    <format>no-llgr</format>
    <description>Well-known communities value NO_LLGR 0xFFFF0007</description>
</valueHelp>
<valueHelp>
    <format>accept-own-nexthop</format>
    <description>Well-known communities value accept-own-nexthop 0xFFFF0008</description>
</valueHelp>
<valueHelp>
    <format>blackhole</format>
    <description>Well-known communities value BLACKHOLE 0xFFFF029A</description>
</valueHelp>
<valueHelp>
    <format>no-peer</format>
    <description>Well-known communities value NOPEER 0xFFFFFF04</description>
</valueHelp>
<multi/>
<constraint>
    <regex>local-as|no-advertise|no-export|internet|graceful-shutdown|accept-own|route-filter-translated-v4|route-filter-v4|route-filter-translated-v6|route-filter-v6|llgr-stale|no-llgr|accept-own-nexthop|blackhole|no-peer</regex>
    <validator name="bgp-regular-community"/>
</constraint>
        <!-- include end -->
