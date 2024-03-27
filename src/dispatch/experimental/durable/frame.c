#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#if PY_MAJOR_VERSION != 3 || (PY_MINOR_VERSION < 10 || PY_MINOR_VERSION > 13)
# error Python 3.10-3.13 is required
#endif

// https://github.com/python/cpython/blob/3.10/Include/cpython/frameobject.h#L20
typedef int8_t PyFrameState;

// https://github.com/python/cpython/blob/3.10/Include/cpython/frameobject.h#L22
typedef struct _PyTryBlock {
    int b_type;
    int b_handler;
    int b_level;
} PyTryBlock;

// This is a redefinition of the private/opaque frame object.
// In Python 3.10 and prior, `struct _frame` is both the PyFrameObject and
// PyInterpreterFrame. From Python 3.11 onwards, the two were split with the
// PyFrameObject (struct _frame) pointing to struct _PyInterpreterFrame.
typedef struct Frame {
#if PY_MINOR_VERSION == 10
// https://github.com/python/cpython/blob/3.10/Include/cpython/frameobject.h#L28
    PyObject_VAR_HEAD
    struct Frame *f_back; // struct _frame
    PyCodeObject *f_code;
    PyObject *f_builtins;
    PyObject *f_globals;
    PyObject *f_locals;
    PyObject **f_valuestack;
    PyObject *f_trace;
    int f_stackdepth;
    char f_trace_lines;
    char f_trace_opcodes;
    PyObject *f_gen;
    int f_lasti;
    int f_lineno;
    int f_iblock;
    PyFrameState f_state;
    PyTryBlock f_blockstack[CO_MAXBLOCKS];
    PyObject *f_localsplus[1];
#elif PY_MINOR_VERSION == 11
// https://github.com/python/cpython/blob/3.11/Include/internal/pycore_frame.h#L47
    PyFunctionObject *f_func;
    PyObject *f_globals;
    PyObject *f_builtins;
    PyObject *f_locals;
    PyCodeObject *f_code;
    PyFrameObject *frame_obj;
    struct Frame *previous; // struct _PyInterpreterFrame
    _Py_CODEUNIT *prev_instr;
    int stacktop;
    bool is_entry;
    char owner;
    PyObject *localsplus[1];
#elif PY_MINOR_VERSION == 12
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L51
    PyCodeObject *f_code;
    struct Frame *previous; // struct _PyInterpreterFrame
    PyObject *f_funcobj;
    PyObject *f_globals;
    PyObject *f_builtins;
    PyObject *f_locals;
    PyFrameObject *frame_obj;
    _Py_CODEUNIT *prev_instr;
    int stacktop;
    uint16_t return_offset;
    char owner;
    PyObject *localsplus[1];
#elif PY_MINOR_VERSION == 13
// https://github.com/python/cpython/blob/v3.13.0a5/Include/internal/pycore_frame.h#L57
    PyObject *f_executable;
    struct Frame *previous; // struct _PyInterpreterFrame
    PyObject *f_funcobj;
    PyObject *f_globals;
    PyObject *f_builtins;
    PyObject *f_locals;
    PyFrameObject *frame_obj;
    _Py_CODEUNIT *instr_ptr;
    int stacktop;
    uint16_t return_offset;
    char owner;
    PyObject *localsplus[1];
#endif
} Frame;

// This is a redefinition of private frame state constants:
typedef enum _framestate {
#if PY_MINOR_VERSION == 10
// https://github.com/python/cpython/blob/3.10/Include/cpython/frameobject.h#L10
    FRAME_CREATED = -2,
    FRAME_SUSPENDED = -1,
    FRAME_EXECUTING = 0,
    FRAME_RETURNED = 1,
    FRAME_UNWINDING = 2,
    FRAME_RAISED = 3,
    FRAME_CLEARED = 4
#elif PY_MINOR_VERSION == 11
// https://github.com/python/cpython/blob/3.11/Include/internal/pycore_frame.h#L33
    FRAME_CREATED = -2,
    FRAME_SUSPENDED = -1,
    FRAME_EXECUTING = 0,
    FRAME_COMPLETED = 1,
    FRAME_CLEARED = 4
#elif PY_MINOR_VERSION == 12
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L34
    FRAME_CREATED = -2,
    FRAME_SUSPENDED = -1,
    FRAME_EXECUTING = 0,
    FRAME_COMPLETED = 1,
    FRAME_CLEARED = 4
#elif PY_MINOR_VERSION == 13
// https://github.com/python/cpython/blob/v3.13.0a5/Include/internal/pycore_frame.h#L38
    FRAME_CREATED = -3,
    FRAME_SUSPENDED = -2,
    FRAME_SUSPENDED_YIELD_FROM = -1,
    FRAME_EXECUTING = 0,
    FRAME_COMPLETED = 1,
    FRAME_CLEARED = 4
#endif
} FrameState;

