"""
This module defines a single Theory class for using a C theory with
clingo's python library.
"""

import sys
import ctypes
from typing import Optional, Union, Iterator, Tuple, Callable, IO
from ctypes import c_bool, c_void_p, c_int, c_double, c_uint, c_uint64, c_size_t, c_char_p, Structure
from ctypes import POINTER, byref, CFUNCTYPE, cdll
from ctypes.util import find_library

from clingo import _error_message, _error_code, _Symbol # type: ignore
from clingo import Control, ApplicationOptions, Model, StatisticsMap, Symbol
from clingo import parse_program
from clingo.ast import AST


ValueType = Union[int, float, Symbol]


class _c_value(ctypes.Union):
    # pylint: disable=bad-whitespace,bad-continuation,invalid-name
    _fields_ = [ ("integer", c_int)
               , ("double", c_double)
               , ("symbol", c_uint64)
               ]


class _c_variant(Structure):
    # pylint: disable=bad-whitespace,bad-continuation,invalid-name
    _fields_ = [ ("type", c_int)
               , ("value", _c_value)
               ]


_add_stm = CFUNCTYPE(c_bool, c_void_p, c_void_p) # pylint: disable=invalid-name


class Theory:
    """
    Interface to call functions from a C-library extending clingo's C/Python
    library.

    The functions in here are designed to be used with a `Application`
    object but can also be used with a standalone `Control` object.

    Notes
    -----
    The C library must implement the following functions:

    - `bool create(theory_t **theory)`
    - `bool destroy(theory_t *theory)`
    - `bool register(theory_t *theory, clingo_control_t* control)`
    - `bool rewrite_statement(theory_t *theory, clingo_ast_statement_t const *stm, rewrite_callback_t add, void *data)`
    - `bool prepare(theory_t *theory, clingo_control_t* control)`
    - `bool register_options(theory_t *theory, clingo_options_t* options)`
    - `bool validate_options(theory_t *theory)`
    - `bool on_model(theory_t *theory, clingo_model_t* model)`
    - `bool on_statistics(theory_t *theory, clingo_statistics_t* step, clingo_statistics_t* accu)`
    - `bool lookup_symbol(theory_t *theory, clingo_symbol_t symbol, size_t *index)`
    - `clingo_symbol_t get_symbol(theory_t *theory, size_t index)`
    - `void assignment_begin(theory_t *theory, uint32_t thread_id, size_t *index)`
    - `bool assignment_next(theory_t *theory, uint32_t thread_id, size_t *index)`
    - `void assignment_has_value(theory_t *theory, uint32_t thread_id, size_t index)`
    - `void assignment_get_value(theory_t *theory, uint32_t thread_id, size_t index, value_t *value)`
    - `bool configure(theory_t *theory, char const *key, char const *value)`
    """
    # pylint: disable=too-many-instance-attributes,line-too-long,protected-access

    def __init__(self, prefix: str, lib: str):
        """
        Loads a given library.

        Arguments
        ---------
        prefix: str
            Prefix of functions in the library.
        lib: str
            Name of the library to load.
        """
        self.__c_theory = None

        # load library
        opt_lib = find_library(lib)
        if opt_lib is None:
            raise RuntimeError('could not find library')
        self.__theory = cdll.LoadLibrary(opt_lib)

        # bool create(theory_t **theory);
        self.__create = self.__fun(prefix, "create", c_bool, [POINTER(c_void_p)])

        # bool destroy(theory_t *theory);
        self.__destroy = self.__fun(prefix, "destroy", c_bool, [c_void_p])

        # bool register(theory_t *theory, clingo_control_t* control);
        self.__register = self.__fun(prefix, "register", c_bool, [c_void_p, c_void_p])

        # bool rewrite_statement(theory_t *theory, clingo_ast_statement_t const *stm, rewrite_callback_t add, void *data)
        try:
            self.__rewrite_statement = self.__fun(prefix, "rewrite_statement", c_bool, [c_void_p, c_void_p, c_void_p])
        except AttributeError:
            self.__rewrite_statement = None

        # bool prepare(theory_t *theory, clingo_control_t* control);
        self.__prepare = self.__fun(prefix, "prepare", c_bool, [c_void_p, c_void_p])

        # bool register_options(theory_t *theory, clingo_options_t* options);
        self.__register_options = self.__fun(prefix, "register_options", c_bool, [c_void_p, c_void_p])

        # bool validate_options(theory_t *theory);
        self.__validate_options = self.__fun(prefix, "validate_options", c_bool, [c_void_p])

        # bool on_model(theory_t *theory, clingo_model_t* model);
        self.__on_model = self.__fun(prefix, "on_model", c_bool, [c_void_p, c_void_p])

        # bool on_statistics(theory_t *theory, clingo_statistics_t* step, clingo_statistics_t* accu);
        self.__on_statistics = self.__fun(prefix, "on_statistics", c_bool, [c_void_p, c_void_p, c_void_p])

        # bool lookup_symbol(theory_t *theory, clingo_symbol_t symbol, size_t *index);
        self.__lookup_symbol = self.__fun(prefix, "lookup_symbol", c_bool, [c_void_p, c_uint64, POINTER(c_size_t)], False)

        # clingo_symbol_t get_symbol(theory_t *theory, size_t index);
        self.__get_symbol = self.__fun(prefix, "get_symbol", c_uint64, [c_void_p, c_size_t], False)

        # void assignment_begin(theory_t *theory, uint32_t thread_id, size_t *index);
        self.__assignment_begin = self.__fun(prefix, "assignment_begin", None, [c_void_p, c_uint, POINTER(c_size_t)], False)

        # bool assignment_next(theory_t *theory, uint32_t thread_id, size_t *index);
        self.__assignment_next = self.__fun(prefix, "assignment_next", c_bool, [c_void_p, c_uint, POINTER(c_size_t)], False)

        # void assignment_has_value(theory_t *theory, uint32_t thread_id, size_t index);
        self.__assignment_has_value = self.__fun(prefix, "assignment_has_value", c_bool, [c_void_p, c_uint, c_size_t], False)

        # void assignment_get_value(theory_t *theory, uint32_t thread_id, size_t index, value_t *value);
        self.__assignment_get_value = self.__fun(prefix, "assignment_get_value", None, [c_void_p, c_uint, c_size_t, POINTER(_c_variant)], False)

        # bool configure(theory_t *theory, char const *key, char const *value);
        self.__configure = self.__fun(prefix, "configure", c_bool, [c_void_p, c_char_p, c_char_p])

        # create theory
        c_theory = c_void_p()
        self.__create(byref(c_theory))
        self.__c_theory = c_theory

    def __del__(self):
        if self.__c_theory is not None:
            self.__destroy(self.__c_theory)
            self.__c_theory = None

    def configure(self, key: str, value: str) -> None:
        """
        Allows for configuring a theory via key/value pairs similar to
        command line options.

        This function must be called before the theory is registered.

        Arguments
        ---------
        key: str
            The name of the option.
        value: str
            The value of the option.
        """
        self.__configure(self.__c_theory, key.encode(), value.encode())

    def register(self, control: Control) -> None:
        """
        Register the theory with the given control object.

        Arguments
        ---------
        control: Control
            Target to register with.
        """
        self.__register(self.__c_theory, control._to_c) # type: ignore

    def prepare(self, control: Control) -> None:
        """
        Prepare the theory.

        Must be called between ground and solve.

        Arguments
        ---------
        control: Control
            The associated control object.
        """
        self.__prepare(self.__c_theory, control._to_c) # type: ignore

    def rewrite_statement(self, stm: AST, add: Callable[[AST], None]) -> None:
        """
        Rewrite the given statement and call add on the rewritten version(s).

        Must be called for some theories that have to perform rewritings on the
        AST.

        Arguments
        ---------
        stm: AST
            Statement to translate.
        add: Callable[[AST], None]
            Callback for adding translated statements.
        """
        def py_add(stm, data):
            # pylint: disable=unused-argument,bare-except
            try:
                add(AST._from_c(stm))
            except:
                return False
            return True
        self.__rewrite_statement(self.__c_theory, stm._to_c, _add_stm(py_add), None)

    def register_options(self, options: ApplicationOptions) -> None:
        """
        Register the theory's options with the given application options
        object.

        Arguments
        ---------
        options: ApplicationOptions
            Target to register with.
        """

        self.__register_options(self.__c_theory, options._to_c) # type: ignore

    def validate_options(self) -> None:
        """
        Validate the options of the theory.
        """
        self.__validate_options(self.__c_theory)

    def on_model(self, model: Model) -> None:
        """
        Inform the theory that a model has been found.

        Arguments
        ---------
        model: Model
            The current model.
        """
        self.__on_model(self.__c_theory, model._to_c) # type: ignore

    def on_statistics(self, step: StatisticsMap, accu: StatisticsMap) -> None:
        """
        Add the theory's statistics to the given maps.

        Arguments
        ---------
        step: StatisticsMap
            Map for per step statistics.
        accu: StatisticsMap
            Map for accumulated statistics.
        """
        self.__on_statistics(self.__c_theory, step._to_c, accu._to_c) # type: ignore

    def lookup_symbol(self, symbol: Symbol) -> Optional[int]:
        """
        Get the integer index of a symbol assigned by the theory when a
        model is found.

        Using indices allows for efficent retreival of values.

        Arguments
        ---------
        symbol: Symbol
            The symbol to look up.

        Returns
        -------
        Optional[int]
            The index of the value if found.
        """
        c_index = c_size_t()
        if self.__lookup_symbol(self.__c_theory, symbol._to_c, byref(c_index)): # type: ignore
            return c_index.value
        return None

    def get_symbol(self, index: int) -> Symbol:
        """
        Get the symbol associated with an index.

        The index must be valid.

        Arguments
        ---------
        index: int
            Index to retreive.

        Returns
        -------
        Symbol
            The associated symbol.
        """
        return _Symbol(self.__get_symbol(self.__c_theory, index))

    def has_value(self, thread_id: int, index: int) -> bool:
        """
        Check if the given symbol index has a value in the current model.

        Arguments
        ---------
        thread_id: int
            The index of the solving thread that found the model.
        index: int
            Index to retreive.

        Returns
        -------
        bool
            Whether the given index has a value.
        """
        return self.__assignment_has_value(self.__c_theory, thread_id, index)

    def get_value(self, thread_id: int, index: int) -> ValueType:
        """
        Get the value of the symbol index in the current model.

        Arguments
        ---------
        thread_id: int
            The index of the solving thread that found the model.
        index: int
            Index to retreive.

        Returns
        -------
        ValueType
            The value of the index in form of an int, float, or Symbol.
        """
        c_value = _c_variant()
        self.__assignment_get_value(self.__c_theory, thread_id, index, byref(c_value))
        if c_value.type == 0:
            return c_value.value.integer
        if c_value.type == 1:
            return c_value.value.double
        if c_value.type == 2:
            return _Symbol(c_value.value.symbol)
        raise RuntimeError("must not happen")

    def assignment(self, thread_id: int) -> Iterator[Tuple[Symbol, ValueType]]:
        """
        Get all values symbol/value pairs assigned by the theory in the
        current model.

        Arguments
        ---------
        thread_id: int
            The index of the solving thread that found the model.

        Returns
        -------
        Iterator[Tuple[Symbol,ValueType]]
            An iterator over symbol/value pairs.
        """
        c_index = c_size_t()
        self.__assignment_begin(self.__c_theory, thread_id, byref(c_index))
        while self.__assignment_next(self.__c_theory, thread_id, byref(c_index)):
            yield (self.get_symbol(c_index.value), self.get_value(thread_id, c_index.value))

    def __fun(self, prefix, name, res, args, error=True):
        ret = self.__theory["{}_{}".format(prefix, name)]
        ret.restype = res
        ret.argtypes = args
        ret.errcheck = self.__handle_error if error else self.__skip_error
        return ret

    def __skip_error(self, ret, func, arguments):
        # pylint: disable=unused-argument
        return ret

    def __handle_error(self, success, func, arguments):
        if not success:
            msg = _error_message()
            code = _error_code()
            if msg is None:
                msg = "no message"
            if code in (1, 2, 4):
                raise RuntimeError(msg)
            if code == 3:
                raise MemoryError(msg)
            raise RuntimeError("unknow error")


def _parse(stream: IO[str], theory: Theory, add: Callable[[AST], None]):
    parse_program(stream.read(), lambda stm: theory.rewrite_statement(stm, add))


def parse_files(files: Iterator[str], theory: Theory, add: Callable[[AST], None]):
    """
    Helper function to ease parsing of files.

    This function calls the rewrite method of the theory on each parsed
    statement and then passes them to the callback.
    """
    parsed = False

    for name in files:
        parsed = True
        if name == "-":
            _parse(sys.stdin, theory, add)
        else:
            with open(name) as file_:
                _parse(file_, theory, add)

    if not parsed:
        _parse(sys.stdin, theory, add)
