# Create ctypes wrapper code for abstract type descriptions.
# Type descriptions are collections of typedesc instances.

# $Log$
# Revision 1.5  2005/03/11 15:40:44  theller
# Detect an 'Enum' com method, and create an __iter__ method in this class.
#
# Detect a COM enumerator by checking for the 4 Enum methods, in the
# correct order, and make this class a Python iterator by generating
# __iter__() and next() methods.  IMO it's better to do this in the
# generated code than to mix in another class.
#
# Revision 1.4  2005/03/11 10:18:02  theller
# Various fixes.  And autodetect whether to generate ctypes.com or
# comtypes wrapper code for com interfaces.
#
# Revision 1.3  2005/02/17 19:22:54  theller
# Refactoring for easier dynamic code generation.
#
# Revision 1.2  2005/02/04 18:04:24  theller
# The code generator now assumes decorators are present in the ctypes module.
#
# Revision 1.1  2005/02/04 17:01:24  theller
# Moved the code generation stuff from the sandbox to it's final location.
#

import typedesc, sys

try:
    set
except NameError:
    from sets import Set as set

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

class NeedToParseMoreError(Exception):pass
# XXX Should this be in ctypes itself?
ctypes_names = {
    "unsigned char": "c_ubyte",
    "signed char": "c_byte",
    "char": "c_char",

    "wchar_t": "c_wchar",

    "short unsigned int": "c_ushort",
    "short int": "c_short",

    "long unsigned int": "c_ulong",
    "long int": "c_long",
    "long signed int": "c_long",

    "unsigned int": "c_uint",
    "int": "c_int",

    "long long unsigned int": "c_ulonglong",
    "long long int": "c_longlong",

    "double": "c_double",
    "float": "c_float",

    # Hm...
    "void": "None",
}

################

def storage(t):
    # return the size and alignment of a type
    if isinstance(t, typedesc.Typedef):
        return storage(t.typ)
    elif isinstance(t, typedesc.ArrayType):
        s, a = storage(t.typ)
        m = t.max
        
        return s * (int(m) - int(t.min) + 1), a
    return int(t.size), int(t.align)

class PackingError(Exception):
    pass

def _calc_packing(struct, fields, pack, isStruct):
    # Try a certain packing, raise PackingError if field offsets,
    # total size ot total alignment is wrong.
    if struct.size is None: # incomplete struct
        return -1
    if struct.name in dont_assert_size:
        return None
    if struct.bases:
        size = struct.bases[0].size
        total_align = struct.bases[0].align
    else:
        size = 0
        total_align = 8 # in bits
    for i, f in enumerate(fields):
        if type(f) is typedesc.Field:
            if f.bits:
    ##            print "##XXX FIXME"
                return -2 # XXX FIXME
            s, a = storage(f.typ)
#        elif type(f) is typedesc.Union:
#            s, a = storage(f)
        else:
            raise PackingError, "unknown alignment field"
        if pack is not None:
            a = min(pack, a)
        if size % a:
            size += a - size % a
        if isStruct:
            if size != f.offset:
                raise PackingError, "field offset (%s/%s)" % (size, f.offset)
            size += s
        else:
            size = max(size, s)
        total_align = max(total_align, a)
    if total_align != struct.align:
        raise PackingError, "total alignment (%s/%s)" % (total_align, struct.align)
    a = total_align
    if pack is not None:
        a = min(pack, a)
    if size % a:
        size += a - size % a
    if size != struct.size:
        raise PackingError, "total size (%s/%s)" % (size, struct.size)

def calc_packing(struct, fields):
    # try several packings, starting with unspecified packing
    isStruct = isinstance(struct, typedesc.Structure)
    for pack in [None, 16*8, 8*8, 4*8, 2*8, 1*8]:
        try:
            _calc_packing(struct, fields, pack, isStruct)
        except PackingError, details:
            continue
        else:
            if pack is None:
                return None
            return pack/8
    import pdb; pdb.set_trace()
    raise PackingError, "PACKING FAILED: %s" % details

