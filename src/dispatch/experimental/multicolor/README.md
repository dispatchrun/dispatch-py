This package contains a JIT compiler that "recolors" functions on the fly.

[What color is your function?][what-color] Python has async functions (red), generator functions (green),
async generator functions (yellow) and regular functions (blue):

```python
>>> async def red(): pass
>>> def green(): yield
>>> async def yellow(): yield
>>> def blue(): pass
```

You interact with these functions in different ways. For example, you `await` red and yellow async
functions, and `yield from` (or iterate over) green and yellow generator functions.

There are rules that make mixing colors painful. For example, you cannot `await` an async red or
yellow function from a non-async blue or green function. Some colors (e.g. red, yellow) tend to
infect a codebase, requiring that you either avoid that color or [go all in][asyncio].

Red, green and yellow functions create `coroutine`, `generator` and `async_generator` objects,
respectively:

```
>>> red()
<coroutine object red at 0x1025e5f30>
>>> green()
<generator object green at 0x1025e6140>
>>> yellow()
<async_generator object yellow at 0x1025e5f30>
```

These objects are all types of coroutines. They all share a desirable property; they can
be suspended during execution and then later resumed from the same point. There is however
a major caveat, which is that to suspend a coroutine deep within a call stack, there cannot
be regular (blue) function call on the path. Unfortunately, most Python functions in the
standard library and [package index][pypi] are blue.

`multicolor` solves the issue by providing a `compile_function` that turns blue functions
green. As blue or green functions are called, it recursively turns them green. This turns
regular functions and generator functions into coroutines that can be suspended at any
point, even when there are functions from the standard library or other dependencies that
the user has no control over.

```python
from multicolor import compile_function

green = compile_function(blue)  # recursively turns functions into green coroutines
```

See the internal `compile_function` docs for more usage information.

Caveats:
* Only functions called explicitly are recolored. Implicit function calls (e.g. via
  magic methods) are not supported at this time.
* Red and yellow function support may be added in future, allowing the user to mix and
  match all colors. For now, this package only works with synchronous (blue and green)
  functions.
* Function calls are not currently supported in `match` case guards, in the parameter
  list of a nested function or class definition, in `lambda` functions and as exception
  handler type expressions.
* Nested generators are supported, but they're eagerly evaluated at their call site
  which may subtly break your program. Nested `yield from` statements are not well
  supported.


[what-color]: https://journal.stuffwithstuff.com/2015/02/01/what-color-is-your-function/
[asyncio]: https://docs.python.org/3/library/asyncio.html
[pypi]: https://pypi.org
