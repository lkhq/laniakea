/*  =========================================================================
    czmq_prelude.h - CZMQ environment

    Copyright (c) the Contributors as noted in the AUTHORS file.
    This file is part of CZMQ, the high-level C binding for 0MQ:
    http://czmq.zeromq.org.

    This Source Code Form is subject to the terms of the Mozilla Public
    License, v. 2.0. If a copy of the MPL was not distributed with this
    file, You can obtain one at http://mozilla.org/MPL/2.0/.
    =========================================================================
*/

import core.sys.posix.netinet.in_;

public import c.zmq.czmq_library;

extern (C):

//- Data types --------------------------------------------------------------

alias dbyte = ushort; //  Double byte = 16 bits
alias qbyte = uint; //  Quad byte = 32 bits
alias inaddr_t = sockaddr_in; //  Internet socket address structure
alias in6addr_t = sockaddr_in6; //  Internet 6 socket address structure

// Common structure to hold inaddr_t and in6addr_t with length
struct inaddr_storage_t
{
    //  IPv4 address
    //  IPv6 address
    union AddrUnion
    {
        inaddr_t __addr;
        in6addr_t __addr6;
    }

    AddrUnion __inaddr_u;

    alias ipv4addr = __inaddr_u.__addr;
    alias ipv6addr = __inaddr_u.__addr6;

    int inaddrlen;
}



//- Inevitable macros -------------------------------------------------------

extern (D) auto streq(T0, T1)(auto ref T0 s1, auto ref T1 s2)
{
    return !strcmp(s1, s2);
}

extern (D) auto strneq(T0, T1)(auto ref T0 s1, auto ref T1 s2)
{
    return strcmp(s1, s2);
}

//  Provide random number from 0..(num-1)
//  Note that (at least in Solaris) while rand() returns an int limited by
//  RAND_MAX, random() returns a 32-bit value all filled with random bits.

extern (D) auto randof(T)(auto ref T num)
{
    return cast(int) cast(float) num * (random() % RAND_MAX) / (RAND_MAX + 1.0);
}

// Windows MSVS doesn't have stdbool

//- A number of POSIX and C99 keywords and data types -----------------------
//  CZMQ uses uint for array indices; equivalent to unsigned int, but more
//  convenient in code. We define it in czmq_prelude.h on systems that do
//  not define it by default.

//  MSVC does not support C99's va_copy so we use a regular assignment

//  This fixes header-order dependence problem with some Linux versions

//- Non-portable declaration specifiers -------------------------------------

//  For thread-local storage

//  Replacement for malloc() which asserts if we run out of heap, and
//  which zeroes the allocated block.

//     printf ("%s:%u %08d\n", file, line, (int) size);
void* safe_malloc (size_t size, const(char)* file, uint line);

//  Define _ZMALLOC_DEBUG if you need to trace memory leaks using e.g. mtrace,
//  otherwise all allocations will claim to come from czmq_prelude.h. For best
//  results, compile all classes so you see dangling object allocations.
//  _ZMALLOC_PEDANTIC does the same thing, but its intention is to propagate
//  out of memory condition back up the call stack.

extern (D) auto zmalloc(T)(auto ref T size)
{
    return safe_malloc(size, __FILE__, __LINE__);
}

//  GCC supports validating format strings for functions that act like printf

//  Lets us write code that compiles both on Windows and normal platforms

alias SOCKET = int;
enum INVALID_SOCKET = -1;
enum SOCKET_ERROR = -1;
enum O_BINARY = 0;

//- Include non-portable header files based on platform.h -------------------

//  This would normally come from net/if.h

//  ZMQ compatibility macros

enum ZMQ_POLL_MSEC = 1; //  zmq_poll is msec

//  zmq_poll is msec

//  zmq_poll is usec
//  Smooth out 2.x changes

//  Older libzmq APIs may be missing some aspects of libzmq v3.0

