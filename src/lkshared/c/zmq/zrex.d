/*  =========================================================================
    zrex - work with regular expressions

    Copyright (c) the Contributors as noted in the AUTHORS file.
    This file is part of CZMQ, the high-level C binding for 0MQ:
    http://czmq.zeromq.org.

    This Source Code Form is subject to the terms of the Mozilla Public
    License, v. 2.0. If a copy of the MPL was not distributed with this
    file, You can obtain one at http://mozilla.org/MPL/2.0/.
    =========================================================================
*/

public import c.zmq.czmq_library;

extern (C):

//  @interface
//  Constructor. Optionally, sets an expression against which we can match
//  text and capture hits. If there is an error in the expression, reports
//  zrex_valid() as false and provides the error in zrex_strerror(). If you
//  set a pattern, you can call zrex_matches() to test it against text.
zrex_t* zrex_new (const(char)* expression);

//  Destructor
void zrex_destroy (zrex_t** self_p);

//  Return true if the expression was valid and compiled without errors.
bool zrex_valid (zrex_t* self);

//  Return the error message generated during compilation of the expression.
const(char)* zrex_strerror (zrex_t* self);

//  Returns true if the text matches the previously compiled expression.
//  Use this method to compare one expression against many strings.
bool zrex_matches (zrex_t* self, const(char)* text);

//  Returns true if the text matches the supplied expression. Use this
//  method to compare one string against several expressions.
bool zrex_eq (zrex_t* self, const(char)* text, const(char)* expression);

//  Returns number of hits from last zrex_matches or zrex_eq. If the text
//  matched, returns 1 plus the number of capture groups. If the text did
//  not match, returns zero. To retrieve individual capture groups, call
//  zrex_hit ().
int zrex_hits (zrex_t* self);

//  Returns the Nth capture group from the last expression match, where
//  N is 0 to the value returned by zrex_hits(). Capture group 0 is the
//  whole matching string. Sequence 1 is the first capture group, if any,
//  and so on.
const(char)* zrex_hit (zrex_t* self, uint index);

//  Fetches hits into string variables provided by caller; this makes for
//  nicer code than accessing hits by index. Caller should not modify nor
//  free the returned values. Returns number of strings returned. This
//  method starts at hit 1, i.e. first capture group, as hit 0 is always
//  the original matched string.
int zrex_fetch (zrex_t* self, const(char*)* string_p, ...);

//  Self test of this class
void zrex_test (bool verbose);

//  @end