// This is a redefinition of the private PyCoroWrapper:
// https://github.com/python/cpython/blob/3.10/Objects/genobject.c#L884
// https://github.com/python/cpython/blob/3.11/Objects/genobject.c#L1016
// https://github.com/python/cpython/blob/3.12/Objects/genobject.c#L1003
// https://github.com/python/cpython/blob/v3.13.0a5/Objects/genobject.c#L985
typedef struct {
    PyObject_HEAD
    PyCoroObject *cw_coroutine;
} PyCoroWrapper;

/*
// This is the definition of PyFrameObject (aka. struct _frame) for reference
// to developers working on the extension. As noted above, the contents of
// struct _frame changed over time, with some fields moving in Python >= 3.11
// to a separate struct _PyInterpreterFrame.
//
typedef struct {
#if PY_MINOR_VERSION == 10
// https://github.com/python/cpython/blob/3.10/Include/cpython/frameobject.h#L28
    PyObject_VAR_HEAD
    struct _frame *f_back;
    PyCodeObject *f_code;
    PyObject *f_builtins;
    PyObject *f_globals;
    PyObject *f_locals;
    PyObject **f_valuestack;
    PyObject *f_trace;
    int f_stackdepth;
    char f_trace_lines;
    char f_trace_opcodes;
    PyObject *f_gen;
    int f_lasti;
    int f_lineno;
    int f_iblock;
    PyFrameState f_state;
    PyTryBlock f_blockstack[CO_MAXBLOCKS];
    PyObject *f_localsplus[1];
#elif PY_MINOR_VERSION == 11
// https://github.com/python/cpython/blob/3.11/Include/internal/pycore_frame.h#L15
    PyObject_HEAD
    PyFrameObject *f_back;
    struct _PyInterpreterFrame *f_frame;
    PyObject *f_trace;
    int f_lineno;
    char f_trace_lines;
    char f_trace_opcodes;
    char f_fast_as_locals;
    PyObject *_f_frame_data[1];
#elif PY_MINOR_VERSION == 12
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L16
    PyObject_HEAD
    PyFrameObject *f_back;
    struct _PyInterpreterFrame *f_frame;
    PyObject *f_trace;
    int f_lineno;
    char f_trace_lines;
    char f_trace_opcodes;
    char f_fast_as_locals;
    PyObject *_f_frame_data[1];
#elif PY_MINOR_VERSION == 13
// https://github.com/python/cpython/blob/v3.13.0a5/Include/internal/pycore_frame.h#L20
    PyObject_HEAD
    PyFrameObject *f_back;
    struct _PyInterpreterFrame *f_frame;
    PyObject *f_trace;
    int f_lineno;
    char f_trace_lines;
    char f_trace_opcodes;
    char f_fast_as_locals;
    PyObject *_f_frame_data[1];
#endif
} PyFrameObject;
*/