def decode_value(init):
    # decode init value from gccxml
    if init[0] == "0":
        return int(init, 16) # hex integer
    elif init[0] == "'":
        return eval(init) # character
    elif init[0] == '"':
        return eval(init) # string
    return int(init) # integer

def get_real_type(tp):
    if type(tp) is typedesc.Typedef:
        return get_real_type(tp.typ)
    return tp

# XXX These should be filtered out in gccxmlparser.
dont_assert_size = set(
    [
    "__si_class_type_info_pseudo",
    "__class_type_info_pseudo",
    ]
    )

################################################################

class Generator(object):
    def __init__(self, output,
                 use_decorators=False,
                 known_symbols=None,
                 searched_dlls=None):
        self.output = output
##        self.stream = StringIO.StringIO()
##        self.imports = StringIO.StringIO()
        self.stream = self.imports = self.output
        self.use_decorators = use_decorators
        self.known_symbols = known_symbols or {}
        self.searched_dlls = searched_dlls or []
        self.need_more_ids = set()
        
        self.tagged_items = {}
        self.pointer_names_defined = set()

        self.done = set() # type descriptions that have been generated
        self.names = set() # names that have been generated

    def init_value(self, t, init):
        tn = self.type_name(t, False)
        if tn in ["c_ulonglong", "c_ulong", "c_uint", "c_ushort", "c_ubyte"]:
            return decode_value(init)
        elif tn in ["c_longlong", "c_long", "c_int", "c_short", "c_byte"]:
            return decode_value(init)
        elif tn in ["c_float", "c_double"]:
            return float(init)
        elif tn == "POINTER(c_char)":
            if init[0] == '"':
                value = eval(init)
            else:
                value = int(init, 16)
            return value
        elif tn == "POINTER(c_wchar)":
            if init[0] == '"':
                value = eval(init)
            else:
                value = int(init, 16)
            if isinstance(value, str):
                value = value[:-1] # gccxml outputs "D\000S\000\000" for L"DS"
                value = value.decode("utf-16") # XXX Is this correct?
            return value
        elif tn == "c_void_p":
            if init[0] == "0":
                value = int(init, 16)
            else:
                value = int(init) # hm..
            # Hm, ctypes represents them as SIGNED int
            return value
        elif tn == "c_char":
            return decode_value(init)
        elif tn == "c_wchar":
            value = decode_value(init)
            if isinstance(value, int):
                return unichr(value)
            return value
        elif tn.startswith("POINTER("):
            # Hm, POINTER(HBITMAP__) for example
            return decode_value(init)
        else:
            raise ValueError, "cannot decode %s(%r)" % (tn, init)

    def pointer_type_name(self, t, generate):
        assert isinstance(t, typedesc.PointerType)
        result = "POINTER(%s)" % self.type_name(t.typ, generate)
        # XXX Better to inspect t.typ!
        if result.startswith("POINTER(WINFUNCTYPE"):
            return result[len("POINTER("):-1]
        if result.startswith("POINTER(CFUNCTYPE"):
            return result[len("POINTER("):-1]
        elif result == "POINTER(None)":
            return "c_void_p"
        return result
    def type_name(self, t, generate=True):
        # Return a string, containing an expression which can be used to
        # refer to the type. Assumes the * namespace is available.
        if isinstance(t, typedesc.PointerType):
            result = self.type_name(t.typ, generate)
            if not (result.startswith("WINFUNCTYPE") or result.startswith("CFUNCTYPE")):
            
                result = "LP_%s" % (result, )
            # XXX Better to inspect t.typ!
            return result
        elif isinstance(t, typedesc.ArrayType):
            return "%s * %s" % (self.type_name(t.typ, generate), int(t.max)+1)
        elif isinstance(t, typedesc.FunctionType):
            args = [self.type_name(x, generate) for x in [t.returns] + t.arguments]
            if "__stdcall__" in t.attributes:
                return "WINFUNCTYPE(%s)" % ", ".join(args)
            else:
                return "CFUNCTYPE(%s)" % ", ".join(args)
        elif isinstance(t, typedesc.CvQualifiedType):
            # const and volatile are ignored
            return "%s" % self.type_name(t.typ, generate)
        elif isinstance(t, typedesc.FundamentalType):
            return ctypes_names[t.name]
        elif isinstance(t, typedesc.Structure):
            return t.name
        elif isinstance(t, typedesc.Enumeration):
            if t.name:
                return t.name
            return "c_int" # enums are integers
        elif isinstance(t, typedesc.Typedef):
            return t.name
        return t.name

    ################################################################

    def Alias(self, alias):
        if alias.typ is not None: # we can resolve it
            self.generate(alias.typ)
            if alias.alias in self.names:
                print >> self.stream, "%s = %s # alias" % (alias.name, alias.alias)
                self.names.add(alias.name)
                return
        # we cannot resolve it
        print >> self.stream, "# %s = %s # alias" % (alias.name, alias.alias)
        print "# unresolved alias: %s = %s" % (alias.name, alias.alias)
            

    def Macro(self, macro):
        # We don't know if we can generate valid, error free Python
        # code All we can do is to try to compile the code.  If the
        # compile fails, we know it cannot work, so we generate
        # commented out code.  If it succeeds, it may fail at runtime.
        code = "def %s%s: return %s # macro" % (macro.name, macro.args, macro.body)
        try:
            compile(code, "<string>", "exec")
        except SyntaxError:
            print >> self.stream, "#", code
        else:
            print >> self.stream, code
            self.names.add(macro.name)

    def StructureHead(self, head):
        for struct in head.struct.bases:
            self.generate(struct.get_head())
            self.more.add(struct)
        if head.struct.location:
            print >> self.stream, "# %s %s" % head.struct.location
        basenames = [self.type_name(b) for b in head.struct.bases]
        if basenames:
            self.need_GUID()
            method_names = [m.name for m in head.struct.members if type(m) is typedesc.Method]
            print >> self.stream, "class %s(%s):" % (head.struct.name, ", ".join(basenames))
            print >> self.stream, "    _iid_ = GUID('{}') # please look up iid and fill in!"
            if "Enum" in method_names:
                print >> self.stream, "    def __iter__(self):"
                print >> self.stream, "        return self.Enum()"
            elif method_names == "Next Skip Reset Clone".split():
                print >> self.stream, "    def __iter__(self):"
                print >> self.stream, "        return self"
                print >> self.stream
                print >> self.stream, "    def next(self):"
                print >> self.stream, "         arr, fetched = self.Next(1)"
                print >> self.stream, "         if fetched == 0:"
                print >> self.stream, "             raise StopIteration"
                print >> self.stream, "         return arr[0]"
        else:
            methods = [m for m in head.struct.members if type(m) is typedesc.Method]
            if methods:
                # Hm. We cannot generate code for IUnknown...
                print >> self.stream, "assert 0, 'cannot generate code for IUnknown'"
                print >> self.stream, "class %s(_com_interface):" % head.struct.name
            elif type(head.struct) == typedesc.Structure:
                print >> self.stream, "class %s(Structure):" % head.struct.name
            elif type(head.struct) == typedesc.Union:
                print >> self.stream, "class %s(Union):" % head.struct.name
            print >> self.stream, "    pass"
        self.names.add(head.struct.name)

    _structures = 0
    def Structure(self, struct):
        self._structures += 1
        self.generate(struct.get_head())
        self.generate(struct.get_body())

    Union = Structure
        
    _typedefs = 0
    def Typedef(self, tp):
        self._typedefs += 1
        if type(tp.typ) in (typedesc.Structure, typedesc.Union):
            self.generate(tp.typ.get_head())
            self.more.add(tp.typ)
        else:
            self.generate(tp.typ)
        if self.type_name(tp.typ) in self.known_symbols:
            stream = self.imports
        else:
            stream = self.stream
        if tp.name != self.type_name(tp.typ):
            print >> stream, "%s = %s" % \
                  (tp.name, self.type_name(tp.typ))
        self.names.add(tp.name)

    _arraytypes = 0
    def ArrayType(self, tp):
        self._arraytypes += 1
        self.generate(get_real_type(tp.typ))
        self.generate(tp.typ)

    _functiontypes = 0
    def FunctionType(self, tp):
        self._functiontypes += 1
        self.generate(tp.returns)
        self.generate_all(tp.arguments)
        
    _pointertypes = 0
    def PointerType(self, tp):
        self._pointertypes += 1
        if type(tp.typ) is typedesc.PointerType:
            self.generate(tp.typ)
        elif type(tp.typ) in (typedesc.Union, typedesc.Structure):
            self.generate(tp.typ.get_head())
            self.more.add(tp.typ)
        elif type(tp.typ) is typedesc.Typedef:
            self.generate(tp.typ)
        else:
            self.generate(tp.typ)
        
        name = self.type_name(tp, False)
        pointer_type_name = self.pointer_type_name(tp, False)
        if pointer_type_name not in self.pointer_names_defined:
            print >> self.stream, \
                "%s = %s" % (name, pointer_type_name,)
            self.pointer_names_defined.add(pointer_type_name)
              
    def CvQualifiedType(self, tp):
        self.generate(tp.typ)

    _variables = 0
    def Variable(self, tp):
        self._variables += 1
        if tp.init is None:
            # wtypes.h contains IID_IProcessInitControl, for example
            return
        try:
            value = self.init_value(tp.typ, tp.init)
        except (TypeError, ValueError), detail:
            print "Could not init", tp.name, tp.init, detail
            return
        print >> self.stream, \
              "%s = %r # Variable %s" % (tp.name,
                                         value,
                                         self.type_name(tp.typ, False))
        self.names.add(tp.name)

    _enumvalues = 0
    def EnumValue(self, tp):
        value = int(tp.value)
        print >> self.stream, \
              "%s = %d" % (tp.name, value)
        self.names.add(tp.name)
        self._enumvalues += 1

    _enumtypes = 0
    def Enumeration(self, tp):
        self._enumtypes += 1
        if tp.name:
            print >> self.stream
            print >> self.stream, "%s = c_int # enum" % tp.name
        for item in tp.values:
            self.generate(item)
            
    def Destructor(self, body):
        pass # just register it, and ignore it for now. each struct has constructor and destructor, and it it being searched for when parsing the struct fields
        
    def OperatorMethod(self, body):
        pass

    def StructureBody(self, body):
        fields = []
        methods = []
        for m in body.struct.members:
            if m in self.tagged_items:
                m = self.tagged_items[m]
                
            if type(m) is typedesc.Field:
                fields.append(m)
                if type(m.typ) is typedesc.Typedef:
                    self.generate(get_real_type(m.typ))
                #import pdb; pdb.set_trace()
                self.generate(m.typ)
            elif type(m) is typedesc.Union:
                #import pdb; pdb.set_trace()
                #fields.append(m) # happens then unions are defined in the struct 
                self.generate(m)
            elif type(m) is typedesc.Structure:
                #import pdb; pdb.set_trace()
                #fields.append(m) # happens then unions are defined in the struct 
                self.generate(m)
            elif type(m) is typedesc.Method:
                methods.append(m)
                self.generate(m.returns)
                self.generate_all(m.arguments)
            elif type(m) is typedesc.Constructor:
                pass
            elif type(m) is typedesc.Destructor:
                pass
            elif type(m) is typedesc.OperatorMethod:
                pass

            elif m not in self.tagged_items:
                import pdb; pdb.set_trace()
                raise NeedToParseMoreError(m)
            #import pdb; pdb.set_trace()
                
        
        # we don't need _pack_ on Unions (I hope, at least), and
        # not on COM interfaces:
        #
        # Hm, how to detect a COM interface with no methods? IXMLDOMCDATASection is such a beast...
