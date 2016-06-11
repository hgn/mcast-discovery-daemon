#!/usr/bin/python3

import asyncio
import socket
import struct
import binascii
import time
import sys
import functools
import argparse


MCAST_ADDR_V4     = '224.1.1.1' 
MCAST_ADDR_V6 = 'FF02::1' 
DEFAULT_PORT    = 5007


def init_v4_rx_fd(port=DEFAULT_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(sock, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    
    sock.bind(('', port))
    host = socket.gethostbyname(socket.gethostname())
    sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))

    mreq = struct.pack("4sl", socket.inet_aton(MCAST_ADDR_V4), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


def init_v4_tx_fd(ttl):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    return sock


def init_v6_rx_fd(port=DEFAULT_PORT):
    addrinfo = socket.getaddrinfo(MCAST_ADDR_V6, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(sock, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(('', port))
    group_bin = socket.inet_pton(addrinfo[0], addrinfo[4][0])
    mreq = group_bin + struct.pack('@I', 0)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, mreq)
    return sock


def init_v6_tx_fd(ttl):
    addrinfo = socket.getaddrinfo(MCAST_ADDR_V6, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_HOPS, ttl)
    return sock


def cb_v4_rx(fd):
    try:
        data, addr = fd.recvfrom(1024)
    except socket.error as e:
        print('Expection')
    print("Messagr from: {}:{}".format(str(addr[0]), str(addr[1])))
    print("Message: {!r}".format(data.decode()))


def cb_v6_rx(fd):
    try:
        data, addr = fd.recvfrom(1024)
    except socket.error as e:
        print('Expection')
    print("Messagr from: {}:{}".format(str(addr[0]), str(addr[1])))
    print("Message: {!r}".format(data.decode()))


async def tx_v4(fd, port=DEFAULT_PORT):
    while True:
        try:
            fd.sendto(b'', (MCAST_ADDR_V4, port))
        except Exception as e:
            print(str(e))
        await asyncio.sleep(2)


async def tx_v6(fd, port=DEFAULT_PORT):
    while True:
        try:
            fd.sendto(b'', (MCAST_ADDR_V6, port))
        except Exception as e:
            print(str(e))
        await asyncio.sleep(2)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("--ttl", help="IPv{4,6} TTL for transmission (default: 2)", type=int, default=2)
    parser.add_argument("--port", help="TX/RX port (default: {})".format(DEFAULT_PORT), type=int, default=DEFAULT_PORT)
    return parser.parse_args()

def main():
    args = parse_args()

    loop = asyncio.get_event_loop()

    # RX functionality
    fd = init_v4_rx_fd(port=args.port)
    loop.add_reader(fd, functools.partial(cb_v4_rx, fd))

    fd = init_v6_rx_fd(port=args.port)
    loop.add_reader(fd, functools.partial(cb_v6_rx, fd))

    # TX side
    fd = init_v4_tx_fd(ttl=args.ttl)
    asyncio.ensure_future(tx_v4(fd, port=args.port))

    fd = init_v6_tx_fd(ttl=args.ttl)
    asyncio.ensure_future(tx_v6(fd, port=args.port))

    # start it
    loop.run_forever()
    loop.close()


if __name__ == "__main__":
    main()
