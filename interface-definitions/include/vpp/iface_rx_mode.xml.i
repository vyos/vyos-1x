<!-- include start from vpp/iface_rx_mode.xml.i -->
<leafNode name="rx-mode">
    <properties>
        <help>Receive packet processing mode</help>
        <completionHelp>
            <list>polling interrupt adaptive</list>
        </completionHelp>
        <valueHelp>
            <format>polling</format>
            <description>Constantly check for new data</description>
        </valueHelp>
        <valueHelp>
            <format>interrupt</format>
            <description>Interrupt mode</description>
        </valueHelp>
        <valueHelp>
            <format>adaptive</format>
            <description>Adaptive mode</description>
        </valueHelp>
        <constraint>
            <regex>(polling|interrupt|adaptive)</regex>
        </constraint>
    </properties>
</leafNode>
<!-- include end -->
