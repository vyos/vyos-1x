<!-- include start from accel-ppp/radius-additions-rate-limit.xml.i -->
<node name="rate-limit">
  <properties>
    <help>Upload/Download speed limits</help>
  </properties>
  <children>
    <leafNode name="attribute">
      <properties>
        <help>Specifies which radius attribute contains rate information. (default is Filter-Id)</help>
      </properties>
      <defaultValue>Filter-Id</defaultValue>
    </leafNode>
    <leafNode name="vendor">
      <properties>
        <help>Specifies the vendor dictionary. (dictionary needs to be in /usr/share/accel-ppp/radius)</help>
      </properties>
    </leafNode>
    <leafNode name="enable">
      <properties>
        <help>Enables Bandwidth shaping via RADIUS</help>
        <valueless />
      </properties>
    </leafNode>
    <leafNode name="multiplier">
      <properties>
        <help>Shaper multiplier</help>
        <valueHelp>
          <format>&lt;0.001-1000&gt;</format>
          <description>Shaper multiplier</description>
        </valueHelp>
        <constraint>
          <validator name="numeric" argument="--range 0.001-1000 --float"/>
        </constraint>
        <constraintErrorMessage>Multiplier needs to be between 0.001 and 1000</constraintErrorMessage>
      </properties>
      <defaultValue>1</defaultValue>
    </leafNode>
  </children>
</node>
<!-- include end -->
