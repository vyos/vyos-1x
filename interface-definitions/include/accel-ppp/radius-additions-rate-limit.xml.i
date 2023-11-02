<!-- include start from accel-ppp/radius-additions-rate-limit.xml.i -->
<node name="rate-limit">
  <properties>
    <help>Upload/Download speed limits</help>
  </properties>
  <children>
    <leafNode name="attribute">
      <properties>
        <help>RADIUS attribute that contains rate information</help>
      </properties>
      <defaultValue>Filter-Id</defaultValue>
    </leafNode>
    <leafNode name="vendor">
      <properties>
        <help>Vendor dictionary</help>
      </properties>
    </leafNode>
    <leafNode name="enable">
      <properties>
        <help>Enable bandwidth shaping via RADIUS</help>
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
