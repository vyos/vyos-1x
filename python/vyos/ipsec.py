# Copyright 2020-2023 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

#Package to communicate with Strongswan VICI

class ViciInitiateError(Exception):
    """
        VICI can't initiate a session.
    """
    pass
class ViciCommandError(Exception):
    """
        VICI can't execute a command by any reason.
    """
    pass

def get_vici_sas():
    from vici import Session as vici_session

    try:
        session = vici_session()
    except Exception:
        raise ViciInitiateError("IPsec not initialized")
    sas = list(session.list_sas())
    return sas


def get_vici_connections():
    from vici import Session as vici_session

    try:
        session = vici_session()
    except Exception:
        raise ViciInitiateError("IPsec not initialized")
    connections = list(session.list_conns())
    return connections


def get_vici_sas_by_name(ike_name: str, tunnel: str) -> list:
    """
    Find sas by IKE_SA name and/or CHILD_SA name
    and return list of OrdinaryDicts with SASs info
    If tunnel is not None return value is list of OrdenaryDicts contained only
    CHILD_SAs wich names equal tunnel value.
    :param ike_name: IKE SA name
    :type ike_name: str
    :param tunnel: CHILD SA name
    :type tunnel: str
    :return: list of Ordinary Dicts with SASs
    :rtype: list
    """
    from vici import Session as vici_session

    try:
        session = vici_session()
    except Exception:
        raise ViciInitiateError("IPsec not initialized")
    vici_dict = {}
    if ike_name:
        vici_dict['ike'] = ike_name
    if tunnel:
        vici_dict['child'] = tunnel
    try:
        sas = list(session.list_sas(vici_dict))
        return sas
    except Exception:
        raise ViciCommandError(f'Failed to get SAs')


def terminate_vici_ikeid_list(ike_id_list: list) -> None:
    """
    Terminate IKE SAs by their id that contained in the list
    :param ike_id_list: list of IKE SA id
    :type ike_id_list: list
    """
    from vici import Session as vici_session

    try:
        session = vici_session()
    except Exception:
        raise ViciInitiateError("IPsec not initialized")
    try:
        for ikeid in ike_id_list:
            session_generator = session.terminate(
                {'ike-id': ikeid, 'timeout': '-1'})
            # a dummy `for` loop is required because of requirements
            # from vici. Without a full iteration on the output, the
            # command to vici may not be executed completely
            for _ in session_generator:
                pass
    except Exception:
        raise ViciCommandError(
            f'Failed to terminate SA for IKE ids {ike_id_list}')


def terminate_vici_by_name(ike_name: str, child_name: str) -> None:
    """
    Terminate IKE SAs by name if CHILD SA name is None.
    Terminate CHILD SAs by name if CHILD SA name is specified
    :param ike_name: IKE SA name
    :type ike_name: str
    :param child_name: CHILD SA name
    :type child_name: str
    """
    from vici import Session as vici_session

    try:
        session = vici_session()
    except Exception:
        raise ViciInitiateError("IPsec not initialized")
    try:
        vici_dict: dict= {}
        if ike_name:
            vici_dict['ike'] = ike_name
        if child_name:
            vici_dict['child'] = child_name
        session_generator = session.terminate(vici_dict)
        # a dummy `for` loop is required because of requirements
        # from vici. Without a full iteration on the output, the
        # command to vici may not be executed completely
        for _ in session_generator:
            pass
    except Exception:
        if child_name:
            raise ViciCommandError(
                f'Failed to terminate SA for IPSEC {child_name}')
        else:
            raise ViciCommandError(
                f'Failed to terminate SA for IKE {ike_name}')
