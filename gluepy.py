
from threading import Lock
import asyncio
import ctypes
from ctypes import cast, POINTER, Structure, CFUNCTYPE, c_int, c_char_p, c_bool, c_double, c_longlong, c_void_p, c_uint32
import os

from _ctypes import Union, byref

# Enums


class GlueState(ctypes.c_int):
    NONE = 0
    CONNECTING = 1
    CONNECTED = 2
    INITIALIZED = 3
    DISCONNECTED = 4


class GlueNotificationSeverity(ctypes.c_int):
    glue_severity_none = 0
    glue_severity_low = 1
    glue_severity_medium = 2
    glue_severity_high = 3
    glue_severity_critical = 4


class GlueType(ctypes.c_int):
    glue_none = 0
    glue_bool = 1
    glue_int = 2
    glue_long = 3
    glue_double = 4
    glue_string = 5
    glue_datetime = 6
    glue_tuple = 7
    glue_composite = 8
    glue_composite_array = 9

# union for glue_value


class GlueValueUnion(Union):
    _fields_ = [
        ("b", c_bool),               # Boolean value
        ("i", c_int),                # Integer value
        ("l", c_longlong),           # Long long value
        ("d", c_double),             # Double value
        ("s", c_char_p),             # String value

        ("bb", POINTER(c_bool)),     # Pointer to boolean array
        ("ii", POINTER(c_int)),      # Pointer to integer array
        ("ll", POINTER(c_longlong)),  # Pointer to long long array
        ("dd", POINTER(c_double)),   # Pointer to double array
        ("ss", POINTER(c_char_p)),   # Pointer to string array

        ("composite", c_void_p),    # Pointer to glue_arg - as void*
        ("tuple", c_void_p)         # Pointer to another glue_value - as void*
    ]


class GlueValue(Structure):
    _fields_ = [
        ("data", GlueValueUnion),    # The union for actual data
        ("type", c_int),             # glue_type (as integer)
        ("len", c_int)               # Length for array types
    ]


class GlueArg(Structure):
    _fields_ = [
        ("name", c_char_p),
        ("value", GlueValue)
    ]


class GluePayload(Structure):
    _fields_ = [
        ("reader", c_void_p),
        ("origin", c_char_p),
        ("status", c_int),
        ("args", POINTER(GlueArg)),
        ("args_len", c_int)
    ]


# Callback function types
GlueInitCallback = CFUNCTYPE(
    None, c_int, c_char_p, POINTER(GluePayload), c_void_p)
GlueWindowCallback = CFUNCTYPE(None, c_int, c_char_p, c_void_p)
GlueEndpointStatusCallback = CFUNCTYPE(
    None, c_char_p, c_char_p, c_bool, c_void_p)
InvocationCallback = CFUNCTYPE(
    None, c_char_p, c_void_p, POINTER(GluePayload), c_void_p)
StreamCallback = CFUNCTYPE(c_bool, c_char_p, c_void_p,
                           POINTER(GluePayload), POINTER(c_char_p))
PayloadFunction = CFUNCTYPE(None, c_char_p, c_void_p, POINTER(GluePayload))
ContextFunction = CFUNCTYPE(
    None, c_char_p, c_char_p, POINTER(GlueValue), c_void_p)
AppCallbackFunction = CFUNCTYPE(
    None, c_int, c_void_p, POINTER(GluePayload), c_void_p)

# Add the current folder to the DLL search path
if hasattr(os, "add_dll_directory"):
    os.add_dll_directory(os.getcwd())
else:
    os.environ["PATH"] += os.pathsep + os.getcwd()

# Load DLL
dll_path = os.path.join(os.getcwd(), "GlueCLILib.dll")
glue_lib = ctypes.CDLL(dll_path)

