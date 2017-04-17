/*
    Copyright (c) 2007-2016 Contributors as noted in the AUTHORS file

    This file is part of libzmq, the ZeroMQ core engine in C++.

    libzmq is free software; you can redistribute it and/or modify it under
    the terms of the GNU Lesser General Public License (LGPL) as published
    by the Free Software Foundation; either version 3 of the License, or
    (at your option) any later version.

    As a special exception, the Contributors give you permission to link
    this library with independent modules to produce an executable,
    regardless of the license terms of these independent modules, and to
    copy and distribute the resulting executable under terms of your choice,
    provided that you also meet, for each linked independent module, the
    terms and conditions of the license of that module. An independent
    module is a module which is not derived from or based on this library.
    If you modify this library, you must extend this exception to your
    version of the library.

    libzmq is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
    License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

    *************************************************************************
    NOTE to contributors. This file comprises the principal public contract
    for ZeroMQ API users. Any change to this file supplied in a stable
    release SHOULD not break existing applications.
    In practice this means that the value of constants must not change, and
    that old values may not be reused for new constants.
    *************************************************************************
*/

import core.stdc.config;

extern (C):

/*  Version macros for compile-time API version detection                     */
enum ZMQ_VERSION_MAJOR = 4;
enum ZMQ_VERSION_MINOR = 2;
enum ZMQ_VERSION_PATCH = 1;

extern (D) auto ZMQ_MAKE_VERSION(T0, T1, T2)(auto ref T0 major, auto ref T1 minor, auto ref T2 patch)
{
    return major * 10000 + minor * 100 + patch;
}

enum ZMQ_VERSION = ZMQ_MAKE_VERSION(ZMQ_VERSION_MAJOR, ZMQ_VERSION_MINOR, ZMQ_VERSION_PATCH);

//  Set target version to Windows Server 2008, Windows Vista or higher.
//  Windows XP (0x0501) is supported but without client & server socket types.

//  Require Windows XP or higher with MinGW for getaddrinfo().

/*  Handle DSO symbol visibility                                             */

/*  Define integer types needed for event interface                          */
enum ZMQ_DEFINED_STDINT = 1;

//  32-bit AIX's pollfd struct members are called reqevents and rtnevents so it
//  defines compatibility macros for them. Need to include that header first to
//  stop build failures since zmq_pollset_t defines them as events and revents.

/******************************************************************************/
/*  0MQ errors.                                                               */
/******************************************************************************/

/*  A number random enough not to collide with different errno ranges on      */
/*  different OSes. The assumption is that error_t is at least 32-bit type.   */
enum ZMQ_HAUSNUMERO = 156384712;

/*  On Windows platform some of the standard POSIX errnos are not defined.    */

/*  Native 0MQ error codes.                                                   */
enum EFSM = ZMQ_HAUSNUMERO + 51;
enum ENOCOMPATPROTO = ZMQ_HAUSNUMERO + 52;
enum ETERM = ZMQ_HAUSNUMERO + 53;
enum EMTHREAD = ZMQ_HAUSNUMERO + 54;

/*  This function retrieves the errno as it is known to 0MQ library. The goal */
/*  of this function is to make the code 100% portable, including where 0MQ   */
/*  compiled with certain CRT library (on Windows) is linked to an            */
/*  application that uses different CRT library.                              */
int zmq_errno ();

/*  Resolves system errors and 0MQ errors to human-readable string.           */
const(char)* zmq_strerror (int errnum);

/*  Run-time API version detection                                            */
void zmq_version (int* major, int* minor, int* patch);

/******************************************************************************/
/*  0MQ infrastructure (a.k.a. context) initialisation & termination.         */
/******************************************************************************/

/*  Context options                                                           */
enum ZMQ_IO_THREADS = 1;
enum ZMQ_MAX_SOCKETS = 2;
enum ZMQ_SOCKET_LIMIT = 3;
enum ZMQ_THREAD_PRIORITY = 3;
enum ZMQ_THREAD_SCHED_POLICY = 4;
enum ZMQ_MAX_MSGSZ = 5;

/*  Default for new contexts                                                  */
enum ZMQ_IO_THREADS_DFLT = 1;
enum ZMQ_MAX_SOCKETS_DFLT = 1023;
enum ZMQ_THREAD_PRIORITY_DFLT = -1;
enum ZMQ_THREAD_SCHED_POLICY_DFLT = -1;

void* zmq_ctx_new ();
int zmq_ctx_term (void* context);
int zmq_ctx_shutdown (void* context);
int zmq_ctx_set (void* context, int option, int optval);
int zmq_ctx_get (void* context, int option);

/*  Old (legacy) API                                                          */
void* zmq_init (int io_threads);
int zmq_term (void* context);
int zmq_ctx_destroy (void* context);