/*
// This is the definition of PyGenObject for reference to developers
// working on the extension.
//
// Note that PyCoroObject and PyAsyncGenObject have the same layout as
// PyGenObject, however the struct fields have a cr_ and ag_ prefix
// (respectively) rather than a gi_ prefix. In Python 3.10, PyCoroObject
// and PyAsyncGenObject have extra fields compared to PyGenObject. In Python
// 3.11 onwards, the three objects are identical (except for field name
// prefixes). The extra fields in Python 3.10 are not applicable to this
// extension at this time.
//
typedef struct {
    PyObject_HEAD
#if PY_MINOR_VERSION == 10
// https://github.com/python/cpython/blob/3.10/Include/genobject.h#L16
    PyFrameObject *gi_frame;
    PyObject *gi_code;
    PyObject *gi_weakreflist;
    PyObject *gi_name;
    PyObject *gi_qualname;
    _PyErr_StackItem gi_exc_state;
#elif PY_MINOR_VERSION == 11
// https://github.com/python/cpython/blob/3.11/Include/cpython/genobject.h#L14
    PyCodeObject *gi_code;
    PyObject *gi_weakreflist;
    PyObject *gi_name;
    PyObject *gi_qualname;
    _PyErr_StackItem gi_exc_state;
    PyObject *gi_origin_or_finalizer;
    char gi_hooks_inited;
    char gi_closed;
    char gi_running_async;
    int8_t gi_frame_state;
    PyObject *gi_iframe[1];
#elif PY_MINOR_VERSION == 12
// https://github.com/python/cpython/blob/3.12/Include/cpython/genobject.h#L14
    PyObject *gi_weakreflist;
    PyObject *gi_name;
    PyObject *gi_qualname;
    _PyErr_StackItem gi_exc_state;
    PyObject *gi_origin_or_finalizer;
    char gi_hooks_inited;
    char gi_closed;
    char gi_running_async;
    int8_t gi_frame_state;
    PyObject *gi_iframe[1];
#elif PY_MINOR_VERSION == 13
// https://github.com/python/cpython/blob/v3.13.0a5/Include/cpython/genobject.h#L14
    PyObject *gi_weakreflist;
    PyObject *gi_name;
    PyObject *gi_qualname;
    _PyErr_StackItem gi_exc_state;
    PyObject *gi_origin_or_finalizer;
    char gi_hooks_inited;
    char gi_closed;
    char gi_running_async;
    int8_t gi_frame_state;
    PyObject *gi_iframe[1];
#endif
} PyGenObject;
*/

static const char *get_type_name(PyObject *obj) {
    PyObject* type = PyObject_Type(obj);
    if (!type) {
        return NULL;
    }
    PyObject* name = PyObject_GetAttrString(type, "__name__");
    Py_DECREF(type);
    if (!name) {
        return NULL;
    }
    const char* name_str = PyUnicode_AsUTF8(name);
    Py_DECREF(name);
    return name_str;
}

static PyGenObject *get_generator_like_object(PyObject *obj) {
    if (PyGen_Check(obj) || PyCoro_CheckExact(obj) || PyAsyncGen_CheckExact(obj)) {
        // Note: In Python 3.10-3.13, the PyGenObject, PyCoroObject and PyAsyncGenObject
        // have the same layout, they just have different field prefixes (gi_, cr_, ag_).
        // We cast to PyGenObject here so that the remainder of the code can use the gi_
        // prefix for all three cases.
        return (PyGenObject *)obj;
    }
    // If the object isn't a PyGenObject, PyCoroObject or PyAsyncGenObject, it may
    // still be a coroutine, for example a PyCoroWrapper. CPython unfortunately does
    // not export a function that checks whether a PyObject is a PyCoroWrapper. We
    // need to check the type name string.
    const char *type_name = get_type_name(obj);
    if (!type_name) {
        return NULL;
    }
    if (strcmp(type_name, "coroutine_wrapper") == 0) {
        // FIXME: improve safety here, e.g. by checking that the obj type matches a known size
        PyCoroWrapper *wrapper = (PyCoroWrapper *)obj;
        // Cast the inner PyCoroObject to a PyGenObject. See the comment above.
        return (PyGenObject *)wrapper->cw_coroutine;
    }
    PyErr_SetString(PyExc_TypeError, "Input object is not a generator or coroutine");
    return NULL;
}