# Function prototypes
glue_lib.glue_ensure_clr_.argtypes = [
    ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
glue_lib.glue_ensure_clr_.restype = ctypes.c_int

glue_lib.glue_init.argtypes = [c_char_p, GlueInitCallback, c_void_p]
glue_lib.glue_init.restype = c_int

glue_lib.glue_subscribe_endpoints_status.argtypes = [
    GlueEndpointStatusCallback, c_void_p]
glue_lib.glue_subscribe_endpoints_status.restype = c_void_p

glue_lib.glue_set_save_state.argtypes = [InvocationCallback, c_void_p]
glue_lib.glue_set_save_state.restype = c_int

glue_lib.glue_register_window.argtypes = [
    c_void_p, GlueWindowCallback, c_char_p, c_void_p, c_bool]
glue_lib.glue_register_window.restype = c_void_p

glue_lib.glue_register_main_window.argtypes = [
    c_void_p, AppCallbackFunction, GlueWindowCallback, c_char_p, c_void_p]
glue_lib.glue_register_main_window.restype = c_void_p

glue_lib.glue_is_launched_by_gd.restype = c_bool

glue_lib.glue_get_starting_context_reader.restype = c_void_p

glue_lib.glue_register_endpoint.argtypes = [
    c_char_p, InvocationCallback, c_void_p]
glue_lib.glue_register_endpoint.restype = c_int

glue_lib.glue_register_streaming_endpoint.argtypes = [
    c_char_p, StreamCallback, InvocationCallback, c_void_p]
glue_lib.glue_register_streaming_endpoint.restype = c_void_p

glue_lib.glue_open_streaming_branch.argtypes = [c_void_p, c_char_p]
glue_lib.glue_open_streaming_branch.restype = c_void_p

glue_lib.glue_invoke.argtypes = [c_char_p, POINTER(
    GlueArg), c_int, PayloadFunction, c_void_p]
glue_lib.glue_invoke.restype = c_int

glue_lib.glue_invoke_all.argtypes = [c_char_p, POINTER(GlueArg), c_int, CFUNCTYPE(
    None, c_char_p, c_void_p, POINTER(GluePayload), c_int), c_void_p]
glue_lib.glue_invoke_all.restype = c_int

glue_lib.glue_gc.restype = c_int

glue_lib.glue_get_value_reader.argtypes = [GlueValue]
glue_lib.glue_get_value_reader.restype = c_void_p

glue_lib.glue_read_json.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_json.restype = c_char_p

glue_lib.glue_read_glue_value.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_glue_value.restype = GlueValue

glue_lib.glue_read_b.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_b.restype = c_bool

glue_lib.glue_read_i.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_i.restype = c_int

glue_lib.glue_read_l.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_l.restype = c_longlong

glue_lib.glue_read_d.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_d.restype = c_double

glue_lib.glue_read_s.argtypes = [c_void_p, c_char_p]
glue_lib.glue_read_s.restype = c_char_p

glue_lib.glue_read_context.argtypes = [
    c_char_p, c_char_p, ContextFunction, c_void_p]
glue_lib.glue_read_context.restype = c_int

glue_lib.glue_read_context_sync.argtypes = [c_char_p]
glue_lib.glue_read_context_sync.restype = c_void_p

glue_lib.glue_write_context.argtypes = [c_char_p, c_char_p, GlueValue, c_bool]
glue_lib.glue_write_context.restype = c_void_p

glue_lib.glue_get_context_writer.argtypes = [c_char_p, c_char_p]
glue_lib.glue_get_context_writer.restype = c_void_p

glue_lib.glue_push_payload.argtypes = [
    c_void_p, POINTER(GlueArg), c_int, c_bool]
glue_lib.glue_push_payload.restype = c_void_p

glue_lib.glue_push_json_payload.argtypes = [c_void_p, c_char_p, c_bool]
glue_lib.glue_push_json_payload.restype = c_void_p

glue_lib.glue_push_failure.argtypes = [c_void_p, c_char_p]
glue_lib.glue_push_failure.restype = c_int

glue_lib.glue_subscribe_context.argtypes = [
    c_char_p, c_char_p, ContextFunction, c_void_p]
glue_lib.glue_subscribe_context.restype = c_void_p

glue_lib.glue_subscribe_stream.argtypes = [
    c_char_p, PayloadFunction, POINTER(GlueArg), c_int, c_void_p]
glue_lib.glue_subscribe_stream.restype = c_void_p

glue_lib.glue_subscribe_single_stream.argtypes = [
    c_char_p, PayloadFunction, POINTER(GlueArg), c_int, c_void_p]
glue_lib.glue_subscribe_single_stream.restype = c_void_p

glue_lib.glue_app_register_factory.argtypes = [
    c_char_p, AppCallbackFunction, c_char_p, c_void_p]
glue_lib.glue_app_register_factory.restype = c_void_p

glue_lib.glue_app_announce_instance.argtypes = [
    c_void_p, c_void_p, AppCallbackFunction, GlueWindowCallback, c_void_p]
glue_lib.glue_app_announce_instance.restype = c_int

glue_lib.glue_raise_simple_notification.argtypes = [
    c_char_p, c_char_p, GlueNotificationSeverity, c_void_p]
glue_lib.glue_raise_simple_notification.restype = c_int

glue_lib.glue_destroy_resource.argtypes = [c_void_p]
glue_lib.glue_destroy_resource.restype = c_int

glue_lib.glue_read_async_result.argtypes = [
    c_void_p, POINTER(POINTER(GlueValue)), c_uint32]
glue_lib.glue_read_async_result.restype = c_int


def glue_ensure_clr(version=None, build_flavor=None, assembly=None):
    """
    Ensures the CLR is loaded with the specified version and build flavor.
    :param version: The CLR version as a string (e.g., "v4.0.30319") or None for the latest version.
    :param build_flavor: The build flavor (e.g., "wks" for workstation, "svr" for server) or None for default.
    :param assembly: The assembly to initialize the glue clr with or None for default.
    :return: Result code from glue_ensure_clr_.
    """
    version = version.encode('utf-8') if version else None
    build_flavor = build_flavor.encode('utf-8') if build_flavor else None
    assembly = assembly.encode('utf-8') if assembly else None
    return glue_lib.glue_ensure_clr_(version, build_flavor, assembly)


def get_glue_type_name(value_type):
    glue_type_names = {
        0: "glue_none",
        1: "glue_bool",
        2: "glue_int",
        3: "glue_long",
        4: "glue_double",
        5: "glue_string",
        6: "glue_datetime",
        7: "glue_tuple",
        8: "glue_composite",
        9: "glue_composite_array",
    }
    return glue_type_names.get(value_type, f"Unknown({value_type})")


def translate_glue_value(glue_value):
    """
    Converts a glue_value to a Python-friendly object.
    """
    value = None

    # Handle scalar types
    if glue_value.type == GlueType.glue_bool:
        value = glue_value.data.b
    elif glue_value.type == GlueType.glue_int:
        value = glue_value.data.i
    elif glue_value.type == GlueType.glue_long:
        value = glue_value.data.l
    elif glue_value.type == GlueType.glue_double:
        value = glue_value.data.d
    elif glue_value.type == GlueType.glue_string:
        value = glue_value.data.s.decode(
            "utf-8") if glue_value.data.s else None

    # Handle arrays (support empty arrays as well)
    elif glue_value.type == GlueType.glue_bool and glue_value.len >= 0:
        value = [glue_value.data.bb[i] for i in range(glue_value.len)]
    elif glue_value.type == GlueType.glue_int and glue_value.len >= 0:
        value = [glue_value.data.ii[i] for i in range(glue_value.len)]
    elif glue_value.type == GlueType.glue_long and glue_value.len >= 0:
        value = [glue_value.data.ll[i] for i in range(glue_value.len)]
    elif glue_value.type == GlueType.glue_double and glue_value.len >= 0:
        value = [glue_value.data.dd[i] for i in range(glue_value.len)]
    elif glue_value.type == GlueType.glue_string and glue_value.len >= 0:
        value = [glue_value.data.ss[i].decode(
            "utf-8") if glue_value.data.ss[i] else None for i in range(glue_value.len)]

    # Handle composites (dictionary-like)
    elif glue_value.type == GlueType.glue_composite:
        if glue_value.data.composite:
            composite = cast(glue_value.data.composite, POINTER(
                GlueArg * glue_value.len)).contents
            value = {c.name.decode("utf-8"): translate_glue_value(c.value)
                     for c in composite[:glue_value.len]}
        else:
            value = {}

    # Handle tuples (list-like)
    elif glue_value.type == GlueType.glue_tuple:
        if glue_value.data.tuple:
            tuple_values = cast(glue_value.data.tuple, POINTER(
                GlueValue * glue_value.len)).contents
            value = [translate_glue_value(tv)
                     for tv in tuple_values[:glue_value.len]]
        else:
            value = None

    # Handle composite arrays (list of dictionaries)
    elif glue_value.type == GlueType.glue_composite_array:
        if glue_value.data.composite:
            composite_array = cast(glue_value.data.composite, POINTER(
                GlueArg * glue_value.len)).contents
            value = [translate_glue_value(c.value)
                     for c in composite_array[:glue_value.len]]
        else:
            value = None

    return value


def payload_to_object(payload):
    """
    Converts a glue_payload into a Python-friendly object.
    Each glue_arg in the payload becomes a key-value pair in the resulting dictionary.
    """
    python_object = {}
    args = payload.args

    for i in range(payload.args_len):
        arg = args[i]
        name = arg.name.decode("utf-8") if arg.name else f"arg_{i}"
        python_object[name] = translate_glue_value(arg.value)

    return python_object


def object_to_glue_value(py_object):
    """
    Translates a Python-native object to a glue_value structure.
    Supports:
    - Scalars (int, float, bool, str)
    - Lists (homogeneous or mixed) - mixed are mapped to tuples
    - Dictionaries (mapped to glue_composite)
    - Lists of dictionaries (mapped to glue_composite_array)
    """
    glue_value = GlueValue()

    if not py_object:
        glue_value.type = GlueType.glue_none
        glue_value.len = -1
        return glue_value

    # Handle scalars
    if isinstance(py_object, bool):
        glue_value.data.b = py_object
        glue_value.type = GlueType.glue_bool
        glue_value.len = -1
    elif isinstance(py_object, int):
        glue_value.data.l = py_object
        glue_value.type = GlueType.glue_long
        glue_value.len = -1
    elif isinstance(py_object, float):
        glue_value.data.d = py_object
        glue_value.type = GlueType.glue_double
        glue_value.len = -1
    elif isinstance(py_object, str):
        glue_value.data.s = py_object.encode("utf-8")
        glue_value.type = GlueType.glue_string
        glue_value.len = -1

    # Handle lists (homogeneous or mixed types)
    elif isinstance(py_object, list):
        glue_value.len = len(py_object)
        if all(isinstance(x, bool) for x in py_object):
            glue_value.data.bb = (c_bool * len(py_object))(*py_object)
            glue_value.type = GlueType.glue_bool
        elif all(isinstance(x, int) for x in py_object):
            glue_value.data.ll = (c_longlong * len(py_object))(*py_object)
            glue_value.type = GlueType.glue_long
        elif all(isinstance(x, float) for x in py_object):
            glue_value.data.dd = (c_double * len(py_object))(*py_object)
            glue_value.type = GlueType.glue_double
        elif all(isinstance(x, str) for x in py_object):
            glue_value.data.ss = (c_char_p * len(py_object)
                                  )(*(s.encode("utf-8") for s in py_object))
            glue_value.type = GlueType.glue_string
        else:
            # Mixed-type list: Convert each item to a glue_value and treat as a tuple
            glue_values = (GlueValue * len(py_object))()
            for i, item in enumerate(py_object):
                glue_values[i] = object_to_glue_value(item)
            glue_value.data.tuple = cast(
                glue_values, c_void_p)  # cast to void*
            glue_value.type = GlueType.glue_tuple

    # Handle dictionaries (nested maps, composites)
    elif isinstance(py_object, dict):
        glue_args = (GlueArg * len(py_object))()
        for i, (key, value) in enumerate(py_object.items()):
            glue_args[i].name = key.encode("utf-8")
            glue_args[i].value = object_to_glue_value(value)
        glue_value.data.composite = cast(glue_args, c_void_p)  # cast to void*
        glue_value.type = GlueType.glue_composite
        glue_value.len = len(py_object)

    # Handle lists of dictionaries (mapped to glue_composite_array)
    elif isinstance(py_object, list) and all(isinstance(x, dict) for x in py_object):
        glue_args_array = (GlueArg * len(py_object))()
        for i, item in enumerate(py_object):
            glue_args_array[i].value = object_to_glue_value(item)
        glue_value.data.composite = cast(
            glue_args_array, c_void_p)  # cast to void*
        glue_value.type = GlueType.glue_composite_array
        glue_value.len = len(py_object)

    # Unsupported types
    else:
        raise ValueError(f"Unsupported Python object type: {type(py_object)}")

    return glue_value


def create_glue_arg(name, py_value):
    """
    Creates a GlueArg from a name and a Python-native value.

    Args:
        name (str): The name of the GlueArg.
        py_value (any): The Python-native value to be converted to a GlueValue.

    Returns:
        GlueArg: A GlueArg with the given name and value.
    """
    glue_arg = GlueArg()
    glue_arg.name = name.encode("utf-8")
    glue_arg.value = object_to_glue_value(py_value)
    return glue_arg


def create_args(py_map):
    """
    Creates an array of GlueArg structures from a Python dictionary.

    Args:
        py_map (dict): A Python dictionary where keys are strings and values can be any Python-native type.

    Returns:
        POINTER(GlueArg): A ctypes array of GlueArg structures.
    """
    if not isinstance(py_map, dict):
        raise ValueError("Input must be a dictionary.")

    glue_args = (GlueArg * len(py_map))()  # Create an array of GlueArg
    for i, (key, value) in enumerate(py_map.items()):
        glue_args[i].name = key.encode("utf-8")
        glue_args[i].value = object_to_glue_value(
            value)  # Convert the value to GlueValue

    return glue_args


class PayloadPusher:
    def __init__(self, result_endpoint):
        self.result_endpoint = result_endpoint

    def push(self, result_obj):
        """
        Encodes multiple result objects and pushes them as a list of GlueArgs.

        Args:
            result_obj (dict): A dictionary where keys are argument names and values are their corresponding data.
        """
        glue_args = create_args(
            result_obj)  # Convert the dictionary to GlueArgs
        glue_lib.glue_push_payload(
            self.result_endpoint,
            # Correctly cast the GlueArg array
            cast(glue_args, POINTER(GlueArg)),
            len(result_obj),
            False
        )


context_callback_references = []


def subscribe_context(context_name, field_path, on_update):
    """
    Sugar method for glue_subscribe_context.

    Args:
        context_name (str): Name of the context to subscribe to.
        field_path (str): Field path to subscribe to.
        on_update (callable): Callback function for updates.

    Returns:
        callable: A lambda that unsubscribes the callback when called.
    """
    def context_callback(context_name_ptr, field_path_ptr, value_ptr, cookie):
        context_name = context_name_ptr.decode("utf-8")
        field_path = field_path_ptr.decode("utf-8")
        if value_ptr:
            value = translate_glue_value(value_ptr.contents)
        else:
            value = None
        on_update(context_name, field_path, value)

    cxt_callback = ContextFunction(context_callback)
    context_callback_references.append(cxt_callback)

    subscription = glue_lib.glue_subscribe_context(
        context_name.encode("utf-8"),
        field_path.encode("utf-8"),
        cxt_callback,
        None
    )

    return lambda: (
        glue_lib.glue_destroy_resource(subscription),
        context_callback_references.remove(cxt_callback)
    )


def register_endpoint(endpoint_name, argument_handler):
    """
    Registers a Glue endpoint and provides a result pusher for the user.

    Args:
        endpoint_name (str): Name of the endpoint to register.
        argument_handler (callable): A lambda or function that processes decoded arguments
                                     and uses the result pusher to send results.
    """

    def endpoint_callback(endpoint_name_ptr, cookie, payload_ptr, result_endpoint):
        # Decode the endpoint name
        endpoint_name = endpoint_name_ptr.decode("utf-8")

        # Access and decode the payload
        if payload_ptr:
            payload = payload_ptr.contents
            args = [
                {arg.name.decode("utf-8"): translate_glue_value(arg.value)}
                for arg in payload.args[:payload.args_len]
            ]
        else:
            args = None

        # Create a result pusher for the user
        payload_pusher = PayloadPusher(result_endpoint)

        # Call the argument handler with args and payload_pusher
        argument_handler(args, payload_pusher)

    # Register the endpoint using the callback
    callback_instance = InvocationCallback(endpoint_callback)
    ptr = glue_lib.glue_register_endpoint(
        endpoint_name.encode("utf-8"), callback_instance, None)
    active_callbacks.append(callback_instance)
    return lambda: (
        active_callbacks.remove(callback_instance),
        glue_lib.glue_destroy_resource(ptr)
    )


active_callbacks = []
callback_lock = Lock()


def invoke_method(method_name, args, result_callback):
    """
    Simplifies invoking a Glue method by handling argument encoding and result translation.

    Args:
        method_name (str): The name of the method to invoke.
        args (dict): A dictionary of arguments to pass to the method.
        result_callback (callable): A callback to handle the translated result.
    """
    # Convert Python args to GlueArgs
    glue_args = create_args(args)

    # Define the result handler
    def result_handler(origin, cookie, payload_ptr):
        # Translate payload to Python-friendly result

        if payload_ptr:
            payload = payload_ptr.contents
            result = {
                arg.name.decode("utf-8"): translate_glue_value(arg.value)
                for arg in payload.args[:payload.args_len]
            }
        else:
            result = None
        if result_callback:
            result_callback(result)

        # Remove callback from active list after execution
        if result_callback:
            with callback_lock:
                if result_handler_instance in active_callbacks:
                    active_callbacks.remove(result_handler_instance)

    if result_callback:
        # Create the result callback instance
        result_handler_instance = PayloadFunction(result_handler)
        # Store the callback reference to ensure it stays alive
        with callback_lock:
            active_callbacks.append(result_handler_instance)
    else:
        result_handler_instance = ctypes.cast(None, PayloadFunction)

    # Invoke the method
    glue_lib.glue_invoke(
        method_name.encode("utf-8"),
        cast(glue_args, POINTER(GlueArg)),
        len(glue_args),
        result_handler_instance,
        None
    )


def subscribe_endpoint_status(callback):
    def endpoint_status_callback(endpoint_name, origin, state, cookie):
        endpoint_name = endpoint_name.decode('utf-8') if endpoint_name else ""
        origin = origin.decode('utf-8') if origin else ""
        callback(endpoint_name, origin, state)

    callback_instance = GlueEndpointStatusCallback(endpoint_status_callback)
    ptr = glue_lib.glue_subscribe_endpoints_status(callback_instance, None)
    active_callbacks.append(callback_instance)

    return lambda: (
        active_callbacks.remove(callback_instance),
        glue_lib.glue_destroy_resource(ptr)
    )


def raise_notification(title, description, severity):
    """
    Simplifies raising a simple Glue notification.

    Args:
        title (str): The title of the notification.
        description (str): The description of the notification.
        severity (GlueNotificationSeverity): The severity of the notification (e.g., NONE, LOW, HIGH).

    Example:
        raise_notification("Test Title", "This is a test notification", GlueNotificationSeverity.HIGH)
    """
    glue_lib.glue_raise_simple_notification(
        title.encode("utf-8"),
        description.encode("utf-8"),
        severity,
        None
    )


def initialize_glue(app_name, on_state_change=None):
    """
    Initializes Glue and returns an awaitable Future.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def glue_init_callback(state, message, glue_payload, cookie):
        decoded_message = message.decode('utf-8')
        if on_state_change:
            on_state_change(state, decoded_message)
        if state == GlueState.INITIALIZED:
            loop.call_soon_threadsafe(future.set_result, True)
        elif state == GlueState.DISCONNECTED:
            loop.call_soon_threadsafe(future.set_result, False)

    init_callback = GlueInitCallback(glue_init_callback)
    active_callbacks.append(init_callback)  # keep alive

    def cleanup(_):
        active_callbacks.remove(init_callback)  # cleanup

    future.add_done_callback(cleanup)

    result = glue_lib.glue_init(app_name.encode("utf-8"), init_callback, None)
    if result != 0:
        future.set_result(False)

    return future
