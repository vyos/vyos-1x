<!-- include start from accel-ppp/client-ip-pool-name.xml.i -->
<tagNode name="name">
  <properties>
    <help>Pool name</help>
    <valueHelp>
      <format>txt</format>
      <description>Name of IP pool</description>
    </valueHelp>
    <constraint>
      <regex>[-_a-zA-Z0-9.]+</regex>
    </constraint>
  </properties>
  <children>
    #include <include/accel-ppp/gateway-address.xml.i>
    #include <include/accel-ppp/client-ip-pool-subnet-single.xml.i>
  </children>
</tagNode>
<!-- include end -->
