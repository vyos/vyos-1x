<!-- include start from haproxy/rule-match-domain.xml.i -->
<leafNode name="domain-name">
    <properties>
    <help>Domain name to match</help>
    <valueHelp>
        <format>txt</format>
        <description>Domain address to match</description>
    </valueHelp>
    <constraint>
        <validator name="fqdn"/>
    </constraint>
    <multi/>
    </properties>
</leafNode>
<leafNode name="wildcard-domain">
    <properties>
    <help>Match subdomains of specified domain(s)</help>
    <valueless/>
    </properties>
</leafNode>
<!-- include end -->
