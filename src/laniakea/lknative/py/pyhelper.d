/*
 * Copyright (C) 2018 Atila Neves
 *
 * Licensed under the BSD-3-Clause License
 */

// if a type is a struct or a class
package template isUserAggregate(A...)
if(A.length == 1)
{
    import std.datetime;
    import std.traits: Unqual, isInstanceOf;
    import std.typecons: Tuple;
    alias T = A[0];

    enum isUserAggregate =
        !is(Unqual!T == DateTime) &&
        !isInstanceOf!(Tuple, T) &&
        (is(T == struct) || is(T == class));
}

// must be a global template
private template isMemberFunction(A...)
if(A.length == 1)
{
    alias T = A[0];
    static if(__traits(compiles, __traits(identifier, T)))
        enum isMemberFunction = isPublicFunction!T && __traits(identifier, T) != "__ctor";
    else
        enum isMemberFunction = false;
}

private template isPublicFunction(alias F)
{
    import std.traits: isFunction;
    enum prot = __traits(getProtection, F);
    enum isPublicFunction = isFunction!F && (prot == "export" || prot == "public");
}

// Given a parent (module, struct, ...) and a memberName, alias the actual member,
// or void if not possible
package template Symbol(alias parent, string memberName)
{
    static if(__traits(compiles, I!(__traits(getMember, parent, memberName))))
        alias Symbol = I!(__traits(getMember, parent, memberName));
    else
        alias Symbol = void;
}

/**
Wraps a member function of the class.

Supports default arguments, typesafe variadic arguments, and python's
keyword arguments.

Params:
fn = The member function to wrap.
Options = Optional parameters. Takes Docstring!(docstring), PyName!(pyname),
and fn_t.
fn_t = The type of the function. It is only useful to specify this
       if more than one function has the same name as this one.
pyname = The name of the function as it will appear in Python. Defaults to
fn's name in D
docstring = The function's docstring. Defaults to "".
*/
struct MemberFunction(alias fn, Options...)
{
    import pyd.def: Args;

    alias args = Args!("", "", __traits(identifier, fn), "", Options);

    static if(args.rem.length) {
        alias fn_t = args.rem[0];
    } else {
        alias fn_t = typeof(&fn);
    }

    mixin MemberFunctionImpl!(fn, args.pyname, fn_t, args.docstring);
}

/**
   Wrap aggregate of type T.
 */
void wrapAggregate(T)()
if(isUserAggregate!T)
{

    import pyd.pyd: wrap_class, Member, Init;
    import std.meta: staticMap, Filter, AliasSeq;
    import std.traits: Parameters, FieldNameTuple, hasMember;
    import std.typecons: Tuple;

    alias AggMember(string memberName) = Symbol!(T, memberName);
    alias members = staticMap!(AggMember, __traits(allMembers, T));

    alias memberFunctions = Filter!(isMemberFunction, members);

    static if(hasMember!(T, "__ctor"))
        alias constructors = AliasSeq!(__traits(getOverloads, T, "__ctor"));
    else
        alias constructors = AliasSeq!();

    // If we staticMap with std.traits.Parameters, we end up with a collapsed tuple
    // i.e. with one constructor that takes int and another that takes int, string,
    // we'd end up with 3 elements (int, int, string) instead of 2 ((int), (int, string))
    // so we package them up in a std.typecons.Tuple to avoid flattening
    // each being an AliasSeq of types for the constructor
    alias ParametersTuple(alias F) = Tuple!(Parameters!F);

    // A tuple, with as many elements as constructors. Each element is a
    // std.typecons.Tuple of the constructor parameter types.
    alias constructorParamTuples = staticMap!(ParametersTuple, constructors);

    // Apply pyd's Init to the unpacked types of the parameter Tuple.
    alias InitTuple(alias Tuple) = Init!(Tuple.Types);

    enum isPublic(string fieldName) = __traits(getProtection, __traits(getMember, T, fieldName)) == "public";
    alias publicFields = Filter!(isPublic, FieldNameTuple!T);

    wrap_class!(
        T,
        staticMap!(Member, publicFields),
        staticMap!(MemberFunction, memberFunctions),
        staticMap!(InitTuple, constructorParamTuples),
   );
}
