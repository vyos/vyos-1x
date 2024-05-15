<!-- include start from firewall/time.xml.i -->
<node name="time">
  <properties>
    <help>Time to match rule</help>
  </properties>
  <children>
    <leafNode name="startdate">
      <properties>
        <help>Date to start matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter date using following notation - YYYY-MM-DD</description>
        </valueHelp>
        <constraint>
          <regex>(\d{4}\-\d{2}\-\d{2})</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="starttime">
      <properties>
        <help>Time of day to start matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter time using using 24 hour notation - hh:mm:ss</description>
        </valueHelp>
        <constraint>
          <regex>([0-2][0-9](\:[0-5][0-9]){1,2})</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="stopdate">
      <properties>
        <help>Date to stop matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter date using following notation - YYYY-MM-DD</description>
        </valueHelp>
        <constraint>
          <regex>(\d{4}\-\d{2}\-\d{2})</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="stoptime">
      <properties>
        <help>Time of day to stop matching rule</help>
        <valueHelp>
          <format>txt</format>
          <description>Enter time using using 24 hour notation - hh:mm:ss</description>
        </valueHelp>
        <constraint>
          <regex>([0-2][0-9](\:[0-5][0-9]){1,2})</regex>
        </constraint>
      </properties>
    </leafNode>
    <leafNode name="weekdays">
      <properties>
        <help>Comma separated weekdays to match rule on</help>
        <valueHelp>
          <format>txt</format>
          <description>Name of day (Monday, Tuesday, Wednesday, Thursdays, Friday, Saturday, Sunday)</description>
        </valueHelp>
        <valueHelp>
          <format>u32:0-6</format>
          <description>Day number (0 = Sunday ... 6 = Saturday)</description>
        </valueHelp>
      </properties>
    </leafNode>
  </children>
</node>
<!-- include end -->