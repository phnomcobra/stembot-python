"""Online Agent Configuration"""
import argparse
import time

from devtools import pprint

from stembot.executor.agent import ControlFormClient
from stembot.dao import kvstore
from stembot.models.control import DeletePeers, DiscoverPeer, GetPeers, GetRoutes

parser = argparse.ArgumentParser(description='Online Agent Configuration')

subparsers = parser.add_subparsers(help='commands')

discover_parser = subparsers.add_parser('discover', help='discover peer')
discover_parser.add_argument('peer_url', action='store', help='url')
discover_parser.add_argument('-p', dest='polling', action='store_true')
discover_parser.add_argument(
    '-d', dest='delay_secs', action='store', type=int,
    help='Delay making discovery request for n number of seconds'
)
discover_parser.add_argument(
    '--ttl', dest='ttl', action='store',
    help='time-to-live (seconds)', type=int
)

del_parser = subparsers.add_parser('del', help='delete peer')
del_parser.add_argument('--all', dest='del_all_agents', action='store_true')
del_parser.add_argument('--agtuuid', dest='del_agtuuid', action='store')

list_parser = subparsers.add_parser('list')
list_parser.add_argument('peers', action='store_true')
list_parser.add_argument('routes', action='store_true')

trace_parser = subparsers.add_parser('trace')
trace_parser.add_argument(dest='trace_agtuuid', action='store')
trace_parser.add_argument('-t', dest='timeout_secs', action='store', default=15, type=int)

ping_parser = subparsers.add_parser('ping')
ping_parser.add_argument(dest='ping_agtuuid', action='store')
ping_parser.add_argument('-t', dest='timeout_secs', action='store', default=15, type=int)
ping_parser.add_argument('-c', dest='continuous', action='store_true')


def main():
    kargs = vars(parser.parse_args())

    client = ControlFormClient(
        url=kvstore.get('client_control_url'),
        secret_digest=kvstore.get('secret_digest')
    )

    if 'peer_url' in kargs:
        if delay_secs := kargs['delay_secs']:
            time.sleep(delay_secs)

        pprint(client.send_control_form(DiscoverPeer(
            url=kargs['peer_url'],
            polling=kargs['polling'],
            ttl=kargs['ttl'],
        )))

    if 'del_all_agents' in kargs:
        pprint(client.send_control_form(DeletePeers()))

    if 'del_agtuuid' in kargs:
        pprint(client.send_control_form(DeletePeers(agtuuids=[kargs['del_agtuuid']])))

    if kargs.get('peers'):
        pprint(client.send_control_form(GetPeers()))

    if kargs.get('routes'):
        pprint(client.send_control_form(GetRoutes()))

if __name__ == '__main__':
    main()