static Frame *get_frame(PyGenObject *gen_like) {
#if PY_MINOR_VERSION == 10
    Frame *frame = (Frame *)(gen_like->gi_frame);
#elif PY_MINOR_VERSION == 11
    Frame *frame = (Frame *)(struct _PyInterpreterFrame *)(gen_like->gi_iframe);
#elif PY_MINOR_VERSION == 12
    Frame *frame = (Frame *)(struct _PyInterpreterFrame *)(gen_like->gi_iframe);
#elif PY_MINOR_VERSION == 13
    Frame *frame = (Frame *)(struct _PyInterpreterFrame *)(gen_like->gi_iframe);
#endif
    assert(frame);
    return frame;
}

static PyCodeObject *get_frame_code(Frame *frame) {
#if PY_MINOR_VERSION == 10
    PyCodeObject *code = frame->f_code;
#elif PY_MINOR_VERSION == 11
    PyCodeObject *code = frame->f_code;
#elif PY_MINOR_VERSION == 12
    PyCodeObject *code = frame->f_code;
#elif PY_MINOR_VERSION == 13
    PyCodeObject *code = (PyCodeObject *)frame->f_executable;
#endif
    assert(code);
    return code;
}

static int get_frame_lasti(Frame *frame) {
#if PY_MINOR_VERSION == 10
    return frame->f_lasti;
#elif PY_MINOR_VERSION == 11
// https://github.com/python/cpython/blob/3.11/Include/internal/pycore_frame.h#L69
    PyCodeObject *code = get_frame_code(frame);
    assert(frame->prev_instr);
    return (int)((intptr_t)frame->prev_instr - (intptr_t)_PyCode_CODE(code));
#elif PY_MINOR_VERSION == 12
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L77
    PyCodeObject *code = get_frame_code(frame);
    assert(frame->prev_instr);
    return (int)((intptr_t)frame->prev_instr - (intptr_t)_PyCode_CODE(code));
#elif PY_MINOR_VERSION == 13
// https://github.com/python/cpython/blob/v3.13.0a5/Include/internal/pycore_frame.h#L73
    PyCodeObject *code = get_frame_code(frame);
    assert(frame->instr_ptr);
    return (int)((intptr_t)frame->instr_ptr - (intptr_t)_PyCode_CODE(code));
#endif
}

static void set_frame_lasti(Frame *frame, int lasti) {
#if PY_MINOR_VERSION == 10
    frame->f_lasti = lasti;
#elif PY_MINOR_VERSION == 11
// https://github.com/python/cpython/blob/3.11/Include/internal/pycore_frame.h#L69
    PyCodeObject *code = get_frame_code(frame);
    frame->prev_instr = (_Py_CODEUNIT *)((intptr_t)_PyCode_CODE(code) + (intptr_t)lasti);
#elif PY_MINOR_VERSION == 12
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L77
    PyCodeObject *code = get_frame_code(frame);
    frame->prev_instr = (_Py_CODEUNIT *)((intptr_t)_PyCode_CODE(code) + (intptr_t)lasti);
#elif PY_MINOR_VERSION == 13
// https://github.com/python/cpython/blob/v3.13.0a5/Include/internal/pycore_frame.h#L73
    PyCodeObject *code = get_frame_code(frame);
    frame->instr_ptr = (_Py_CODEUNIT *)((intptr_t)_PyCode_CODE(code) + (intptr_t)lasti);
#endif
}

static int get_frame_state(PyGenObject *gen_like) {
#if PY_MINOR_VERSION == 10
    Frame *frame = (Frame *)(gen_like->gi_frame);
    if (!frame) {
        return FRAME_CLEARED;
    }
    return frame->f_state;
#elif PY_MINOR_VERSION == 11
    return gen_like->gi_frame_state;
#elif PY_MINOR_VERSION == 12
    return gen_like->gi_frame_state;
#elif PY_MINOR_VERSION == 13
    return gen_like->gi_frame_state;
#endif
}

static void set_frame_state(PyGenObject *gen_like, int fs) {
#if PY_MINOR_VERSION == 10
    Frame *frame = get_frame(gen_like);
    frame->f_state = (PyFrameState)fs;
#elif PY_MINOR_VERSION == 11
    gen_like->gi_frame_state = (int8_t)fs;
#elif PY_MINOR_VERSION == 12
    gen_like->gi_frame_state = (int8_t)fs;
#elif PY_MINOR_VERSION == 13
    gen_like->gi_frame_state = (int8_t)fs;
#endif
}