##        if not isinstance(body.struct, typedesc.Union) and not methods:
        if not methods:
            pack = calc_packing(body.struct, fields)
            if pack is not None:
                print >> self.stream, "%s._pack_ = %s" % (body.struct.name, pack)

        if fields:
            if body.struct.bases:
                assert len(body.struct.bases) == 1
                self.generate(body.struct.bases[0].get_body())
            # field definition normally span several lines.
            # Before we generate them, we need to 'import' everything they need.
            # So, call type_name for each field once,
            for f in fields:
                self.type_name(f.typ)
            print >> self.stream, "%s._fields_ = [" % body.struct.name
            if body.struct.location:
                print >> self.stream, "    # %s %s" % body.struct.location
            # unnamed fields will get autogenerated names "_", "_1". "_2", "_3", ...
            unnamed_index = 0
            for f in fields:
                if not f.name:
                    if unnamed_index:
                        fieldname = "_%d" % unnamed_index
                    else:
                        fieldname = "_"
                    unnamed_index += 1
                    print >> self.stream, "    # Unnamed field renamed to '%s'" % fieldname
                else:
                    fieldname = f.name
                type_name = self.type_name(f.typ)
                
                #if type(f.typ) is typedesc.PointerType:
                #    import pdb; pdb.set_trace()
                if f.bits is None:
                    print >> self.stream, "    ('%s', %s)," % (fieldname, type_name)
                else:
                    print >> self.stream, "    ('%s', %s, %s)," % (fieldname, type_name, f.bits)
            print >> self.stream, "]"
            # generate assert statements for size and alignment
            if body.struct.size and body.struct.name not in dont_assert_size:
                size = body.struct.size // 8
                print >> self.stream, "assert sizeof(%s) == %s, sizeof(%s)" % \
                      (body.struct.name, size, body.struct.name)
                align = body.struct.align // 8
                print >> self.stream, "assert alignment(%s) == %s, alignment(%s)" % \
                      (body.struct.name, align, body.struct.name)

        if methods:
            # Ha! Autodetect ctypes.com or comtypes ;)
            if "COMMETHOD" in self.known_symbols:
                self.need_COMMETHOD()
            else:
                self.need_STDMETHOD()
            # method definitions normally span several lines.
            # Before we generate them, we need to 'import' everything they need.
            # So, call type_name for each field once,
            for m in methods:
                self.type_name(m.returns)
                for a in m.arguments:
                    self.type_name(a)
            if "COMMETHOD" in self.known_symbols:
                print >> self.stream, "%s._methods_ = [" % body.struct.name
            else:
                # ctypes.com needs baseclass methods listed as well
                if body.struct.bases:
                    basename = body.struct.bases[0].name
                    print >> self.stream, "%s._methods_ = %s._methods + [" % \
                          (body.struct.name, body.struct.bases[0].name)
                else:
                    print >> self.stream, "%s._methods_ = [" % body.struct.name
            if body.struct.location:
                print >> self.stream, "# %s %s" % body.struct.location

            if "COMMETHOD" in self.known_symbols:
                for m in methods:
                    if m.location:
                        print >> self.stream, "    # %s %s" % m.location
                    print >> self.stream, "    COMMETHOD([], %s, '%s'," % (
                        self.type_name(m.returns),
                        m.name)
                    for a in m.arguments:
                        print >> self.stream, \
                              "               ( [], %s, )," % self.type_name(a)
                    print >> self.stream, "             ),"
            else:
                for m in methods:
                    args = [self.type_name(a) for a in m.arguments]
                    print >> self.stream, "    STDMETHOD(%s, '%s', [%s])," % (
                        self.type_name(m.returns),
                        m.name,
                        ", ".join(args))
            print >> self.stream, "]"

    def find_dllname(self, func):
        if hasattr(func, "dllname"):
            return func.dllname
        name = func.name
        for dll in self.searched_dlls:
            try:
                getattr(dll, name)
            except AttributeError:
                pass
            else:
                return dll._name
