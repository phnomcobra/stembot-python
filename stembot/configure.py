"""Offline Agent Configuration"""
import argparse
import hashlib
import os

from stembot.dao import kvstore

parser = argparse.ArgumentParser(description='Offline Agent Configuration')

parser.add_argument(
    '-a', '--agtuuid', dest='agt_uuid', action='store', type=str,
    help='Agent identifier'
)

parser.add_argument(
    '-p', '--port', dest='agt_port', action='store', type=int,
    help='Server TCP port'
)

parser.add_argument(
    '-d', '--host', dest='agt_host', action='store', type=str,
    help='Server host address'
)

parser.add_argument(
    '-s', '--secret-text', dest='agt_secret', action='store', type=str, help='Encryption key'
)

parser.add_argument(
    '-l', '--log-path', dest='agt_log_path', action='store', type=str,
    help='Log output path'
)

parser.add_argument(
    '-v', dest='view_config', action='store_true',
    help='View current configuration settings'
)

parser.add_argument(
    '-e', dest='load_env', action='store_true',
    help='Load configuration settings from environment variables'
)

parser.add_argument(
    '-c', dest='agt_client_control_url', action='store', type=str,
    help='Set the agent client control url'
)

LOCAL_HOST_CLIENT_CONTROL_URL = f'''http://127.0.0.1:{kvstore.get('socket_port')}/control'''
parser.add_argument(
    '-cl', dest='agt_client_control_url', action='store_const',
    help='Set the agent client control url to the local host and port. ' \
         f'Example: {LOCAL_HOST_CLIENT_CONTROL_URL}',
    const=LOCAL_HOST_CLIENT_CONTROL_URL
)

def main():
    kwargs = vars(parser.parse_args())

    if kwargs['load_env']:
        if agtuuid := os.environ.get('AGT_UUID'):
            kvstore.commit('agtuuid', agtuuid)

        if socket_host := os.environ.get('AGT_HOST'):
            kvstore.commit('socket_host', socket_host)

        if socket_port := os.environ.get('AGT_PORT'):
            kvstore.commit('socket_port', int(socket_port))

        if log_path := os.environ.get('AGT_LOG_PATH'):
            kvstore.commit('log_path', log_path)

        if secret_text := os.environ.get('AGT_SECRET'):
            kvstore.commit('secret_digest', hashlib.sha256(secret_text.encode()).hexdigest())

        if client_control_url := os.environ.get('AGT_CLIENT_CONTROL_URL'):
            kvstore.commit('client_control_url', client_control_url)

    if agtuuid := kwargs['agt_uuid']:
        kvstore.commit('agtuuid', agtuuid)

    if socket_host := kwargs['agt_host']:
        kvstore.commit('socket_host', socket_host)

    if socket_port := kwargs['agt_port']:
        kvstore.commit('socket_port', socket_port)

    if log_path := kwargs['agt_log_path']:
        kvstore.commit('log_path', log_path)

    if secret_text := kwargs['agt_secret']:
        kvstore.commit('secret_digest', hashlib.sha256(secret_text.encode()).hexdigest())

    if client_control_url := kwargs['agt_client_control_url']:
        kvstore.commit('client_control_url', client_control_url)

    if kwargs['view_config']:
        print('client control url:', kvstore.get('client_control_url'))
        print('          agent id:', kvstore.get('agtuuid'))
        print('              host:', kvstore.get('socket_host'))
        print('              port:', kvstore.get('socket_port'))
        print('          log path:', kvstore.get('log_path'))
        print('     secret digest:', kvstore.get('secret_digest'))

if __name__ == '__main__':
    main()