static int valid_frame_state(int fs) {
#if PY_MINOR_VERSION == 10
    return fs == FRAME_CREATED || fs == FRAME_SUSPENDED || fs == FRAME_EXECUTING || fs == FRAME_RETURNED || fs == FRAME_UNWINDING || fs == FRAME_RAISED || fs == FRAME_CLEARED;
#elif PY_MINOR_VERSION == 11
    return fs == FRAME_CREATED || fs == FRAME_SUSPENDED || fs == FRAME_EXECUTING || fs == FRAME_COMPLETED || fs == FRAME_CLEARED;
#elif PY_MINOR_VERSION == 12
    return fs == FRAME_CREATED || fs == FRAME_SUSPENDED || fs == FRAME_EXECUTING || fs == FRAME_COMPLETED || fs == FRAME_CLEARED;
#elif PY_MINOR_VERSION == 13
    return fs == FRAME_CREATED || fs == FRAME_SUSPENDED || fs == FRAME_SUSPENDED_YIELD_FROM || fs == FRAME_EXECUTING || fs == FRAME_COMPLETED || fs == FRAME_CLEARED;
#endif
}

static int get_frame_stacktop_limit(Frame *frame) {
    PyCodeObject *code = get_frame_code(frame);
#if PY_MINOR_VERSION == 10
    return code->co_stacksize + code->co_nlocals;
#elif PY_MINOR_VERSION == 11
    return code->co_stacksize + code->co_nlocalsplus;
#elif PY_MINOR_VERSION == 12
    return code->co_stacksize + code->co_nlocalsplus;
#elif PY_MINOR_VERSION == 13
    return code->co_stacksize + code->co_nlocalsplus;
#endif
}

static int get_frame_stacktop(Frame *frame) {
#if PY_MINOR_VERSION == 10
    assert(frame->f_localsplus);
    assert(frame->f_valuestack);
    int stacktop = (int)(frame->f_valuestack - frame->f_localsplus) + frame->f_stackdepth;
#elif PY_MINOR_VERSION == 11
    int stacktop = frame->stacktop;
#elif PY_MINOR_VERSION == 12
    int stacktop = frame->stacktop;
#elif PY_MINOR_VERSION == 13
    int stacktop = frame->stacktop;
#endif
    assert(stacktop >= 0 && stacktop < get_frame_stacktop_limit(frame));
    return stacktop;
}

static void set_frame_stacktop(Frame *frame, int stacktop) {
    assert(stacktop >= 0 && stacktop < get_frame_stacktop_limit(frame));
#if PY_MINOR_VERSION == 10
    assert(frame->f_localsplus);
    assert(frame->f_valuestack);
    int base = (int)(frame->f_valuestack - frame->f_localsplus);
    assert(stacktop >= base);
    frame->f_stackdepth = stacktop - base;
#elif PY_MINOR_VERSION == 11
    frame->stacktop = stacktop;
#elif PY_MINOR_VERSION == 12
    frame->stacktop = stacktop;
#elif PY_MINOR_VERSION == 13
    frame->stacktop = stacktop;
#endif
}

static PyObject **get_frame_localsplus(Frame *frame) {
#if PY_MINOR_VERSION == 10
    PyObject **localsplus = frame->f_localsplus;
#elif PY_MINOR_VERSION == 11
    PyObject **localsplus = frame->localsplus;
#elif PY_MINOR_VERSION == 12
    PyObject **localsplus = frame->localsplus;
#elif PY_MINOR_VERSION == 13
    PyObject **localsplus = frame->localsplus;
#endif
    assert(localsplus);
    return localsplus;
}

static int get_frame_iblock_limit(Frame *frame) {
#if PY_MINOR_VERSION == 10
    return CO_MAXBLOCKS;
#endif
    return 1; // not applicable >= 3.11
}

static int get_frame_iblock(Frame *frame) {
#if PY_MINOR_VERSION == 10
    return frame->f_iblock;
#endif
    return 0; // not applicable >= 3.11
}