##        if self.verbose:
        # warnings.warn, maybe?
##        print >> sys.stderr, "function %s not found in any dll" % name
        return None

    _loadedlibs = None
    def get_sharedlib(self, dllname):
        if self._loadedlibs is None:
            self._loadedlibs = {}
        try:
            return self._loadedlibs[dllname]
        except KeyError:
            pass
        import os
        basename = os.path.basename(dllname)
        name, ext = os.path.splitext(basename)
        self._loadedlibs[dllname] = name
        # This should be handled in another way!
##        print >> self.stream, "%s = CDLL(%r)" % (name, dllname)
        return name

    _STDMETHOD_defined = False
    def need_STDMETHOD(self):
        if self._STDMETHOD_defined:
            return
        print >> self.imports, "from ctypes.com import STDMETHOD"
        self._STDMETHOD_defined = True

    _COMMETHOD_defined = False
    def need_COMMETHOD(self):
        if self._COMMETHOD_defined:
            return
        print >> self.imports, "from comtypes import COMMETHOD"
        self._STDMETHOD_defined = True

    _GUID_defined = False
    def need_GUID(self):
        if self._GUID_defined:
            return
        self._GUID_defined = True
        modname = self.known_symbols.get("GUID")
        if modname:
            print >> self.imports, "from %s import GUID" % modname

    _functiontypes = 0
    _notfound_functiontypes = 0
    def Function(self, func):
        dllname = self.find_dllname(func)
        if dllname:
            self.generate(func.returns)
            self.generate_all(func.arguments)
            args = [self.type_name(a) for a in func.arguments]
            argnames = [a if a is not None else b for a, b in zip(func.arg_names, ["p%d" % i for i in range(1, 1+len(args))])]
            #import pdb; pdb.set_trace()
            if "__stdcall__" in func.attributes:
                cc = "stdcall"
                dt = "windll"
            else:
                cc = "cdecl"
                dt = "cdll"
            libname = self.get_sharedlib(dllname)
            print >> self.stream
            #if self.use_decorators:
            #    print >> self.stream, "@ %s(%s, %s)" % \
            #          (cc, self.type_name(func.returns), ", ".join(args))
