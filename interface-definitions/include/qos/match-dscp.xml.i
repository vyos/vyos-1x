<!-- include start from qos/match-dscp.xml.i -->
<leafNode name="dscp">
  <properties>
    <help>Match on Differentiated Services Codepoint (DSCP)</help>
    <completionHelp>
      <list>default reliability throughput lowdelay priority immediate flash flash-override critical internet network af11 af12 af13 af21 af22 af23 af31 af32 af33 af41 af42 af43 cs1 cs2 cs3 cs4 cs5 cs6 cs7 ef</list>
    </completionHelp>
    <valueHelp>
      <format>u32:0-63</format>
      <description>Differentiated Services Codepoint (DSCP) value </description>
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
      <format>af11</format>
      <description>High-throughput data</description>
    </valueHelp>
    <valueHelp>
      <format>af12</format>
      <description>High-throughput data</description>
    </valueHelp>
    <valueHelp>
      <format>af13</format>
      <description>High-throughput data</description>
    </valueHelp>
    <valueHelp>
      <format>af21</format>
      <description>Low-latency data</description>
    </valueHelp>
    <valueHelp>
      <format>af22</format>
      <description>Low-latency data</description>
    </valueHelp>
    <valueHelp>
      <format>af23</format>
      <description>Low-latency data</description>
    </valueHelp>
    <valueHelp>
      <format>af31</format>
      <description>Multimedia streaming</description>
    </valueHelp>
    <valueHelp>
      <format>af32</format>
      <description>Multimedia streaming</description>
    </valueHelp>
    <valueHelp>
      <format>af33</format>
      <description>Multimedia streaming</description>
    </valueHelp>
    <valueHelp>
      <format>af41</format>
      <description>Multimedia conferencing</description>
    </valueHelp>
    <valueHelp>
      <format>af42</format>
      <description>Multimedia conferencing</description>
    </valueHelp>
    <valueHelp>
      <format>af43</format>
      <description>Multimedia conferencing</description>
    </valueHelp>
    <valueHelp>
      <format>cs1</format>
      <description>Low-priority data</description>
    </valueHelp>
    <valueHelp>
      <format>cs2</format>
      <description>OAM</description>
    </valueHelp>
    <valueHelp>
      <format>cs3</format>
      <description>Broadcast video</description>
    </valueHelp>
    <valueHelp>
      <format>cs4</format>
      <description>Real-time interactive</description>
    </valueHelp>
    <valueHelp>
      <format>cs5</format>
      <description>Signaling</description>
    </valueHelp>
    <valueHelp>
      <format>cs6</format>
      <description>Network control</description>
    </valueHelp>
    <valueHelp>
      <format>cs7</format>
      <description></description>
    </valueHelp>
    <valueHelp>
      <format>ef</format>
      <description>Expedited Forwarding</description>
    </valueHelp>
    <constraint>
      <validator name="numeric" argument="--range 0-63"/>
      <regex>(default|reliability|throughput|lowdelay|priority|immediate|flash|flash-override|critical|internet|network|af11|af12|af13|af21|af22|af23|af31|af32|af33|af41|af42|af43|cs1|cs2|cs3|cs4|cs5|cs6|cs7|ef)</regex>
    </constraint>
  </properties>
</leafNode>
<!-- include end -->
