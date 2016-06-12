#!/usr/bin/python3
# -*- coding: utf-8 -*- 

import asyncio
import socket
import struct
import binascii
import time
import sys
import functools
import argparse
import signal
import os


MCAST_ADDR_V4 = '224.0.0.1' 
MCAST_ADDR_V6 = 'FF02::1' 
DEFAULT_PORT  = 5007
DEFAULT_INTERVAL = 5.0

# don't recognize own mcast transmissions
# by default, can be changed for debugging
MCAST_LOOP = 0

# For communication with separated thread (e.g. to use dbus-glib)
# janus queue can be used: https://pypi.python.org/pypi/janus


def init_v4_rx_fd(addr=None, port=DEFAULT_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(sock, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, MCAST_LOOP)
    
    sock.bind(('', port))
    host = socket.gethostbyname(socket.gethostname())
    sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(host))

    mreq = struct.pack("4sl", socket.inet_aton(addr), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock


def init_v4_tx_fd(ttl, addr=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    if addr:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(addr))
    return sock


def init_v6_rx_fd(addr=None, port=DEFAULT_PORT):
    addrinfo = socket.getaddrinfo(addr, None)[0]
    sock = socket.socket(addrinfo[0], socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(sock, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_MULTICAST_LOOP, MCAST_LOOP)

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


def cb_v4_rx(fd, queue):
    try:
        data, addr = fd.recvfrom(1024)
    except socket.error as e:
        print('Expection')
    d = []
    d.append("v4")
    d.append(data)
    d.append(addr)
    #print("Messagr from: {}:{}".format(str(addr[0]), str(addr[1])))
    #print("Message: {!r}".format(data.decode()))
    try:
        queue.put_nowait(d)
    except asyncio.queues.QueueFull:
        sys.stderr.write("queue overflow, strange things happens")


def cb_v6_rx(fd, queue):
    try:
        data, addr = fd.recvfrom(1024)
    except socket.error as e:
        print('Expection')
    d = []
    d.append("v6")
    d.append(data)
    d.append(addr)
    try:
        queue.put_nowait(d)
    except asyncio.queues.QueueFull:
        sys.stderr.write("queue overflow, strange things happens")


async def tx_v4(fd, addr=None, port=DEFAULT_PORT, interval=None):
    while True:
        try:
            fd.sendto(b'', (addr, port))
        except Exception as e:
            print(str(e))
        await asyncio.sleep(interval)


async def tx_v6(fd, addr=None, port=DEFAULT_PORT, interval=None):
    while True:
        try:
            fd.sendto(b'', (addr, port))
        except Exception as e:
            print(str(e))
        await asyncio.sleep(interval)


def update_db(db, msg):
    proto = msg[0]; data = msg[1]; addr = msg[2]
    if addr not in db:
        db[addr] = dict()
        db[addr]['first-seen'] = time.time()
        db[addr]['received-messages'] = 0
    db[addr]['last-seen'] = time.time()
    db[addr]['received-messages'] += 1



def display_time(seconds, granularity=2):
    result = []
    intervals = (
            ('weeks', 604800),
            ('days',   86400),
            ('hours',   3600),
            ('minutes',   60),
            ('seconds',    1),
    )

    if seconds <= 1.0:
        return "just now"

    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {} ago".format(value, name))
    return ', '.join(result[:granularity])


def print_db(db):
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    
    if not sys.stdout.isatty():
        HEADER = OKBLUE = OKGREEN = WARNING = FAIL = ENDC = ''

    print("\033c")
    sys.stdout.write("{}Number of Neighbors: {}{} (may include"
                     " this host too, multiple source addresses"
                     " possible)\n\n".format(WARNING, len(db), ENDC))
    for key, value in db.items():
        sys.stdout.write("{}{}{}\n".format(OKGREEN, key[0], ENDC))
        now = time.time()
        last_seen_delta = display_time(now - value['last-seen'])
        fist_seen_delta = display_time(now - value['first-seen'])
        sys.stdout.write("\tLast seen:  {}\n".format(last_seen_delta))
        sys.stdout.write("\tFirst seen: {}\n".format(fist_seen_delta))
        sys.stdout.write("\tReceived messages: {}\n".format(value['received-messages']))
        print("\n")


async def print_stats(queue):
    db = dict()
    while True:
        entry = await queue.get()
        update_db(db, entry)
        print_db(db)


def ask_exit(signame, loop):
    sys.stderr.write("got signal %s: exit\n" % signame)
    loop.stop()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--v4addr", help="IPv4 mcast address (default: {})".format(MCAST_ADDR_V4), type=str, default=MCAST_ADDR_V4)
    parser.add_argument("--v4outaddr", help="IPv4 outgoing interface address (default: {})".format("None"), type=str, default=None)
    parser.add_argument("--v6addr", help="IPv6 mcast address (default: {})".format(MCAST_ADDR_V6), type=str, default=MCAST_ADDR_V6)
    parser.add_argument("--port", help="TX/RX port (default: {})".format(DEFAULT_PORT), type=int, default=DEFAULT_PORT)
    parser.add_argument("--ttl", help="IPv{4,6} TTL for transmission (default: 2)", type=int, default=2)
    parser.add_argument("-i", "--interval", help="Time between transmission (default: {})".format(DEFAULT_INTERVAL), type=float, default=DEFAULT_INTERVAL)
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    loop = asyncio.get_event_loop()
    queue = asyncio.Queue(32)

    # RX functionality
    fd = init_v4_rx_fd(addr=args.v4addr, port=args.port)
    loop.add_reader(fd, functools.partial(cb_v4_rx, fd, queue))

    fd = init_v6_rx_fd(addr=args.v6addr, port=args.port)
    loop.add_reader(fd, functools.partial(cb_v6_rx, fd, queue))

    # TX side
    fd = init_v4_tx_fd(ttl=args.ttl, addr=args.v4outaddr)
    asyncio.ensure_future(tx_v4(fd, addr=args.v4addr, port=args.port, interval=args.interval))

    fd = init_v6_tx_fd(ttl=args.ttl)
    asyncio.ensure_future(tx_v6(fd, addr=args.v6addr, port=args.port, interval=args.interval))

    # Outputter
    asyncio.ensure_future(print_stats(queue))

    for signame in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, signame),
                                functools.partial(ask_exit, signame, loop))

    try:
        loop.run_forever()
    finally:
        loop.close()


if __name__ == "__main__":
    main()