#                print >> self.stream, "@ %s(%s, '%s', tuple([%s]))" % \
#                      (cc, self.type_name(func.returns), libname, ", ".join(args))
            #argnames = ["p%d" % i for i in range(1, 1+len(args))]
            # function definition
            #print >> self.stream, "def %s(%s):" % (func.name, ", ".join(argnames))
            if func.location:
                print >> self.stream, "# %s %s" % func.location
            print >> self.stream, "%s = %s(%s, %s) (('%s', %s.%s,),)" % \
                      (func.name, cc, self.type_name(func.returns), ", ".join(args), func.name, dt, libname)
            #print >> self.stream, "    return %s._api_(%s)" % (func.name, ", ".join(argnames))
            #if not self.use_decorators:
            #    print >> self.stream, "%s = %s(%s, %s) ('%s', windll.%s)" % \
            #          (func.name, cc, self.type_name(func.returns), ", ".join(args), func.name, libname)
#                print >> self.stream, "%s = %s(%s, '%s', tuple([%s])) (tuple(%s))" % \
#                      (func.name, cc, self.type_name(func.returns), libname, ", ".join(args), func.name)
            print >> self.stream
            self.names.add(func.name)
            self._functiontypes += 1
        else:
            self._notfound_functiontypes += 1
    def FundamentalType(self, item):
        pass # we should check if this is known somewhere
