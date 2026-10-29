import ctypes


class KeychainError(Exception):
    pass


def store_cookie(cookie: str) -> None:
    if not cookie or cookie.startswith('connect.sid=') or any(
        ord(character) < 33 or ord(character) > 126 or character == ';' for character in cookie
    ):
        raise KeychainError('Cannot save an invalid Loom session cookie.')
    security = ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
    foundation = ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
    pointer = ctypes.c_void_p
    foundation.CFStringCreateWithCString.argtypes = [pointer, ctypes.c_char_p, ctypes.c_uint32]
    foundation.CFStringCreateWithCString.restype = pointer
    foundation.CFDataCreate.argtypes = [pointer, ctypes.c_char_p, ctypes.c_long]
    foundation.CFDataCreate.restype = pointer
    foundation.CFDictionaryCreateMutable.argtypes = [pointer, ctypes.c_long, pointer, pointer]
    foundation.CFDictionaryCreateMutable.restype = pointer
    foundation.CFDictionarySetValue.argtypes = [pointer, pointer, pointer]
    foundation.CFDictionarySetValue.restype = None
    foundation.CFRelease.argtypes = [pointer]
    foundation.CFRelease.restype = None
    security.SecItemUpdate.argtypes = [pointer, pointer]
    security.SecItemUpdate.restype = ctypes.c_int32
    security.SecItemAdd.argtypes = [pointer, pointer]
    security.SecItemAdd.restype = ctypes.c_int32
    owned = []

    def retain(value):
        if not value:
            raise KeychainError('Keychain could not allocate credential storage.')
        owned.append(value)
        return value

    def constant(name):
        return pointer.in_dll(security, name).value

    try:
        service = retain(foundation.CFStringCreateWithCString(None, b'loom-mcp', 0x08000100))
        account = retain(foundation.CFStringCreateWithCString(None, b'connect.sid', 0x08000100))
        encoded = cookie.encode('ascii')
        data = retain(foundation.CFDataCreate(None, encoded, len(encoded)))
        query = retain(foundation.CFDictionaryCreateMutable(None, 0, None, None))
        changes = retain(foundation.CFDictionaryCreateMutable(None, 0, None, None))
        foundation.CFDictionarySetValue(query, constant('kSecClass'), constant('kSecClassGenericPassword'))
        foundation.CFDictionarySetValue(query, constant('kSecAttrService'), service)
        foundation.CFDictionarySetValue(query, constant('kSecAttrAccount'), account)
        foundation.CFDictionarySetValue(changes, constant('kSecValueData'), data)
        status = security.SecItemUpdate(query, changes)
        if status == -25300:
            foundation.CFDictionarySetValue(query, constant('kSecValueData'), data)
            status = security.SecItemAdd(query, None)
        if status:
            raise KeychainError('Keychain did not save the cookie. Allow access if prompted, or use manual entry.')
    finally:
        for value in reversed(owned):
            foundation.CFRelease(value)
