<!-- include start from qos/set-dscp.xml.i -->
<leafNode name="set-dscp">
  <properties>
    <help>Change the Differentiated Services (DiffServ) field in the IP header</help>
    <completionHelp>
      <list>default reliability throughput lowdelay priority immediate flash flash-override critical internet network AF11 AF12 AF13 AF21 AF22 AF23 AF31 AF32 AF33 AF41 AF42 AF43 CS1 CS2 CS3 CS4 CS5 CS6 CS7 EF</list>
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
    <valueHelp>
      <format>AF11</format>
      <description>High-throughput data</description>
    </valueHelp>
    <valueHelp>
      <format>AF12</format>
      <description>High-throughput data</description>
    </valueHelp>
    <valueHelp>
      <format>AF13</format>
      <description>High-throughput data</description>
    </valueHelp>
    <valueHelp>
      <format>AF21</format>
      <description>Low-latency data</description>
    </valueHelp>
    <valueHelp>
      <format>AF22</format>
      <description>Low-latency data</description>
    </valueHelp>
    <valueHelp>
      <format>AF23</format>
      <description>Low-latency data</description>
    </valueHelp>
    <valueHelp>
      <format>AF31</format>
      <description>Multimedia streaming</description>
    </valueHelp>
    <valueHelp>
      <format>AF32</format>
      <description>Multimedia streaming</description>
    </valueHelp>
    <valueHelp>
      <format>AF33</format>
      <description>Multimedia streaming</description>
    </valueHelp>
    <valueHelp>
      <format>AF41</format>
      <description>Multimedia conferencing</description>
    </valueHelp>
    <valueHelp>
      <format>AF42</format>
      <description>Multimedia conferencing</description>
    </valueHelp>
    <valueHelp>
      <format>AF43</format>
      <description>Multimedia conferencing</description>
    </valueHelp>
    <valueHelp>
      <format>CS1</format>
      <description>Low-priority data</description>
    </valueHelp>
    <valueHelp>
      <format>CS2</format>
      <description>OAM</description>
    </valueHelp>
    <valueHelp>
      <format>CS3</format>
      <description>Broadcast video</description>
    </valueHelp>
    <valueHelp>
      <format>CS4</format>
      <description>Real-time interactive</description>
    </valueHelp>
    <valueHelp>
      <format>CS5</format>
      <description>Signaling</description>
    </valueHelp>
    <valueHelp>
      <format>CS6</format>
      <description>Network control</description>
    </valueHelp>
    <valueHelp>
      <format>CS7</format>
      <description></description>
    </valueHelp>
    <valueHelp>
      <format>EF</format>
      <description>Expedited Forwarding</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-63"/>
      <regex>(default|reliability|throughput|lowdelay|priority|immediate|flash|flash-override|critical|internet|network|AF11|AF12|AF13|AF21|AF22|AF23|AF31|AF32|AF33|AF41|AF42|AF43|CS1|CS2|CS3|CS4|CS5|CS6|CS7|EF)</regex>
    </constraint>
    <constraintErrorMessage>Priority must be between 0 and 63</constraintErrorMessage>
  </properties>
</leafNode>
<!-- include end -->
