#!/usr/bin/python3

"""
Watch handover signals of the pcap stream and update interface ip

Output csv format to stdout.
"""

import pyshark
import os
import time
from struct import unpack
import select
import ho

_pipe = "/tmp/pcap_buffer"


def get_packet(fd: int) -> (bytes, bytes):
    ts, pkt_size = unpack("<II", os.read(fd, 8))
    return ts, os.read(fd, pkt_size)


def loop():
    imc = pyshark.InMemCapture(linktype=228, custom_parameters={"-J": "lte_rrc"})

    source = os.open(_pipe, os.O_RDONLY | os.O_NONBLOCK)

    poll = select.poll()
    poll.register(source, select.POLLIN)

    _ip_base = "172.17.0."
    _ip_pool = iter(range(5, 128))
    handover_start = False
    handover_complete = False
    cell_id = None

    test_mode = os.getenv('TEST_SETUP')
    if test_mode == None or not (test_mode in ['mptcp', 'tcpwo', 'tcp', 'sip', 'sipwo']):
        print("TEST_SETUP env variable not set")
        return 
    else:
        print('Test mode: {}'.format(test_mode))

    while True:
        if (source, select.POLLIN) in poll.poll(2000):  # 2s
            ts, pkt = get_packet(source)
        else:
            continue

        pkt = imc.parse_packet(pkt)
        # print("timestamp:", ts, pkt, dir(pkt.lte_rrc))

        # cell id
        new_cell_id = None
        try:
            new_cell_id = pkt.lte_rrc.lte_rrc_physcellid
        except AttributeError:
            pass

        if new_cell_id != None:
            cell_id = new_cell_id

        # Check handover completes
        if handover_start:
            handover_complete = False
            try:
                handover_complete = pkt.lte_rrc.lte_rrc_rrcconnectionreconfigurationcomplete_element == 'rrcConnectionReconfigurationComplete'
            except AttributeError:
                pass

            # Record
            if handover_complete:
                print("***** Handover completes! *****")
                try:
                    ip = _ip_base + str(next(_ip_pool))
                except StopIteration:
                    _ip_pool = iter(range(5, 128))
                    ip = _ip_base + str(next(_ip_pool))

                if not (test_mode in ['tcpwo','sipwo']):
                    #ho.do(new_ip=ip, lat=32.072 * 1e-3, name="uec_new2")
                    ho.do(new_ip=ip, lat=96.0 * 1e-3, name="uec_new2") 

            handover_start = False

        # handover start
        try:
            handover_start = pkt.lte_rrc.lte_rrc_mobilitycontrolinfo_element == 'mobilityControlInfo'
            if handover_start:
                print("***** Handover starts! *****")
        except AttributeError:
            pass

        # TBD which timestamp
        event = 'RRC'
        if handover_complete:
            event = 'HO_END'
        if handover_start:
            event = 'HO_START'

        print(time.time(), event, cell_id)

        # Reset handover completes
        if handover_complete:
            handover_complete = False


if __name__ == "__main__":
    loop()