/******************************************************************************/
/*  0MQ message definition.                                                   */
/******************************************************************************/

/* Some architectures, like sparc64 and some variants of aarch64, enforce pointer
 * alignment and raise sigbus on violations. Make sure applications allocate
 * zmq_msg_t on addresses aligned on a pointer-size boundary to avoid this issue.
 */
struct zmq_msg_t
{
    ubyte[64] _;
}

alias zmq_free_fn = void function (void* data, void* hint);

int zmq_msg_init (zmq_msg_t* msg);
int zmq_msg_init_size (zmq_msg_t* msg, size_t size);
int zmq_msg_init_data (
    zmq_msg_t* msg,
    void* data,
    size_t size,
    void function () ffn,
    void* hint);
int zmq_msg_send (zmq_msg_t* msg, void* s, int flags);
int zmq_msg_recv (zmq_msg_t* msg, void* s, int flags);
int zmq_msg_close (zmq_msg_t* msg);
int zmq_msg_move (zmq_msg_t* dest, zmq_msg_t* src);
int zmq_msg_copy (zmq_msg_t* dest, zmq_msg_t* src);
void* zmq_msg_data (zmq_msg_t* msg);
size_t zmq_msg_size (zmq_msg_t* msg);
int zmq_msg_more (zmq_msg_t* msg);
int zmq_msg_get (zmq_msg_t* msg, int property);
int zmq_msg_set (zmq_msg_t* msg, int property, int optval);
const(char)* zmq_msg_gets (zmq_msg_t* msg, const(char)* property);

/******************************************************************************/
/*  0MQ socket definition.                                                    */
/******************************************************************************/

/*  Socket types.                                                             */
enum ZMQ_PAIR = 0;
enum ZMQ_PUB = 1;
enum ZMQ_SUB = 2;
enum ZMQ_REQ = 3;
enum ZMQ_REP = 4;
enum ZMQ_DEALER = 5;
enum ZMQ_ROUTER = 6;
enum ZMQ_PULL = 7;
enum ZMQ_PUSH = 8;
enum ZMQ_XPUB = 9;
enum ZMQ_XSUB = 10;
enum ZMQ_STREAM = 11;

/*  Deprecated aliases                                                        */
enum ZMQ_XREQ = ZMQ_DEALER;
enum ZMQ_XREP = ZMQ_ROUTER;

/*  Socket options.                                                           */
enum ZMQ_AFFINITY = 4;
enum ZMQ_IDENTITY = 5;
enum ZMQ_SUBSCRIBE = 6;
enum ZMQ_UNSUBSCRIBE = 7;
enum ZMQ_RATE = 8;
enum ZMQ_RECOVERY_IVL = 9;
enum ZMQ_SNDBUF = 11;
enum ZMQ_RCVBUF = 12;
enum ZMQ_RCVMORE = 13;
enum ZMQ_FD = 14;
enum ZMQ_EVENTS = 15;
enum ZMQ_TYPE = 16;
enum ZMQ_LINGER = 17;
enum ZMQ_RECONNECT_IVL = 18;
enum ZMQ_BACKLOG = 19;
enum ZMQ_RECONNECT_IVL_MAX = 21;
enum ZMQ_MAXMSGSIZE = 22;
enum ZMQ_SNDHWM = 23;
enum ZMQ_RCVHWM = 24;
enum ZMQ_MULTICAST_HOPS = 25;
enum ZMQ_RCVTIMEO = 27;
enum ZMQ_SNDTIMEO = 28;
enum ZMQ_LAST_ENDPOINT = 32;
enum ZMQ_ROUTER_MANDATORY = 33;
enum ZMQ_TCP_KEEPALIVE = 34;
enum ZMQ_TCP_KEEPALIVE_CNT = 35;
enum ZMQ_TCP_KEEPALIVE_IDLE = 36;
enum ZMQ_TCP_KEEPALIVE_INTVL = 37;
enum ZMQ_IMMEDIATE = 39;
enum ZMQ_XPUB_VERBOSE = 40;
enum ZMQ_ROUTER_RAW = 41;
enum ZMQ_IPV6 = 42;
enum ZMQ_MECHANISM = 43;
enum ZMQ_PLAIN_SERVER = 44;
enum ZMQ_PLAIN_USERNAME = 45;
enum ZMQ_PLAIN_PASSWORD = 46;
enum ZMQ_CURVE_SERVER = 47;
enum ZMQ_CURVE_PUBLICKEY = 48;
enum ZMQ_CURVE_SECRETKEY = 49;
enum ZMQ_CURVE_SERVERKEY = 50;
enum ZMQ_PROBE_ROUTER = 51;
enum ZMQ_REQ_CORRELATE = 52;
enum ZMQ_REQ_RELAXED = 53;
enum ZMQ_CONFLATE = 54;
enum ZMQ_ZAP_DOMAIN = 55;
enum ZMQ_ROUTER_HANDOVER = 56;
enum ZMQ_TOS = 57;
enum ZMQ_CONNECT_RID = 61;
enum ZMQ_GSSAPI_SERVER = 62;
enum ZMQ_GSSAPI_PRINCIPAL = 63;
enum ZMQ_GSSAPI_SERVICE_PRINCIPAL = 64;
enum ZMQ_GSSAPI_PLAINTEXT = 65;
enum ZMQ_HANDSHAKE_IVL = 66;
enum ZMQ_SOCKS_PROXY = 68;
enum ZMQ_XPUB_NODROP = 69;
enum ZMQ_BLOCKY = 70;
enum ZMQ_XPUB_MANUAL = 71;
enum ZMQ_XPUB_WELCOME_MSG = 72;
enum ZMQ_STREAM_NOTIFY = 73;
enum ZMQ_INVERT_MATCHING = 74;
enum ZMQ_HEARTBEAT_IVL = 75;
enum ZMQ_HEARTBEAT_TTL = 76;
enum ZMQ_HEARTBEAT_TIMEOUT = 77;
enum ZMQ_XPUB_VERBOSER = 78;
enum ZMQ_CONNECT_TIMEOUT = 79;
enum ZMQ_TCP_MAXRT = 80;
enum ZMQ_THREAD_SAFE = 81;
enum ZMQ_MULTICAST_MAXTPDU = 84;
enum ZMQ_VMCI_BUFFER_SIZE = 85;
enum ZMQ_VMCI_BUFFER_MIN_SIZE = 86;
enum ZMQ_VMCI_BUFFER_MAX_SIZE = 87;
enum ZMQ_VMCI_CONNECT_TIMEOUT = 88;
enum ZMQ_USE_FD = 89;

