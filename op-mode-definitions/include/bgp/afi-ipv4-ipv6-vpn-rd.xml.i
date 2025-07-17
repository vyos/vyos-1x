<!-- included start from bgp/afi-ipv4-ipv6-vpn-rd.xml.i -->
<tagNode name="rd">
  <properties>
    <help>Display routes matching the route distinguisher</help>
    <completionHelp>
      <list>ASN:NN IPADDRESS:NN all</list>
    </completionHelp>
  </properties>
  <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
  <children>
    <virtualTagNode>
      <properties>
        <help>Show IP routes of specified prefix</help>
        <completionHelp>
          <list>&lt;x.x.x.x/x&gt; &lt;x:x:x:x:x:x:x:x/x&gt;</list>
        </completionHelp>
      </properties>
      <command>${vyos_op_scripts_dir}/vtysh_wrapper.sh $@</command>
    </virtualTagNode>
  </children>
</tagNode>
<!-- included end -->
