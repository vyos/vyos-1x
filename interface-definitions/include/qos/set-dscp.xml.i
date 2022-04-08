<!-- include start from qos/set-dscp.xml.i -->
<leafNode name="set-dscp">
  <properties>
    <help>Change the Differentiated Services (DiffServ) field in the IP header</help>
    <completionHelp>
      <list>default reliability throughput lowdelay priority immediate flash flash-override critical internet network</list>
    </completionHelp>
    <valueHelp>
      <format>u32:0-63</format>
      <description>Priority order for bandwidth pool</description>
    </valueHelp>
    <valueHelp>
      <format>default</format>
      <description>match DSCP (000000)</description>
    </valueHelp>
    <valueHelp>
      <format>reliability</format>
      <description>match DSCP (000001)</description>
    </valueHelp>
    <valueHelp>
      <format>throughput</format>
      <description>match DSCP (000010)</description>
    </valueHelp>
    <valueHelp>
      <format>lowdelay</format>
      <description>match DSCP (000100)</description>
    </valueHelp>
    <valueHelp>
      <format>priority</format>
      <description>match DSCP (001000)</description>
    </valueHelp>
    <valueHelp>
      <format>immediate</format>
      <description>match DSCP (010000)</description>
    </valueHelp>
    <valueHelp>
      <format>flash</format>
      <description>match DSCP (011000)</description>
    </valueHelp>
    <valueHelp>
      <format>flash-override</format>
      <description>match DSCP (100000)</description>
    </valueHelp>
    <valueHelp>
      <format>critical</format>
      <description>match DSCP (101000)</description>
    </valueHelp>
    <valueHelp>
      <format>internet</format>
      <description>match DSCP (110000)</description>
    </valueHelp>
    <valueHelp>
      <format>network</format>
      <description>match DSCP (111000)</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-63"/>
      <regex>(default|reliability|throughput|lowdelay|priority|immediate|flash|flash-override|critical|internet|network)</regex>
    </constraint>
    <constraintErrorMessage>Priority must be between 0 and 63</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
