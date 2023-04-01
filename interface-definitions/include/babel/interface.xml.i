<!-- include start from babel/interface.xml.i -->
<tagNode name="interface">
  <properties>
    <help>Interface name</help>
    <completionHelp>
      <script>${vyos_completion_dir}/list_interfaces</script>
    </completionHelp>
    <valueHelp>
      <format>txt</format>
      <description>Interface name</description>
    </valueHelp>
    <constraint>
      #include <include/constraint/interface-name.xml.i>
    </constraint>
  </properties>
  <children>
    <leafNode name="type">
      <properties>
        <help>Interface type</help>
        <completionHelp>
          <list>auto wired wireless</list>
        </completionHelp>
        <valueHelp>
          <format>auto</format>
          <description>Automatically detect interface type</description>
        </valueHelp>
        <valueHelp>
          <format>wired</format>
          <description>Wired interface</description>
        </valueHelp>
        <valueHelp>
          <format>wireless</format>
          <description>Wireless interface</description>
        </valueHelp>
        <constraint>
          <regex>(auto|wired|wireless)</regex>
        </constraint>
      </properties>
      <defaultValue>auto</defaultValue>
    </leafNode>
    <leafNode name="split-horizon">
      <properties>
        <help>Split horizon parameters</help>
        <completionHelp>
          <list>default enable disable</list>
        </completionHelp>
        <valueHelp>
          <format>default</format>
          <description>Enable on wired interfaces, and disable on wireless interfaces</description>
        </valueHelp>
        <valueHelp>
          <format>enable</format>
          <description>Enable split horizon processing</description>
        </valueHelp>
        <valueHelp>
          <format>disable</format>
          <description>Disable split horizon processing</description>
        </valueHelp>
        <constraint>
          <regex>(default|enable|disable)</regex>
        </constraint>
      </properties>
      <defaultValue>default</defaultValue>
    </leafNode>
    <leafNode name="hello-interval">
      <properties>
        <help>Time between scheduled hellos</help>
        <valueHelp>
          <format>u32:20-655340</format>
          <description>Milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 20-655340"/>
        </constraint>
      </properties>
      <defaultValue>4000</defaultValue>
    </leafNode>
    <leafNode name="update-interval">
      <properties>
        <help>Time between scheduled updates</help>
        <valueHelp>
          <format>u32:20-655340</format>
          <description>Milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 20-655340"/>
        </constraint>
      </properties>
      <defaultValue>20000</defaultValue>
    </leafNode>
    <leafNode name="rxcost">
      <properties>
        <help>Base receive cost for this interface</help>
        <valueHelp>
          <format>u32:1-65534</format>
          <description>Base receive cost</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65534"/>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="rtt-decay">
      <properties>
        <help>Decay factor for exponential moving average of RTT samples</help>
        <valueHelp>
          <format>u32:1-256</format>
          <description>Decay factor, in units of 1/256</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-256"/>
        </constraint>
      </properties>
      <defaultValue>42</defaultValue>
    </leafNode>
    <leafNode name="rtt-min">
      <properties>
        <help>Minimum RTT</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
      <defaultValue>10</defaultValue>
    </leafNode>
    <leafNode name="rtt-max">
      <properties>
        <help>Maximum RTT</help>
        <valueHelp>
          <format>u32:1-65535</format>
          <description>Milliseconds</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-65535"/>
        </constraint>
      </properties>
      <defaultValue>120</defaultValue>
    </leafNode>
    <leafNode name="max-rtt-penalty">
      <properties>
        <help>Maximum additional cost due to RTT</help>
        <valueHelp>
          <format>u32:0-65535</format>
          <description>Milliseconds (0 to disable the use of RTT-based cost)</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0-65535"/>
        </constraint>
      </properties>
      <defaultValue>150</defaultValue>
    </leafNode>
    <leafNode name="enable-timestamps">
      <properties>
        <help>Enable timestamps with each Hello and IHU message in order to compute RTT values</help>
        <valueless/>
      </properties>
    </leafNode>
    <leafNode name="channel">
      <properties>
        <help>Channel number for diversity routing</help>
        <completionHelp>
          <list>interfering non-interfering</list>
        </completionHelp>
        <valueHelp>
          <format>u32:1-254</format>
          <description>Interfaces with a channel number interfere with interfering interfaces and interfaces with the same channel number</description>
        </valueHelp>
        <valueHelp>
          <format>interfering</format>
          <description>Interfering interfaces are assumed to interfere with all other channels except non-interfering channels</description>
        </valueHelp>
        <valueHelp>
          <format>non-interfering</format>
          <description>Non-interfering interfaces only interfere with themselves</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 1-254"/>
          <regex>(interfering|non-interfering)</regex>
        </constraint>
      </properties>
    </leafNode>
  </children>
</tagNode>
<!-- include end -->
