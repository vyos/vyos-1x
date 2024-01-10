<!-- include start from accel-ppp/client-ip-pool.xml.i -->
<tagNode name="client-ip-pool">
  <properties>
    <help>Client IP pool</help>
    <valueHelp>
      <format>txt</format>
      <description>Name of IP pool</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
    </constraint>
  </properties>
  <children>
    <leafNode name="range">
      <properties>
        <help>Range of IP addresses</help>
        <valueHelp>
          <format>ipv4net</format>
          <description>IPv4 prefix</description>
        </valueHelp>
        <valueHelp>
          <format>ipv4range</format>
          <description>IPv4 address range inside /24 network</description>
        </valueHelp>
        <constraint>
          <validator name="ipv4-prefix"/>
          <validator name="ipv4-host"/>
          <validator name="ipv4-range-mask"  argument="-m 24 -r"/>
        </constraint>
        <multi/>
      </properties>
    </leafNode>
    <leafNode name="next-pool">
      <properties>
        <help>Next pool name</help>
        <completionHelp>
          <path>${COMP_WORDS[@]:1:${#COMP_WORDS[@]}-4}</path>
        </completionHelp>
        <valueHelp>
          <format>txt</format>
          <description>Name of IP pool</description>
        </valueHelp>
        <constraint>
          #include <include/constraint/alpha-numeric-hyphen-underscore-dot.xml.i>
        </constraint>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