/*  Message options                                                           */
enum ZMQ_MORE = 1;
enum ZMQ_SHARED = 3;

/*  Send/recv options.                                                        */
enum ZMQ_DONTWAIT = 1;
enum ZMQ_SNDMORE = 2;

/*  Security mechanisms                                                       */
enum ZMQ_NULL = 0;
enum ZMQ_PLAIN = 1;
enum ZMQ_CURVE = 2;
enum ZMQ_GSSAPI = 3;

/*  RADIO-DISH protocol                                                       */
enum ZMQ_GROUP_MAX_LENGTH = 15;

/*  Deprecated options and aliases                                            */
enum ZMQ_TCP_ACCEPT_FILTER = 38;
enum ZMQ_IPC_FILTER_PID = 58;
enum ZMQ_IPC_FILTER_UID = 59;
enum ZMQ_IPC_FILTER_GID = 60;
enum ZMQ_IPV4ONLY = 31;
enum ZMQ_DELAY_ATTACH_ON_CONNECT = ZMQ_IMMEDIATE;
enum ZMQ_NOBLOCK = ZMQ_DONTWAIT;
enum ZMQ_FAIL_UNROUTABLE = ZMQ_ROUTER_MANDATORY;
enum ZMQ_ROUTER_BEHAVIOR = ZMQ_ROUTER_MANDATORY;

/*  Deprecated Message options                                                */
enum ZMQ_SRCFD = 2;

/******************************************************************************/
/*  0MQ socket events and monitoring                                          */
/******************************************************************************/

/*  Socket transport events (TCP, IPC and TIPC only)                          */

enum ZMQ_EVENT_CONNECTED = 0x0001;
enum ZMQ_EVENT_CONNECT_DELAYED = 0x0002;
enum ZMQ_EVENT_CONNECT_RETRIED = 0x0004;
enum ZMQ_EVENT_LISTENING = 0x0008;
enum ZMQ_EVENT_BIND_FAILED = 0x0010;
enum ZMQ_EVENT_ACCEPTED = 0x0020;
enum ZMQ_EVENT_ACCEPT_FAILED = 0x0040;
enum ZMQ_EVENT_CLOSED = 0x0080;
enum ZMQ_EVENT_CLOSE_FAILED = 0x0100;
enum ZMQ_EVENT_DISCONNECTED = 0x0200;
enum ZMQ_EVENT_MONITOR_STOPPED = 0x0400;
enum ZMQ_EVENT_ALL = 0xFFFF;

void* zmq_socket (void*, int type);
int zmq_close (void* s);
int zmq_setsockopt (void* s, int option, const(void)* optval, size_t optvallen);
int zmq_getsockopt (void* s, int option, void* optval, size_t* optvallen);
int zmq_bind (void* s, const(char)* addr);
int zmq_connect (void* s, const(char)* addr);
int zmq_unbind (void* s, const(char)* addr);
int zmq_disconnect (void* s, const(char)* addr);
int zmq_send (void* s, const(void)* buf, size_t len, int flags);
int zmq_send_const (void* s, const(void)* buf, size_t len, int flags);
int zmq_recv (void* s, void* buf, size_t len, int flags);
int zmq_socket_monitor (void* s, const(char)* addr, int events);

