#!/usr/bin/python3

import asyncio
import socket
import struct
import binascii
import time
import sys


MCAST_GRP     = '224.1.1.1' 
MCAST_ADDR_V6 = 'FF02::1' 
MCAST_PORT    = 5007

TTL = 2

MSG = b""

v4_rx_fd = None
v6_tx_fd = None

v6_rx_fd = None
v6_tx_fd = None



def init_v4_rx_fd():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(sock, "SO_REUSEPORT"):
        self.setsockopt(sock.SOL_SOCKET, sock.SO_REUSEPORT, 1)
    
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    
    sock.bind(('', MCAST_PORT))
    host = socket.gethostbyname(socket.gethostname())
    sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))

    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def init_v4_tx_fd():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, TTL)
    return sock


def init_v6_rx_fd():
    addrinfo = socket.getaddrinfo(MCAST_ADDR_V6, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(sock, "SO_REUSEPORT"):
        self.setsockopt(sock.SOL_SOCKET, sock.SO_REUSEPORT, 1)
    sock.bind(('', MCAST_PORT))
    group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
    mreq = group_bin + struct.pack('@I', 0)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
    return sock

def init_v6_tx_fd():
    addrinfo = socket.getaddrinfo(MCAST_ADDR_V6, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, TTL)
    return sock


def cb_v4_rx():
    try:
        data, addr = v4_rx_fd.recvfrom(1024)
    except socket.error as e:
        print('Expection')
    print("Messagr from: {}:{}".format(str(addr[0]), str(addr[1])))
    print("Message: {!r}".format(data.decode()))

def cb_v6_rx():
    try:
        data, addr = v6_rx_fd.recvfrom(1024)
    except socket.error as e:
        print('Expection')
    print("Messagr from: {}:{}".format(str(addr[0]), str(addr[1])))
    print("Message: {!r}".format(data.decode()))

@asyncio.coroutine
def tx_v4():
    while True:
        try:
            v4_tx_fd.sendto(MSG, (MCAST_GRP, MCAST_PORT))
        except Exception as e:
            print(str(e))
        yield from asyncio.sleep(2)

@asyncio.coroutine
def tx_v6():
    while True:
        try:
            v6_tx_fd.sendto(MSG, (MCAST_ADDR_V6, MCAST_PORT))
        except Exception as e:
            print(str(e))
        yield from asyncio.sleep(2)


loop = asyncio.get_event_loop()

v4_rx_fd = init_v4_rx_fd()
loop.add_reader(v4_rx_fd, cb_v4_rx)

v6_rx_fd = init_v6_rx_fd()
loop.add_reader(v6_rx_fd, cb_v6_rx)

tx_work = []
v4_tx_fd = init_v4_tx_fd()
if v4_tx_fd:
    tx_work.append(tx_v4())
v6_tx_fd = init_v6_tx_fd()
if v6_tx_fd:
    tx_work.append(tx_v6())

loop.run_until_complete(asyncio.wait(tx_work))

loop.run_forever()

loop.close()