static void set_frame_iblock(Frame *frame, int iblock) {
    assert(iblock >= 0 && iblock < get_frame_iblock_limit(frame));
#if PY_MINOR_VERSION == 10
    frame->f_iblock = iblock;
#else
    assert(!iblock); // not applicable >= 3.11
#endif
}

static PyTryBlock *get_frame_blockstack(Frame *frame) {
#if PY_MINOR_VERSION == 10
    PyTryBlock *blockstack = frame->f_blockstack;
#else
    PyTryBlock *blockstack = NULL; // not applicable >= 3.11
#endif
    assert(blockstack);
    return blockstack;
}

static PyObject *ext_get_frame_state(PyObject *self, PyObject *args) {
    PyObject *arg;
    if (!PyArg_ParseTuple(args, "O", &arg)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(arg);
    if (!gen_like) {
        return NULL;
    }
    int fs = get_frame_state(gen_like);
    return PyLong_FromLong((long)fs);
}

static PyObject *ext_get_frame_ip(PyObject *self, PyObject *args) {
    PyObject *obj;
    if (!PyArg_ParseTuple(args, "O", &obj)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int ip = get_frame_lasti(frame);
    return PyLong_FromLong((long)ip);
}

static PyObject *ext_get_frame_sp(PyObject *self, PyObject *args) {
    PyObject *obj;
    if (!PyArg_ParseTuple(args, "O", &obj)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int sp = get_frame_stacktop(frame);
    return PyLong_FromLong((long)sp);
}

static PyObject *ext_get_frame_bp(PyObject *self, PyObject *args) {
    PyObject *obj;
    if (!PyArg_ParseTuple(args, "O", &obj)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int bp = get_frame_iblock(frame);
    return PyLong_FromLong((long)bp);
}

static PyObject *ext_get_frame_stack_at(PyObject *self, PyObject *args) {
    PyObject *obj;
    int index;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &index)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int sp = get_frame_stacktop(frame);
    if (index < 0 || index >= sp) {
        PyErr_SetString(PyExc_IndexError, "Index out of bounds");
        return NULL;
    }

    // NULL in C != None in Python. We need to preserve the fact that some items
    // on the stack are NULL (not yet available).
    PyObject *is_null = Py_False;
    PyObject **localsplus = get_frame_localsplus(frame);
    PyObject *stack_obj = localsplus[index];
    if (!stack_obj) {
        is_null = Py_True;
        stack_obj = Py_None;
    }
    return PyTuple_Pack(2, is_null, stack_obj);
}

static PyObject *ext_get_frame_block_at(PyObject *self, PyObject *args) {
    PyObject *obj;
    int index;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &index)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int bp = get_frame_iblock(frame);
    if (index < 0 || index >= bp) {
        PyErr_SetString(PyExc_IndexError, "Index out of bounds");
        return NULL;
    }
    PyTryBlock *blockstack = get_frame_blockstack(frame);
    PyTryBlock *block = &blockstack[index];
    return Py_BuildValue("(iii)", block->b_type, block->b_handler, block->b_level);
}

static PyObject *ext_set_frame_ip(PyObject *self, PyObject *args) {
    PyObject *obj;
    int ip;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &ip)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    set_frame_lasti(frame, ip);
    Py_RETURN_NONE;
}

static PyObject *ext_set_frame_sp(PyObject *self, PyObject *args) {
    PyObject *obj;
    int sp;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &sp)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int limit = get_frame_stacktop_limit(frame);
    if (sp < 0 || sp >= limit) {
        PyErr_SetString(PyExc_IndexError, "Stack pointer out of bounds");
        return NULL;
    }
    PyObject **localsplus = get_frame_localsplus(frame);
    int current_sp = get_frame_stacktop(frame);
    if (sp > current_sp) {
        for (int i = current_sp; i < sp; i++) {
            localsplus[i] = NULL;
        }
    }
    set_frame_stacktop(frame, sp);
    Py_RETURN_NONE;
}

static PyObject *ext_set_frame_bp(PyObject *self, PyObject *args) {
    PyObject *obj;
    int bp;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &bp)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int limit = get_frame_iblock_limit(frame);
    if (bp < 0 || bp >= limit) {
        PyErr_SetString(PyExc_IndexError, "Block pointer out of bounds");
        return NULL;
    }
    set_frame_iblock(frame, bp);
    Py_RETURN_NONE;
}