/******************************************************************************/
/*  I/O multiplexing.                                                         */
/******************************************************************************/

enum ZMQ_POLLIN = 1;
enum ZMQ_POLLOUT = 2;
enum ZMQ_POLLERR = 4;
enum ZMQ_POLLPRI = 8;

struct zmq_pollitem_t
{
    void* socket;

    int fd;

    short events;
    short revents;
}

enum ZMQ_POLLITEMS_DFLT = 16;

int zmq_poll (zmq_pollitem_t* items, int nitems, c_long timeout);

/******************************************************************************/
/*  Message proxying                                                          */
/******************************************************************************/

int zmq_proxy (void* frontend, void* backend, void* capture);
int zmq_proxy_steerable (void* frontend, void* backend, void* capture, void* control);

/******************************************************************************/
/*  Probe library capabilities                                                */
/******************************************************************************/

enum ZMQ_HAS_CAPABILITIES = 1;
int zmq_has (const(char)* capability);

/*  Deprecated aliases */
enum ZMQ_STREAMER = 1;
enum ZMQ_FORWARDER = 2;
enum ZMQ_QUEUE = 3;

/*  Deprecated methods */
int zmq_device (int type, void* frontend, void* backend);
int zmq_sendmsg (void* s, zmq_msg_t* msg, int flags);
int zmq_recvmsg (void* s, zmq_msg_t* msg, int flags);
struct iovec;
int zmq_sendiov (void* s, iovec* iov, size_t count, int flags);
int zmq_recviov (void* s, iovec* iov, size_t* count, int flags);

/******************************************************************************/
/*  Encryption functions                                                      */
/******************************************************************************/

/*  Encode data with Z85 encoding. Returns encoded data                       */
char* zmq_z85_encode (char* dest, const(ubyte)* data, size_t size);

/*  Decode data with Z85 encoding. Returns decoded data                       */
ubyte* zmq_z85_decode (ubyte* dest, const(char)* string);

/*  Generate z85-encoded public and private keypair with tweetnacl/libsodium. */
/*  Returns 0 on success.                                                     */
int zmq_curve_keypair (char* z85_public_key, char* z85_secret_key);

/*  Derive the z85-encoded public key from the z85-encoded secret key.        */
/*  Returns 0 on success.                                                     */
int zmq_curve_public (char* z85_public_key, const(char)* z85_secret_key);

/******************************************************************************/
/*  Atomic utility methods                                                    */
/******************************************************************************/

void* zmq_atomic_counter_new ();
void zmq_atomic_counter_set (void* counter, int value);
int zmq_atomic_counter_inc (void* counter);
int zmq_atomic_counter_dec (void* counter);
int zmq_atomic_counter_value (void* counter);
void zmq_atomic_counter_destroy (void** counter_p);

/******************************************************************************/
/*  These functions are not documented by man pages -- use at your own risk.  */
/*  If you need these to be part of the formal ZMQ API, then (a) write a man  */
/*  page, and (b) write a test case in tests.                                 */
/******************************************************************************/

/*  Helper functions are used by perf tests so that they don't have to care   */
/*  about minutiae of time-related functions on different OS platforms.       */

/*  Starts the stopwatch. Returns the handle to the watch.                    */
void* zmq_stopwatch_start ();

/*  Stops the stopwatch. Returns the number of microseconds elapsed since     */
/*  the stopwatch was started.                                                */
c_ulong zmq_stopwatch_stop (void* watch_);

/*  Sleeps for specified number of seconds.                                   */
void zmq_sleep (int seconds_);

alias zmq_thread_fn = void function (void*);

/* Start a thread. Returns a handle to the thread.                            */
void* zmq_threadstart (void function () func, void* arg);

/* Wait for thread to complete then free up resources.                        */
void zmq_threadclose (void* thread);

/******************************************************************************/
/*  These functions are DRAFT and disabled in stable releases, and subject to */
/*  change at ANY time until declared stable.                                 */
/******************************************************************************/

/*  DRAFT Socket types.                                                       */

/*  DRAFT 0MQ socket events and monitoring                                    */

/*  DRAFT Context options                                                     */

/*  DRAFT Socket methods.                                                     */

/*  DRAFT Msg methods.                                                        */

/******************************************************************************/
/*  Poller polling on sockets,fd and thread-safe sockets                      */
/******************************************************************************/

/******************************************************************************/
/*  Scheduling timers                                                         */
/******************************************************************************/

// ZMQ_BUILD_DRAFT_API

