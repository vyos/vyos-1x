"""
WWAN State Transition Management Module

This module provides data-driven state transition management for the WWAN state machine.
Extracted from the main state machine to improve maintainability and allow for
dynamic state transition configuration.
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StateTransition:
    """Represents a single state transition"""
    from_state: str
    to_state: str
    event: str
    description: str = ""
    conditions: List[str] = None

    def __post_init__(self):
        if self.conditions is None:
            self.conditions = []


@dataclass
class StateTransitionGroup:
    """Groups related state transitions for better organization"""
    name: str
    description: str
    transitions: List[StateTransition]


class StateTransitionManager:
    """
    Manages state transitions using a data-driven approach.

    Provides validation, analysis, and dynamic transition management
    to replace the hardcoded transition table in the state machine.
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.TransitionManager")
        self.transition_groups = []
        self.transitions_by_state = {}
        self.transitions_by_event = {}
        self._build_transition_groups()
        self._index_transitions()

    def _build_transition_groups(self):
        """Build organized transition groups"""

        # Initial Flow
        initial_flow = StateTransitionGroup(
            name="Initial Flow",
            description="Basic startup and modem discovery flow",
            transitions=[
                StateTransition("INITIAL", "SCANNING", "START_SCAN", "Start scanning for modems"),
                StateTransition("SCANNING", "MODEM_FOUND", "MODEM_FOUND", "Modem discovered and accessible"),
            ]
        )

        # Configuration Flow
        config_flow = StateTransitionGroup(
            name="Configuration Flow",
            description="Modem configuration and setup transitions",
            transitions=[
                StateTransition("MODEM_FOUND", "WAITING_FOR_CONFIG", "WAIT_FOR_CONFIG", "Wait for configuration"),
                StateTransition("WAITING_FOR_CONFIG", "CONFIGURING", "CONFIG_UPDATE", "Apply configuration"),
                StateTransition("USAGE_MONITORING", "MODEM_FOUND", "MODEM_FOUND", "Hot-plug: New modem detected"),
                StateTransition("USAGE_MONITORING", "WAITING_FOR_CONFIG", "WAIT_FOR_CONFIG", "Hot-plug: Wait for config"),
                StateTransition("USAGE_MONITORING", "CONFIGURING", "CONFIG_UPDATE", "Hot-plug: Apply configuration"),
            ]
        )

        # Connection Flow
        connection_flow = StateTransitionGroup(
            name="Connection Flow",
            description="Network connection establishment and monitoring",
            transitions=[
                StateTransition("CONFIGURING", "CONNECTING", "CONNECT", "Attempt network connection"),
                StateTransition("CONNECTING", "CONNECTED", "CONNECTED", "Connection established successfully"),
                StateTransition("CONNECTED", "USAGE_MONITORING", "USAGE_LIMIT_EXCEEDED", "Monitor data usage"),
            ]
        )

        # Disconnection Flow
        disconnection_flow = StateTransitionGroup(
            name="Disconnection Flow",
            description="Network disconnection and cleanup",
            transitions=[
                StateTransition("CONNECTED", "DISCONNECTING", "DISCONNECT", "User or system disconnect"),
                StateTransition("USAGE_MONITORING", "DISCONNECTING", "DISCONNECT", "Disconnect from monitoring"),
                StateTransition("DISCONNECTING", "DISCONNECTED", "DISCONNECTED", "Disconnection completed"),
            ]
        )

        # SIM Management Flow
        sim_flow = StateTransitionGroup(
            name="SIM Management Flow",
            description="SIM card switching and management transitions",
            transitions=[
                StateTransition("WAITING_FOR_SIM", "CONFIGURING", "SIM_READY", "SIM card ready"),
                StateTransition("FAILED", "CONFIGURING", "SIM_READY", "Recovery with SIM ready"),

                # SIM switching transitions
                StateTransition("CONNECTED", "SIM_SWITCHING", "SWITCH_SIM", "Initiate SIM switch"),
                StateTransition("USAGE_MONITORING", "SIM_SWITCHING", "SWITCH_SIM", "SIM switch from monitoring"),
                StateTransition("CONFIGURING", "SIM_SWITCHING", "SWITCH_SIM", "SIM switch from config"),
                StateTransition("DISCONNECTED", "SIM_SWITCHING", "SWITCH_SIM", "SIM switch when disconnected"),
                StateTransition("FAILED", "SIM_SWITCHING", "SWITCH_SIM", "SIM switch from failed state"),

                # SIM switch process (using actual ModemEvent names)
                StateTransition("SIM_SWITCHING", "SIM_DISCONNECTING", "SIM_DISCONNECTED", "Disconnect for SIM switch"),
                StateTransition("SIM_DISCONNECTING", "SIM_DISABLING", "SIM_DISABLED", "Disable current SIM"),
                StateTransition("SIM_DISABLING", "SIM_ENABLING", "SIM_SWITCHED", "Enable target SIM"),
                StateTransition("SIM_ENABLING", "SIM_RECONFIGURING", "SIM_ENABLED", "Reconfigure with new SIM"),
                StateTransition("SIM_RECONFIGURING", "CONFIGURING", "SIM_SWITCH_COMPLETE", "SIM switch completed"),

                # SIM switch error handling (using CONNECTION_FAILED for now)
                StateTransition("SIM_SWITCHING", "FAILED", "CONNECTION_FAILED", "SIM switch failed"),
                StateTransition("SIM_DISCONNECTING", "FAILED", "CONNECTION_FAILED", "Disconnect failed"),
                StateTransition("SIM_DISABLING", "FAILED", "CONNECTION_FAILED", "Disable failed"),
                StateTransition("SIM_ENABLING", "FAILED", "CONNECTION_FAILED", "Enable failed"),
                StateTransition("SIM_RECONFIGURING", "FAILED", "CONNECTION_FAILED", "Reconfig failed"),
            ]
        )

        # Error Handling Flow
        error_flow = StateTransitionGroup(
            name="Error Handling Flow",
            description="Error recovery and failure state management",
            transitions=[
                StateTransition("CONNECTING", "FAILED", "CONNECTION_FAILED", "Connection attempt failed"),
                StateTransition("CONFIGURING", "FAILED", "CONNECTION_FAILED", "Configuration failed"),
                StateTransition("SCANNING", "FAILED", "CONNECTION_FAILED", "Modem scan failed"),
                StateTransition("FAILED", "SCANNING", "START_SCAN", "Retry modem scanning"),
                StateTransition("FAILED", "CONFIGURING", "RECONFIGURE", "Retry configuration"),
                StateTransition("FAILED", "CONNECTING", "CONNECT", "Retry connection"),
            ]
        )

        # Reconfiguration Flow
        reconfig_flow = StateTransitionGroup(
            name="Reconfiguration Flow",
            description="Runtime configuration changes and updates",
            transitions=[
                StateTransition("CONFIGURING", "CONFIGURING", "RECONFIGURE", "Configuration update"),
                StateTransition("CONNECTED", "CONFIGURING", "RECONFIGURE", "Reconfigure connected modem"),
                StateTransition("DISCONNECTED", "CONFIGURING", "RECONFIGURE", "Reconfigure disconnected modem"),
                StateTransition("FAILED", "CONFIGURING", "RECONFIGURE", "Reconfigure failed modem"),
                StateTransition("USAGE_MONITORING", "CONFIGURING", "RECONFIGURE", "Reconfigure from monitoring"),
            ]
        )

        # Usage Monitoring Flow
        usage_flow = StateTransitionGroup(
            name="Usage Monitoring Flow",
            description="Data usage monitoring and threshold management",
            transitions=[
                StateTransition("USAGE_MONITORING", "USAGE_THRESHOLD", "USAGE_LIMIT_EXCEEDED", "Usage limit exceeded"),
                StateTransition("USAGE_THRESHOLD", "USAGE_RESETTING", "RESET_USAGE", "Reset usage counters"),
                StateTransition("USAGE_RESETTING", "CONFIGURING", "RECONFIGURE", "Reconfigure after reset"),
            ]
        )

        # Store all transition groups
        self.transition_groups = [
            initial_flow, config_flow, connection_flow, disconnection_flow,
            sim_flow, error_flow, reconfig_flow, usage_flow
        ]

    def _index_transitions(self):
        """Create indexes for fast transition lookup"""
        self.transitions_by_state = {}
        self.transitions_by_event = {}

        for group in self.transition_groups:
            for transition in group.transitions:
                # Index by from_state
                if transition.from_state not in self.transitions_by_state:
                    self.transitions_by_state[transition.from_state] = []
                self.transitions_by_state[transition.from_state].append(transition)

                # Index by event
                if transition.event not in self.transitions_by_event:
                    self.transitions_by_event[transition.event] = []
                self.transitions_by_event[transition.event].append(transition)

    def get_all_transitions(self) -> List[Tuple[str, str, str]]:
        """Get all transitions as tuples for compatibility with existing code"""
        transitions = []
        for group in self.transition_groups:
            for transition in group.transitions:
                transitions.append((transition.from_state, transition.to_state, transition.event))
        return transitions

    def get_valid_transitions_from_state(self, state: str) -> List[StateTransition]:
        """Get all valid transitions from a given state"""
        return self.transitions_by_state.get(state, [])

    def get_transitions_for_event(self, event: str) -> List[StateTransition]:
        """Get all transitions triggered by a specific event"""
        return self.transitions_by_event.get(event, [])

    def is_valid_transition(self, from_state: str, to_state: str, event: str) -> bool:
        """Check if a specific transition is valid"""
        valid_transitions = self.get_valid_transitions_from_state(from_state)
        for transition in valid_transitions:
            if transition.to_state == to_state and transition.event == event:
                return True
        return False

    def get_transition_description(self, from_state: str, to_state: str, event: str) -> Optional[str]:
        """Get description for a specific transition"""
        valid_transitions = self.get_valid_transitions_from_state(from_state)
        for transition in valid_transitions:
            if transition.to_state == to_state and transition.event == event:
                return transition.description
        return None

    def validate_state_machine(self, states: List[str], events: List[str]) -> Dict[str, List[str]]:
        """Validate the state machine configuration"""
        issues = {
            'invalid_states': [],
            'invalid_events': [],
            'unreachable_states': [],
            'orphaned_events': []
        }

        # Check for invalid states in transitions
        used_states = set()
        used_events = set()

        for group in self.transition_groups:
            for transition in group.transitions:
                used_states.add(transition.from_state)
                used_states.add(transition.to_state)
                used_events.add(transition.event)

                if transition.from_state not in states:
                    issues['invalid_states'].append(transition.from_state)
                if transition.to_state not in states:
                    issues['invalid_states'].append(transition.to_state)
                if transition.event not in events:
                    issues['invalid_events'].append(transition.event)

        # Check for unreachable states
        reachable_states = set(['INITIAL'])  # INITIAL is always reachable
        changed = True
        while changed:
            changed = False
            for group in self.transition_groups:
                for transition in group.transitions:
                    if transition.from_state in reachable_states and transition.to_state not in reachable_states:
                        reachable_states.add(transition.to_state)
                        changed = True

        for state in states:
            if state not in reachable_states:
                issues['unreachable_states'].append(state)

        # Check for orphaned events
        for event in events:
            if event not in used_events:
                issues['orphaned_events'].append(event)

        return issues

    def generate_dot_graph(self) -> str:
        """Generate a Graphviz DOT graph of the state transitions"""
        dot_lines = [
            "digraph StateTransitions {",
            "  rankdir=TD;",
            "  node [shape=box, style=rounded];",
        ]

        # Add color coding by group
        colors = ["red", "blue", "green", "orange", "purple", "brown", "pink", "gray"]

        for i, group in enumerate(self.transition_groups):
            color = colors[i % len(colors)]
            dot_lines.append(f"  // {group.name}")

            for transition in group.transitions:
                label = f"{transition.event}"
                if transition.description:
                    label += f"\\n{transition.description}"

                dot_lines.append(
                    f'  "{transition.from_state}" -> "{transition.to_state}" '
                    f'[label="{label}", color={color}];'
                )

        dot_lines.append("}")
        return "\n".join(dot_lines)

    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about the state machine"""
        stats = {
            'total_groups': len(self.transition_groups),
            'total_transitions': sum(len(group.transitions) for group in self.transition_groups),
            'unique_states': len(set().union(*[
                {t.from_state, t.to_state} for group in self.transition_groups for t in group.transitions
            ])),
            'unique_events': len(set().union(*[
                {t.event} for group in self.transition_groups for t in group.transitions
            ]))
        }

        return stats
