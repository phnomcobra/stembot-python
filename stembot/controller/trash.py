def __process_old(message):
    ctr_increment('messages processed')

    if message['dest'] == cherrypy.config.get('agtuuid'):
        logging.debug(message['type'])
        if message['type'] == 'create peer':
            if 'url' in message:
                url = message['url']
            else:
                url = None

            if 'ttl' in message:
                ttl = message['ttl']
            else:
                ttl = None

            if 'polling' in message:
                polling = message['polling']
            else:
                polling = False

            create_peer(
                message['agtuuid'],
                url=url,
                ttl=ttl,
                polling=polling
            )

            return message

        elif message['type'] == 'delete peers':
            delete_peers()
            return message

        elif message['type'] == 'delete peer':
            delete_peer(message['agtuuid'])
            return message

        elif message['type'] == 'get peers':
            return get_peers()

        elif message['type'] == 'get routes':
            return get_routes()

        elif message['type'] == 'route advertisement':
            process_route_advertisement(message)
            return message

        elif message['type'] == 'discover peer':
            if 'ttl' in message:
                ttl = message['ttl']
            else:
                ttl = None

            if 'polling' in message:
                polling = message['polling']
            else:
                polling = False

            return discover_peer(
                message['url'],
                ttl=ttl,
                polling=polling
            )




        elif message['type'] == 'create info event':
            return message




        elif message['type'] == 'get counters':
            return ctr_get_all()




        elif message['type'] == 'pull messages':
            st = time()

            messages = pull_messages(message['isrc'])

            while len(messages) == 0 and \
                  time() - st < 5.0:
                sleep(0.5)

                messages = pull_messages(message['isrc'])

            return messages




        elif message['type'] == 'ticket request':
            process(process_ticket(message))
            return message

        elif message['type'] == 'ticket response':
            service_ticket(message)
            return message

        elif message['type'] == 'create sync ticket':
            ticket_message = create_ticket(message['request'])
            forward(ticket_message)
            if 'timeout' in message:
                return wait_on_ticket_response(ticket_message['tckuuid'], message['timeout'])
            else:
                return wait_on_ticket_response(ticket_message['tckuuid'])

        elif message['type'] == 'create async ticket':
            ticket_message = create_ticket(message['request'])
            logging.debug(ticket_message)
            forward(ticket_message)
            return ticket_message

        elif message['type'] == 'get ticket response':
            return get_ticket_response(message['tckuuid'])

        elif message['type'] == 'delete ticket':
            delete_ticket(message['tckuuid'])
            return message




        elif message['type'] == 'cascade request':
            process_cascade_request(message)
            return message

        elif message['type'] == 'cascade response':
            service_cascade_request(message)
            return message

        elif message['type'] == 'create cascade sync':
            if 'timeout' in message:
                return wait_on_cascade_responses(create_cascade_request(message)['cscuuid'], message['timeout'])
            else:
                return wait_on_cascade_responses(create_cascade_request(message)['cscuuid'])
    else:
        forward(message)
        return message

def discover_peer(url, ttl, polling):
    message_in = {
        'type': 'create info event',
        'message': 'Agent Hello'
    }

    message_out = MPIClient(
        url,
        cherrypy.config.get('server.secret_digest')
    ).send_json(message_in)

    peer = create_peer(
        message_out['dest'],
        url=url,
        ttl=ttl,
        polling=polling
    )

    return peer.object