##        name = ctypes_names[item.name]
##        if name !=  "None":
##            print >> self.stream, "from ctypes import %s" % name
##        self.done.add(item)

    ########
    
    def Field(self, item):
        pass # we need this just to record the tag_id


    def generate(self, item):
        if item in self.done:
            return
            
        # putting this if here might cause inf loop if one requests the other, and the other need this one
        if hasattr(item, "struct"):
            self.tagged_items[item.struct.tag_id] = item.struct
        else:
            self.tagged_items[item.tag_id] = item
            
            
        if isinstance(item, typedesc.StructureHead):
            name = getattr(item.struct, "name", None)
            
        else:
            name = getattr(item, "name", None)
        
            
        if name in self.known_symbols:
            mod = self.known_symbols[name]
            print >> self.imports, "from %s import %s" % (mod, name)
            self.done.add(item)
            if isinstance(item, typedesc.Structure):
                self.done.add(item.get_head())
                self.done.add(item.get_body())
            return
        mth = getattr(self, type(item).__name__)
        # to avoid infinite recursion, we have to mark it as done
        # before actually generating the code.
        
        self.done.add(item)
        try:
            mth(item)
        except NeedToParseMoreError, e:
            print "missing items " + str(e)
            
            #import pdb; pdb.set_trace()
            #self.done.remove(item)
            #self.more.add(item)

    def generate_all(self, items):
        
        for item in items:
            self.generate(item)

    def register_tag_id(self, items):
        for item in items:
            if hasattr(item, "struct"):
                self.tagged_items[item.struct.tag_id] = item.struct
            else:
                self.tagged_items[item.tag_id] = item
                
    def generate_code(self, items):
        print >> self.imports, "from ctypes import *"
        print >> self.imports, "cdecl = CFUNCTYPE"
        print >> self.imports, "stdcall = WINFUNCTYPE"
        items = set(items)
        loops = 0
        self.register_tag_id(items)
        while items:
            loops += 1
            self.more = set()
            self.generate_all(items)
            
            items |= self.more
            items -= self.done
            #print items
            
            

