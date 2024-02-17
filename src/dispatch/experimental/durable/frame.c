#undef NDEBUG
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>

#define PY_SSIZE_T_CLEAN
#include <Python.h>

#if PY_MAJOR_VERSION != 3 || (PY_MINOR_VERSION < 11 || PY_MINOR_VERSION > 13)
# error Python 3.11-3.13 is required
#endif

// This is a redefinition of the private/opaque struct _PyInterpreterFrame:
// https://github.com/python/cpython/blob/3.12/Include/cpython/pyframe.h#L23
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L51
typedef struct InterpreterFrame {
#if PY_MINOR_VERSION == 11
    PyFunctionObject *f_func;
#elif PY_MINOR_VERSION >= 12
    PyCodeObject *f_code; // 3.13: PyObject *f_executable
    struct _PyInterpreterFrame *previous;
    PyObject *f_funcobj;
#endif
    PyObject *f_globals;
    PyObject *f_builtins;
    PyObject *f_locals;
#if PY_MINOR_VERSION == 11
    PyCodeObject *f_code;
    PyFrameObject *frame_obj;
    struct _PyInterpreterFrame *previous;
    _Py_CODEUNIT *prev_instr;
    int stacktop;
    bool is_entry;
#elif PY_MINOR_VERSION >= 12
    PyFrameObject *frame_obj;
    _Py_CODEUNIT *prev_instr; // 3.13: _Py_CODEUNIT *instr_ptr
    int stacktop;
    uint16_t return_offset;
#endif
    char owner;
    PyObject *localsplus[1];
} InterpreterFrame;

// This is a redefinition of the private/opaque PyFrameObject:
// https://github.com/python/cpython/blob/3.12/Include/pytypedefs.h#L22
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L16
// The definition is the same for Python 3.11-3.13.
typedef struct FrameObject {
    PyObject_HEAD
    PyFrameObject *f_back;
    struct _PyInterpreterFrame *f_frame;
    PyObject *f_trace;
    int f_lineno;
    char f_trace_lines;
    char f_trace_opcodes;
    char f_fast_as_locals;
    PyObject *_f_frame_data[1];
} FrameObject;

// This is a redefinition of frame state constants:
// https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L34
typedef enum _framestate {
#if PY_MINOR_VERSION == 13
    FRAME_CREATED = -3,
    FRAME_SUSPENDED = -2,
    FRAME_SUSPENDED_YIELD_FROM = -1,
#else
    FRAME_CREATED = -2,
    FRAME_SUSPENDED = -1,
#endif
    FRAME_EXECUTING = 0,
    FRAME_COMPLETED = 1,
    FRAME_CLEARED = 4
} FrameState;

// This is a redefinition of the private PyCoroWrapper:
typedef struct {
    PyObject_HEAD
    PyCoroObject *cw_coroutine;
} PyCoroWrapper;