static PyObject *ext_set_frame_state(PyObject *self, PyObject *args) {
    PyObject *obj;
    int fs;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &fs)) {
        return NULL;
    }
    if (fs == FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot set frame state to FRAME_CLEARED");
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    if (!valid_frame_state(fs)) {
        PyErr_SetString(PyExc_ValueError, "Invalid frame state");
        return NULL;
    }
    set_frame_state(gen_like, fs);
    Py_RETURN_NONE;
}

static PyObject *ext_set_frame_stack_at(PyObject *self, PyObject *args) {
    PyObject *obj;
    int index;
    PyObject *unset;
    PyObject *stack_obj;
    if (!PyArg_ParseTuple(args, "OiOO", &obj, &index, &unset, &stack_obj)) {
        return NULL;
    }
    if (!PyBool_Check(unset)) {
        PyErr_SetString(PyExc_TypeError, "Expected a boolean indicating whether to unset the stack object");
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int sp = get_frame_stacktop(frame);
    if (index < 0 || index >= sp) {
        PyErr_SetString(PyExc_IndexError, "Index out of bounds");
        return NULL;
    }
    PyObject **localsplus = get_frame_localsplus(frame);
    PyObject *prev = localsplus[index];
    if (Py_IsTrue(unset)) {
        localsplus[index] = NULL;
    } else {
        Py_INCREF(stack_obj);
        localsplus[index] = stack_obj;
    }
    Py_XDECREF(prev);
    Py_RETURN_NONE;
}

static PyObject *ext_set_frame_block_at(PyObject *self, PyObject *args) {
    PyObject *obj;
    int index;
    int b_type;
    int b_handler;
    int b_level;
    if (!PyArg_ParseTuple(args, "Oi(iii)", &obj, &index, &b_type, &b_handler, &b_level)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (get_frame_state(gen_like) >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    Frame *frame = get_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    int bp = get_frame_iblock(frame);
    if (index < 0 || index >= bp) {
        PyErr_SetString(PyExc_IndexError, "Index out of bounds");
        return NULL;
    }
    PyTryBlock *blockstack = get_frame_blockstack(frame);
    PyTryBlock *block = &blockstack[index];
    block->b_type = b_type;
    block->b_handler = b_handler;
    block->b_level = b_level;
    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
        {"get_frame_ip",  ext_get_frame_ip, METH_VARARGS, "Get instruction pointer of a generator or coroutine."},
        {"set_frame_ip",  ext_set_frame_ip, METH_VARARGS, "Set instruction pointer of a generator or coroutine."},
        {"get_frame_sp",  ext_get_frame_sp, METH_VARARGS, "Get stack pointer of a generator or coroutine."},
        {"set_frame_sp",  ext_set_frame_sp, METH_VARARGS, "Set stack pointer of a generator or coroutine."},
        {"get_frame_bp",  ext_get_frame_bp, METH_VARARGS, "Get block pointer of a generator or coroutine."},
        {"set_frame_bp",  ext_set_frame_bp, METH_VARARGS, "Set block pointer of a generator or coroutine."},
        {"get_frame_stack_at",  ext_get_frame_stack_at, METH_VARARGS, "Get an object from a generator or coroutine's stack, as an (is_null, obj) tuple."},
        {"set_frame_stack_at",  ext_set_frame_stack_at, METH_VARARGS, "Set or unset an object on the stack of a generator or coroutine."},
        {"get_frame_block_at",  ext_get_frame_block_at, METH_VARARGS, "Get a block from a generator or coroutine."},
        {"set_frame_block_at",  ext_set_frame_block_at, METH_VARARGS, "Restore a block of a generator or coroutine."},
        {"get_frame_state",  ext_get_frame_state, METH_VARARGS, "Get frame state of a generator or coroutine."},
        {"set_frame_state",  ext_set_frame_state, METH_VARARGS, "Set frame state of a generator or coroutine."},
        {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "frame", NULL, -1, methods};

PyMODINIT_FUNC PyInit_frame(void) {
    return PyModule_Create(&module);
}