##        self.output.write(self.imports.getvalue())
##        self.output.write("\n\n")
##        self.output.write(self.stream.getvalue())

        return loops

    def print_stats(self, stream):
        total = self._structures + self._functiontypes + self._enumtypes + self._typedefs +\
                self._pointertypes + self._arraytypes
        print >> stream, "###########################"
        print >> stream, "# Symbols defined:"
        print >> stream, "#"
        print >> stream, "# Variables:          %5d" % self._variables
        print >> stream, "# Struct/Unions:      %5d" % self._structures
        print >> stream, "# Functions:          %5d" % self._functiontypes
        print >> stream, "# Enums:              %5d" % self._enumtypes
        print >> stream, "# Enum values:        %5d" % self._enumvalues
        print >> stream, "# Typedefs:           %5d" % self._typedefs
        print >> stream, "# Pointertypes:       %5d" % self._pointertypes
        print >> stream, "# Arraytypes:         %5d" % self._arraytypes
        print >> stream, "# unknown functions:  %5d" % self._notfound_functiontypes
        print >> stream, "#"
        print >> stream, "# Total symbols: %5d" % total
        print >> stream, "###########################"

################################################################

def generate_code(xmlfile,
                  outfile,
                  expressions=None,
                  symbols=None,
                  verbose=False,
                  use_decorators=False,
                  known_symbols=None,
                  searched_dlls=None,
                  types=None):
    # expressions is a sequence of compiled regular expressions,
    # symbols is a sequence of names
    from gccxmlparser import parse
    items = parse(xmlfile)

    # filter symbols to generate
    todo = []

    if types:
        items = [i for i in items if isinstance(i, types)]
    
    if symbols:
        syms = set(symbols)
        for i in items:
            if i.name in syms:
                todo.append(i)
                syms.remove(i.name)

        if syms:
            print "symbols not found", list(syms)

    if expressions:
        for i in items:
            for s in expressions:
                if i.name is None:
                    continue
                match = s.match(i.name)
                # we only want complete matches
                if match and match.group() == i.name:
                    todo.append(i)
                    break
    if symbols or expressions:
        items = todo

    ################
    gen = Generator(outfile,
                    use_decorators=use_decorators,
                    known_symbols=known_symbols,
                    searched_dlls=searched_dlls)

    loops = gen.generate_code(items)
    if verbose:
        gen.print_stats(sys.stderr)
        print >> sys.stderr, "needed %d loop(s)" % loops