// For reference, PyGenObject is defined as follows after expanding top-most macro:
// https://github.com/python/cpython/blob/3.12/Include/cpython/genobject.h
// Note that PyCoroObject and PyAsyncGenObject have the same layout in
// Python 3.11-3.13, however the struct fields have a cr_ and ag_ prefix
// (respectively) instead of a gi_ prefix.
/*
typedef struct {
    PyObject_HEAD
#if PY_MINOR_VERSION == 11
    PyCodeObject *gi_code;
#endif
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
        // Note: In Python 3.11-3.13, the PyGenObject, PyCoroObject and PyAsyncGenObject
        // have the same layout, they just have different field prefixes (gi_, cr_, ag_).
        return (PyGenObject *)obj;
    }
    // CPython unfortunately does not export any functions that
    // check whether an object is a coroutine_wrapper.
    // FIXME: improve safety here, e.g. by checking that the obj type matches a known size
    const char *type_name = get_type_name(obj);
    if (!type_name) {
        return NULL;
    }
    if (strcmp(type_name, "coroutine_wrapper") == 0) {
        PyCoroWrapper *wrapper = (PyCoroWrapper *)obj;
        return (PyGenObject *)wrapper->cw_coroutine;
    }
    PyErr_SetString(PyExc_TypeError, "Input object is not a generator or coroutine");
    return NULL;
}

static InterpreterFrame *get_interpreter_frame(PyGenObject *gen_like) {
    struct _PyInterpreterFrame *frame = (struct _PyInterpreterFrame *)(gen_like->gi_iframe);
    assert(frame);
    return (InterpreterFrame *)frame;
}

static PyObject *get_frame_state(PyObject *self, PyObject *args) {
    PyObject *arg;
    if (!PyArg_ParseTuple(args, "O", &arg)) {
        return NULL;
    }
    PyGenObject *gen = get_generator_like_object(arg);
    if (!gen) {
        return NULL;
    }
    return PyLong_FromLong((long)gen->gi_frame_state); // aka. cr_frame_state / ag_frame_state
}

static PyObject *get_frame_ip(PyObject *self, PyObject *args) {
    PyObject *obj;
    if (!PyArg_ParseTuple(args, "O", &obj)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    assert(frame->f_code);
    assert(frame->prev_instr);
    // See _PyInterpreterFrame_LASTI
    // https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L77
    intptr_t ip = (intptr_t)frame->prev_instr - (intptr_t)_PyCode_CODE(frame->f_code);
    return PyLong_FromLong((long)ip);
}

static PyObject *get_frame_sp(PyObject *self, PyObject *args) {
    PyObject *obj;
    if (!PyArg_ParseTuple(args, "O", &obj)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    assert(frame->stacktop >= 0);
    int sp = frame->stacktop;
    return PyLong_FromLong((long)sp);
}

static PyObject *get_frame_stack_at(PyObject *self, PyObject *args) {
    PyObject *obj;
    int index;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &index)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot access cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    assert(frame->stacktop >= 0);

    int limit = frame->f_code->co_stacksize + frame->f_code->co_nlocalsplus;
    if (index < 0 || index >= limit) {
        PyErr_SetString(PyExc_IndexError, "Index out of bounds");
        return NULL;
    }

    // NULL in C != None in Python. We need to preserve the fact that some items
    // on the stack are NULL (not yet available).
    PyObject *is_null = Py_False;
    PyObject *stack_obj = frame->localsplus[index];
    if (!stack_obj) {
        is_null = Py_True;
        stack_obj = Py_None;
    }
    return PyTuple_Pack(2, is_null, stack_obj);
}

static PyObject *set_frame_ip(PyObject *self, PyObject *args) {
    PyObject *obj;
    int ip;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &ip)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    assert(frame->f_code);
    assert(frame->prev_instr);
    // See _PyInterpreterFrame_LASTI
    // https://github.com/python/cpython/blob/3.12/Include/internal/pycore_frame.h#L77
    frame->prev_instr = (_Py_CODEUNIT *)((intptr_t)_PyCode_CODE(frame->f_code) + (intptr_t)ip);
    Py_RETURN_NONE;
}

static PyObject *set_frame_sp(PyObject *self, PyObject *args) {
    PyObject *obj;
    int sp;
    if (!PyArg_ParseTuple(args, "Oi", &obj, &sp)) {
        return NULL;
    }
    PyGenObject *gen_like = get_generator_like_object(obj);
    if (!gen_like) {
        return NULL;
    }
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    assert(frame->stacktop >= 0);

    int limit = frame->f_code->co_stacksize + frame->f_code->co_nlocalsplus;
    if (sp < 0 || sp >= limit) {
        PyErr_SetString(PyExc_IndexError, "Stack pointer out of bounds");
        return NULL;
    }

    if (sp > frame->stacktop) {
        for (int i = frame->stacktop; i < sp; i++) {
            frame->localsplus[i] = NULL;
        }
    }

    frame->stacktop = sp;
    Py_RETURN_NONE;
}

static PyObject *set_frame_state(PyObject *self, PyObject *args) {
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
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
#if PY_MINOR_VERSION == 13
    if (fs != FRAME_CREATED && fs != FRAME_SUSPENDED && fs != FRAME_SUSPENDED_YIELD_FROM && fs != FRAME_EXECUTING && fs != FRAME_COMPLETED) {
        PyErr_SetString(PyExc_ValueError, "Invalid frame state");
        return NULL;
    }
#else
    if (fs != FRAME_CREATED && fs != FRAME_SUSPENDED && fs != FRAME_EXECUTING && fs != FRAME_COMPLETED) {
        PyErr_SetString(PyExc_ValueError, "Invalid frame state");
        return NULL;
    }
#endif
    gen_like->gi_frame_state = (int8_t)fs; // aka. cr_frame_state / ag_frame_state
    Py_RETURN_NONE;
}

static PyObject *set_frame_stack_at(PyObject *self, PyObject *args) {
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
    if (gen_like->gi_frame_state >= FRAME_CLEARED) {
        PyErr_SetString(PyExc_RuntimeError, "Cannot mutate cleared frame");
        return NULL;
    }
    InterpreterFrame *frame = get_interpreter_frame(gen_like);
    if (!frame) {
        return NULL;
    }
    assert(frame->stacktop >= 0);
    int limit = frame->f_code->co_stacksize + frame->f_code->co_nlocalsplus;
    if (index < 0 || index >= limit) {
        PyErr_SetString(PyExc_IndexError, "Index out of bounds");
        return NULL;
    }

    PyObject *prev = frame->localsplus[index];
    if (Py_IsTrue(unset)) {
        frame->localsplus[index] = NULL;
    } else {
        Py_INCREF(stack_obj);
        frame->localsplus[index] = stack_obj;
    }

    if (index < frame->stacktop) {
        Py_XDECREF(prev);
    }

    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
        {"get_frame_ip",  get_frame_ip, METH_VARARGS, "Get instruction pointer of a generator or coroutine."},
        {"set_frame_ip",  set_frame_ip, METH_VARARGS, "Set instruction pointer of a generator or coroutine."},
        {"get_frame_sp",  get_frame_sp, METH_VARARGS, "Get stack pointer of a generator or coroutine."},
        {"set_frame_sp",  set_frame_sp, METH_VARARGS, "Set stack pointer of a generator or coroutine."},
        {"get_frame_stack_at",  get_frame_stack_at, METH_VARARGS, "Get an object from a generator or coroutine's stack, as an (is_null, obj) tuple."},
        {"set_frame_stack_at",  set_frame_stack_at, METH_VARARGS, "Set or unset an object on the stack of a generator or coroutine."},
        {"get_frame_state",  get_frame_state, METH_VARARGS, "Get frame state of a generator or coroutine."},
        {"set_frame_state",  set_frame_state, METH_VARARGS, "Set frame state of a generator or coroutine."},
        {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "frame", NULL, -1, methods};

PyMODINIT_FUNC PyInit_frame(void) {
    return PyModule_Create(&module);
}
