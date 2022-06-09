# nazov: interpret.py
# autor: Adam Fabo (xfaboa00)
# program bol vytvorený na predmet IPP na FIT-e VUT v Brne

import re
import sys
import codecs
import argparse
import xml.etree.ElementTree as ET

# návratové kódy:
# • 10 - chybějící parametr skriptu (je-li třeba) nebo použití zakázané kombinace parametrů;
# • 11 - chyba při otevírání vstupních souborů (např. neexistence, nedostatečné oprávnění);
# • 31 - chybný XML formát ve vstupním souboru (soubor není tzv. dobře formátovaný, angl. well-formed, viz [1]);
# • 32 - neočekávaná struktura XML
# • 52 - chyba při sémantických kontrolách vstupního kódu v IPPcode21 (např. použití nedefinovaného návěští, redefinice proměnné);
# • 53 - běhová chyba interpretace – špatné typy operandů;
# • 54 - běhová chyba interpretace – přístup k neexistující proměnné (rámec existuje);
# • 55 - běhová chyba interpretace – rámec neexistuje (např. čtení z prázdného zásobníku rámců);
# • 56 - běhová chyba interpretace – chybějící hodnota (v proměnné, na datovém zásobníku nebo
# v zásobníku volání);
# • 57 - běhová chyba interpretace – špatná hodnota operandu (např. dělení nulou, špatná návratová hodnota instrukce EXIT);
# • 58 - běhová chyba interpretace – chybná práce s řetězcem


# spracuje escape sequenciu v reťazci
# prevzate z
# https://stackoverflow.com/questions/4020539/process-escape-sequences-in-a-string-in-python/4020824#4020824
ESCAPE_SEQUENCE_RE = re.compile(r"""
    ( \\U........      # 8-digit hex escapes
    | \\u....          # 4-digit hex escapes
    | \\x..            # 2-digit hex escapes
    | \\[0-7]{1,3}     # Octal escapes
    | \\N\{[^}]+\}     # Unicode characters by name
    | \\[\\'"abfnrtv]  # Single-character escapes
    )""", re.UNICODE | re.VERBOSE)

def decode_escapes(s):
    def decode_match(match):
        return codecs.decode(match.group(0), 'unicode-escape')

    return ESCAPE_SEQUENCE_RE.sub(decode_match, s)



instructions = {

    "CREATEFRAME": (), "PUSHFRAME": (), "POPFRAME": (), "RETURN": (), "BREAK": (),

    "DEFVAR": ("var",), "POPS": ("var",),

    "CALL": ("label",), "JUMP": ("label",), "LABEL": ("label",),

    "PUSHS": ("symb",), "WRITE": ("symb",), "EXIT": ("symb",), "DPRINT": ("symb",),

    "MOVE": ("var", "symb"), "INT2CHAR": ("var", "symb"), "STRLEN": ("var", "symb"), "TYPE": ("var", "symb"),
    "NOT": ("var", "symb"),

    "READ": ("var", "type"),

    "ADD": ("var", "symb", "symb"), "SUB": ("var", "symb", "symb"), "MUL": ("var", "symb", "symb"),
    "IDIV": ("var", "symb", "symb"), "LT": ("var", "symb", "symb"), "GT": ("var", "symb", "symb"),
    "EQ": ("var", "symb", "symb"), "AND": ("var", "symb", "symb"), "OR": ("var", "symb", "symb"),
    "STRI2INT": ("var", "symb", "symb"), "CONCAT" : ("var", "symb", "symb"),
    "GETCHAR" : ("var", "symb", "symb"), "SETCHAR": ("var", "symb", "symb"),

    "JUMPIFNEQ": ("label", "symb", "symb"), "JUMPIFEQ": ("label", "symb", "symb"),

}

symb = ( "int", "bool", "string","nil", "var")

# regulárne výrazy na ošetrovanie argumentov inštrukcí
string_regex_escape = "\\\\([^0-9]{1}|[0-9][^0-9]|[0-9]{2}[^0-9])"

var_regex = "^(LF|TF|GF)@[a-zA-z_\-$&%*!?][0-9a-zA-z_\-$&%*!?]*$"
label_regex = "^[a-zA-z_\-$&%*!?][0-9a-zA-z_\-$&%*!?]*$"
type_regex = "^(string|int|bool)$"
bool_regex = "(true|false)$"
nil_regex = "^nil$"

# prázdna trieda pre typ nil
class Nil:
    pass

# výnimky pre jednotlivé chyby
class IppException(Exception):
    pass

class ArgMissing(IppException):     # 10
    pass

class BadXML(IppException):         # 32
    pass

class SemanticError(IppException):  # 52
    def __init__(self,message):
        self.message = message

class BadOperand(IppException):         #53
    def __init__(self,message):
        self.message = message

class VarDoesntExists(IppException):    #54
    def __init__(self,message):
        self.message = message

class FrameDoesntExists(IppException):  #55
    def __init__(self,message):
        self.message = message

class MissingValue(IppException):       #56
    def __init__(self,message):
        self.message = message

class WrongNumber(IppException):        #57
    def __init__(self,message):
        self.message = message

class BadString(IppException):          #58
    def __init__(self,message):
        self.message = message


# Trieda Data slúži na zapúzdrenie dát a zároveň definuje zopár operácií nad nimi
class Data:
    def __init__(self):
        self.program_counter = 1

        self.data_stack = []

        self.local_frame_stack = []
        self.prg_counter_stack = []

        self.labels = {}
        self.global_frame = {}
        self.tmp_frame    = {}

        self.is_tmp_frame = False

        self.ins_dict = {}

    # Skontroluje či premenna existuje
    def var_exists(self,var):
        if var[0:2] == "GF":
            if var[3:] in self.global_frame:
                return True

        elif var[0:2] == "LF":
            if len(self.local_frame_stack) == 0:
                raise FrameDoesntExists(f"Local Frame neexistuje, odkazuje sa do neho {var}")

            if var[3:] in self.local_frame_stack[-1]:
                return True

        elif var[0:2] == "TF":
            if not self.is_tmp_frame:
                raise FrameDoesntExists(f"Tmp Frame neexistuje, odkazuje sa do neho {var}")

            if var[3:] in self.tmp_frame:
                return True

        raise VarDoesntExists(f"Premenna {var} neexistuje")

    # Nastavi premennu na zadanu hodnotu
    def set_var(self,var,value):
        if self.var_exists(var):

            if var[0:2] == "GF":
                self.global_frame.update({var[3:]:value})

            elif var[0:2] == "LF":
                self.local_frame_stack[-1].update({var[3:]: value})

            elif var[0:2] == "TF":
                self.tmp_frame.update({var[3:]: value})

    # Vráti hodnotu zadanej premennej,
    def get_var(self,var):
        if self.var_exists(var):
            if var[0:2] == "GF":
                return self.global_frame[var[3:]]

            elif var[0:2] == "LF":
                return self.local_frame_stack[-1][var[3:]]

            elif var[0:2] == "TF":
                return self.tmp_frame[var[3:]]


# zisti či zadany argument je platny
def valid_argument(root,arg_type):

    att = root.attrib

    # osetri ci su atributy ok
    if "type" not in att or len(att) != 1:
        print('Nespravny atribut argumentu ', file=sys.stderr)
        return False

    # osetri ci type je ok
    if arg_type == "symb":
        if not symb.__contains__(att["type"]):
            print('Nespravny type pri symb', file=sys.stderr)
            return False
    else:
        if att["type"] != arg_type:
            print('Nespravny type', file=sys.stderr)
            return False

    # osetrenie samotnych hodnot typov
    if att["type"] == "var":
        if re.search(var_regex,root.text) is None:
            print('Zle vyhodnoteny regex pri var', file=sys.stderr)
            return False
    elif att["type"] == "label":
        if re.search(label_regex,root.text) is None:
            print('Zle vyhodnoteny regex pri label', file=sys.stderr)
            return False
    elif att["type"] == "type":
        if re.search(type_regex, root.text) is None:
            print('Zle vyhodnoteny regex pri type', file=sys.stderr)
            return False
    elif att["type"] == "bool":
        if re.search(bool_regex, root.text) is None:
            print('Zle vyhodnoteny regex pri bool', file=sys.stderr)
            return False
    elif att["type"] == "nil":
        if re.search(nil_regex, root.text) is None:
            print('Zle vyhodnoteny regex pri nil', file=sys.stderr)
            return False
    elif att["type"] == "int":
        try:
            int(root.text)
        except ValueError:
            print('Zle cislo pri int', file=sys.stderr)
            return False


    return True


# zisti či zadana inštrukcia je platna
def valid_instruction(root):
    # osetri tag
    if root.tag != "instruction":
        print('Root tag nie je instruction', file=sys.stderr)
        return False

    att = root.attrib

    # osetri ci su atributy ok
    if "order" not in att or "opcode" not in att or len(att) != 2:
        print('Nespravne argumenty instrukcie', file=sys.stderr)
        return False

    # osetri ci je order ok
    try:
        if int(att["order"]) <= 0:
            print('Instruction order <=0', file=sys.stderr)
            return False
    except ValueError:
        print('Wrong Instruction order', file=sys.stderr)
        return False

    # osetri ci instrukcia v opcode je validna
    if att["opcode"] not in instructions:
        print('Zla instrukcia za opcode', file=sys.stderr)
        return False

    # osetri ci pocet arg je spravny
    if len(root) != len(instructions[att["opcode"]]):
        print('Zly pocet argumentov', file=sys.stderr)
        return False

    # osetri ci nazov argumentov sedi, mozu byt v roznom poradi
    arg = []
    for child in root:
        arg.append(child.tag)

    for i in range(1,1 + len(root)):
        if not arg.__contains__('arg{}'.format(i)):
            print('Chyba argument {}'.format(i), file=sys.stderr)
            return False

    # osetri ci su samotne argumenty v spravnom tvare
    for i in range(1, 1 + len(root)):
        if not valid_argument(root.find('arg{}'.format(i)), instructions[att["opcode"]][i-1]):
            print('Chyba na {}. argumente od vrchu'.format(i), file=sys.stderr)
            return False


    return True

# zisti či zadany program je platny
def valid_program(root,data):
    if root.tag != "program":
        print('Root tag nie je program', file=sys.stderr)
        return False

    # skontroluje atributy korena, toto este osetrint aby tam bolo language
    for att in root.attrib:
        if att not in ("language", "name", "description"):
            print('Chyba pri argumentoch programu IPPcode21', file=sys.stderr)
            return False

    # skontroluje ci vsetky deti maju meno instruction

    counter = 1
    data.ins_dict = {}
    for child in root:  # osetrit duplicitne poradie
        if not valid_instruction(child):
            print('Chyba na {}. instrukcii od vrchu'.format(counter), file=sys.stderr)
            return False

        if data.ins_dict.get(child.attrib["order"]) is not None:
            print('Dve instrukcie s rovnakym orderom {}'.format(child.attrib["order"]), file=sys.stderr)
            return False
        else:
            data.ins_dict.update({child.attrib["order"]:1})

        counter +=1

    return True


# staticky ziska vsetky navestia z kodu a ich pozicie
# vrati dictionary
def get_labels(root):
    all_elem = root.findall("./instruction[@opcode='LABEL']")
    label_dict = {}

    for elem in all_elem:
        if list(elem.iter())[1].text in label_dict:     #ak su rovnake nazvy navesti vrati chybu
            raise SemanticError("Duplicitne navestie \"{}\"".format(list(elem.iter())[1].text))

        label_dict.update({list(elem.iter())[1].text: int(elem.attrib["order"])})

    return label_dict


def format_string(string):
    """ Nahradi dekadicke kodovanie \aa za \xbb"""

    for i in range(126):
        string = string.replace('\\{}'.format(str(i).zfill(3)),'\\x{}'.format(str(hex(i))[2:].zfill(2)))

    return string


# získa integer zo zadaného argumentu
def get_int(arg,data):

    symb_type = arg.attrib["type"]

    val = arg.text

    if symb_type == "int":
        return int(val)
    elif symb_type == "var":
        x = data.get_var(val)

        if type(x) is type(None):
            raise MissingValue(f"Error premenna s nedefinovanou hodnotou")
        elif type(x) is not int:
            raise BadOperand(f"Error ocakaval som int a dostal som {type(x)}")
        return x

    else:
        raise BadOperand(f"Error ocakaval som int alebo var  a dostal som {symb_type}")

# získa boolean zo zadaného argumentu
def get_bool(arg,data):

    symb_type = arg.attrib["type"]

    val = arg.text

    if symb_type == "bool":
        if val == "false":
            return False
        else:
            return True
    elif symb_type == "var":
        x = data.get_var(val)

        if type(x) is  type(None):
            raise MissingValue(f"Error premenna s nedefinovanou hodnotou")
        elif type(x) is not bool:
            raise BadOperand(f"Error ocakaval som int a dostal som {type(x)}")
        return x

    else:
        raise BadOperand(f"Error ocakaval som bool alebo var a dostal som {symb_type}")

# získa string zo zadaného argumentu
def get_string(arg,data):

    symb_type = arg.attrib["type"]

    val = arg.text

    if symb_type == "string":
        if val is None:
            return ""

        return str(val)
    elif symb_type == "var":
        x = data.get_var(val)

        if type(x) is  type(None):
            raise MissingValue(f"Error premenna s nedefinovanou hodnotou")
        elif type(x) is not str:
            raise BadOperand(f"Error ocakaval som str a dostal som {type(x)}")
        return x

    else:
        raise BadOperand(f"Error ocakaval som str alebo var a dostal som {symb_type}")


# **** jednotlivé funkcie pre jednotlivé inštrukcie

def createframe(data):
    data.is_tmp_frame = True
    data.tmp_frame = {}


def pushframe(data):

    if data.is_tmp_frame:
        data.local_frame_stack.append(data.tmp_frame)
        data.is_tmp_frame = False
    else:
        raise FrameDoesntExists('Error PUSHFRAME volane na nevytvoreny frame')



def popframe(data):

    if len(data.local_frame_stack) != 0:
        data.tmp_frame = data.local_frame_stack.pop()
        data.is_tmp_frame = True
    else:
        raise FrameDoesntExists('Error POPFRAME volane na nevytvoreny frame')


def defvar(ins,data):
    arg = ins.find("arg1")
    name = arg.text

    #ak uz existuje raise exception
    try:
        if data.var_exists(name):
            raise SemanticError(f'Error DEFVAR redefinicia premennej {name}')

    except VarDoesntExists:
        pass


    if name[0:2] == "GF":
        data.global_frame.update({name[3:] :None})


    elif name[0:2] == "LF":
        if len(data.local_frame_stack) == 0:
            raise FrameDoesntExists(f'Error DEFVAR {name} volane na nevytvoreny frame')

        data.local_frame_stack[-1].update({name[3:] :None})

    elif name[0:2] == "TF":
        if not data.is_tmp_frame:
            raise FrameDoesntExists(f'Error DEFVAR {name} volane na nevytvoreny frame')


        data.tmp_frame.update({name[3:] :None})

def move(ins,data):
    var = ins.find("arg1").text
    if data.var_exists(var):

        symb_arg = ins.find("arg2")
        symb_type = symb_arg.attrib["type"]


        if   symb_type == "int":
            data.set_var(var,int(symb_arg.text))

        elif symb_type == "bool":
            if symb_arg.text == "false":
                data.set_var(var, False)
            else:
                data.set_var(var, True)

        elif symb_type == "string":
            if symb_arg.text is None:
                data.set_var(var, str(""))
            else:
                data.set_var(var,str(symb_arg.text))

        elif symb_type == "nil":
            n = Nil()
            data.set_var(var, n)

        elif symb_type == "var":
            if data.var_exists(str(symb_arg.text)):
                data.set_var(var,data.get_var(str(symb_arg.text)))

# vypise symb na stdout
def write(ins, data):

    symb_arg = ins.find("arg1")
    symb_type = symb_arg.attrib["type"]

    if symb_type == "int":
        print(int(symb_arg.text),end='')
    elif symb_type == "bool":
        if symb_arg.text == "false":
            print('false',end='')
        else:
            print('true',end='')

    elif symb_type == "string":

        s = str(symb_arg.text)
        s = format_string(s)
        s = decode_escapes(s)
        print(s,end='')


    elif symb_type == "nil":
        print('', end='')

    elif symb_type == "var":
        if data.var_exists(str(symb_arg.text)):

            s = data.get_var(str(symb_arg.text))
            if s is None:
                raise MissingValue(f"Error WRITE volane s {str(symb_arg.text)} ktora ma nedefinovanu hodnotu")
            elif type(s) is (Nil):
                s = ""
            elif type(s) is bool:
                if s:
                    s = "true"
                else:
                    s = "false"
            s = str(s)
            s = format_string(s)
            s = decode_escapes(s)
            print(s,end='')


def call(ins,data):
    arg = ins.find("arg1")
    label = arg.text


    if label in data.labels:
        data.prg_counter_stack.append(data.program_counter)
        data.program_counter = data.labels[label]
    else:
        raise SemanticError('Error CALL navestie neexistuje')


def my_retrun(data):
    if len(data.prg_counter_stack) == 0:
        raise MissingValue('Error RETURN prg counter stack je prazdny')

    data.program_counter = data.prg_counter_stack.pop()

def pushs(ins,data):
    arg = ins.find("arg1")
    text = arg.text

    symb_type = arg.attrib["type"]

    if symb_type == "int":
        data.data_stack.append(int(text))
    elif symb_type == "string":
        data.data_stack.append(str(text))
    elif symb_type == "bool":
        if text == "false":
            data.data_stack.append(False)
        else:
            data.data_stack.append(True)
    elif symb_type == "nil":
        n = Nil()
        data.data_stack.append(n)
    elif symb_type == "var":
        data.data_stack.append(data.get_var(text))

def pops(ins,data):
    arg = ins.find("arg1")
    var = arg.text

    if len(data.data_stack) == 0:
        raise MissingValue("Error datovy zasobnik je prazdny")

    data.set_var(var,data.data_stack.pop())


def add(ins,data):

    arg1 = get_int(ins.find("arg2"),data)
    arg2 = get_int(ins.find("arg3"),data)

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var,arg1+arg2)



def sub(ins,data):
    arg1 = get_int(ins.find("arg2"), data)
    arg2 = get_int(ins.find("arg3"), data)

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var, arg1 - arg2)


def mul(ins,data):
    arg1 = get_int(ins.find("arg2"), data)
    arg2 = get_int(ins.find("arg3"), data)

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var, arg1 * arg2)


def idiv(ins,data):
    arg1 = get_int(ins.find("arg2"), data)
    arg2 = get_int(ins.find("arg3"), data)

    if arg2 == 0:
        raise WrongNumber("Error delenie nulou")

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var, arg1 // arg2)


def my_and(ins,data):
    arg1 = get_bool(ins.find("arg2"), data)
    arg2 = get_bool(ins.find("arg3"), data)

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var, arg1 and arg2)


def my_or(ins,data):
    arg1 = get_bool(ins.find("arg2"), data)
    arg2 = get_bool(ins.find("arg3"), data)

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var, arg1 or arg2)


def my_not(ins,data):
    arg1 = get_bool(ins.find("arg2"), data)

    var = ins.find("arg1").text
    if data.var_exists(var):
        data.set_var(var, not arg1)


def my_compare(ins,data,mode):

    var = ins.find("arg1").text
    if data.var_exists(var):

        try:
            arg1 = get_bool(ins.find("arg2"), data)
            arg2 = get_bool(ins.find("arg3"), data)

            if mode == "LT":
                data.set_var(var,arg1 < arg2)
            elif mode == "GT":
                data.set_var(var, arg1 > arg2)
            elif mode == "EQ":
                data.set_var(var, arg1 == arg2)

            return

        except BadOperand:
            pass

        try:
            arg1 = get_int(ins.find("arg2"), data)
            arg2 = get_int(ins.find("arg3"), data)

            if mode == "LT":
                data.set_var(var, arg1 < arg2)
            elif mode == "GT":
                data.set_var(var, arg1 > arg2)
            elif mode == "EQ":
                data.set_var(var, arg1 == arg2)

            return

        except BadOperand:
            pass

        try:
            arg1 = get_string(ins.find("arg2"), data)
            arg2 = get_string(ins.find("arg3"), data)

            if mode == "LT":
                data.set_var(var, arg1 < arg2)
            elif mode == "GT":
                data.set_var(var, arg1 > arg2)
            elif mode == "EQ":
                data.set_var(var, arg1 == arg2)

            return

        except BadOperand:
            pass

        #osetrenie nil pre EQ zvlast
        if mode == "EQ":
            if ins.find("arg2").attrib["type"] == "var":
                if type(data.get_var(ins.find("arg2").text)) == (Nil):
                    data.set_var(var, True)
                    return

            if ins.find("arg3").attrib["type"] == "var":

                if type(data.get_var(ins.find("arg3").text)) == (Nil):

                    data.set_var(var, True)
                    return

            if ins.find("arg2").attrib["type"] == "nil" or ins.find("arg3").attrib["type"] == "nil":
                data.set_var(var, True)
                return

        raise BadOperand("Error pri porovnavani nezhodne typy")

def int2char(ins,data):

    arg1 = get_int(ins.find("arg2"), data)

    var = ins.find("arg1").text
    try:
        data.set_var(var,chr(arg1))
    except ValueError:
        raise BadString("Error INT2CHAR zly argument")


def str2int(ins,data):

    arg1 = get_string(ins.find("arg2"), data)
    arg2 = get_int(ins.find("arg3"), data)

    var = ins.find("arg1").text

    if arg2 >= len(arg1) :
        raise BadString("Error STR2INT int mimo hranicu")

    data.set_var(var,ord(arg1[arg2]))

def setchar(ins,data):
    arg1 = get_int(ins.find("arg2"), data)
    arg2 = get_string(ins.find("arg3"), data)

    var = ins.find("arg1").text
    string = data.get_var(var)
    if type(string) != str:
        raise BadOperand("Eror SETCHAR arg1 nie je string")

    if  arg1 >= len(string):
        raise BadString("Error SETCHAR int mimo hranicu")

    if arg2 == "":
        raise BadString("Error SETCHAR string je prazdny")

    string = string[:arg1] + arg2[0] + string[arg1+1:]
    data.set_var(var, string)


def concat(ins,data):
    arg1 = get_string(ins.find("arg2"), data)
    arg2 = get_string(ins.find("arg3"), data)

    var = ins.find("arg1").text
    data.set_var(var,arg1+arg2)


def getchar(ins,data):
    arg1 = get_string(ins.find("arg2"), data)
    arg2 = get_int(ins.find("arg3"), data)

    var = ins.find("arg1").text

    if arg2 >= len(arg1) or arg2 <0:
        raise BadString("Error GETCHAR int mimo hranicu stringu")

    data.set_var(var,str(arg1[arg2]))

def strlen(ins,data):
    arg1 = get_string(ins.find("arg2"), data)

    var = ins.find("arg1").text

    data.set_var(var,len(arg1))

def my_type(ins,data):
    arg1 = ins.find("arg2")

    var = ins.find("arg1").text

    if arg1.attrib["type"] == "var":

        arg1 = data.get_var(arg1.text)

        if type(arg1) is int:
            data.set_var(var,"int")
        elif type(arg1) is str:
            data.set_var(var, "string")
        elif type(arg1) is bool:
            data.set_var(var, "bool")
        elif type(arg1) is (Nil):
            data.set_var(var, "nil")
        elif type(arg1) is type(None):
            data.set_var(var, "")

    else:
        data.set_var(var,arg1.attrib["type"])

def dprint(ins,data):
    symb_arg = ins.find("arg1")
    symb_type = symb_arg.attrib["type"]

    if symb_type == "int":
        print(int(symb_arg.text),file=sys.stderr)
    elif symb_type == "bool":
        if symb_arg.text == "false":
            print('false',file=sys.stderr)
        else:
            print('true',file=sys.stderr)

    elif symb_type == "string":

        s = str(symb_arg.text)
        s = format_string(s)
        s = decode_escapes(s)
        print(s,file=sys.stderr)


    elif symb_type == "nil":
        print('',file=sys.stderr)

    elif symb_type == "var":
        if data.var_exists(str(symb_arg.text)):

            s = data.get_var(str(symb_arg.text))
            if s is None:
                raise MissingValue(f"Error DPRINT volane s {str(symb_arg.text)} ktora ma nedefinovanu hodnotu")
            elif type(s) is (Nil):
                s = ""
            elif type(s) is bool:
                if s:
                    s = "true"
                else:
                    s = "false"
            s = str(s)
            s = format_string(s)
            s = decode_escapes(s)
            print(s,file=sys.stderr)

def my_break(data):
    print(data.program_counter, file=sys.stderr)
    print(data.global_frame, file=sys.stderr)
    print(data.local_frame_stack, file=sys.stderr)
    print(data.tmp_frame, file=sys.stderr)


def jumpif(ins,data,mode):
    label = ins.find("arg1").text

    if label not in data.labels:
        raise SemanticError(f"Error pri JUMPIF nedefinovane navestie {label}")

    try:
        arg1 = get_bool(ins.find("arg2"), data)
        arg2 = get_bool(ins.find("arg3"), data)

        if mode == "EQ":
            if arg1 == arg2:
                data.program_counter = data.labels[label]
        elif mode == "NEQ":
            if arg1 != arg2:
                data.program_counter = data.labels[label]

        return

    except BadOperand:
        pass

    try:
        arg1 = get_int(ins.find("arg2"), data)
        arg2 = get_int(ins.find("arg3"), data)

        if mode == "EQ":
            if arg1 == arg2:
                data.program_counter = data.labels[label]
        elif mode == "NEQ":
            if arg1 != arg2:
                data.program_counter = data.labels[label]

        return

    except BadOperand:
        pass

    try:
        arg1 = get_string(ins.find("arg2"), data)
        arg2 = get_string(ins.find("arg3"), data)

        if mode == "EQ":
            if arg1 == arg2:
                data.program_counter = data.labels[label]
        elif mode == "NEQ":
            if arg1 != arg2:
                data.program_counter = data.labels[label]

        return

    except BadOperand:
        pass

    #osetrnie pre nil
    arg1 = ins.find("arg2")
    arg2 = ins.find("arg3")

    if arg1.attrib["type"] == "var":
        if type(data.get_var(arg1.text)) == (Nil):
            data.program_counter = data.labels[label]
            return

    if arg2.attrib["type"] == "var":
        if type(data.get_var(arg2.text)) == (Nil):
            data.program_counter = data.labels[label]
            return


    if ins.find("arg2").attrib["type"] == "nil" or  ins.find("arg3").attrib["type"] == "nil" :
        data.program_counter = data.labels[label]
        return

    raise BadOperand("Error pri porovnavani nezhodne typy")


def jump(ins,data):
    label = ins.find("arg1").text

    if label in data.labels:
        data.program_counter = data.labels[label]
    else:
        raise SemanticError(f"Error pri JUMP nedefinovane navestie {label}")


def my_exit(ins,data):
    arg1 = get_int(ins.find("arg1"), data)

    if arg1 < 0 or arg1 > 49:
        raise WrongNumber("Error EXIT volany s nespravnym cislom")

    exit(arg1)


def read(input_file,ins,data):
    var = ins.find("arg1").text

    typ = ins.find("arg2").text

    s = input_file.readline()

    if s == "": #prazdny string nic nenacital
        n = Nil
        data.set_var(var,n)


    else:
        if s[-1] == "\n":
            s = s[:-1]  # odstranenie \n

        if typ == "string":
            data.set_var(var,s)
        elif typ == "int":
            try:
                i = int(s)
                data.set_var(var, i)
            except ValueError:
                n = Nil
                data.set_var(var, n)

        elif typ == "bool":
            if s.lower() == "true":
                data.set_var(var, True)
            else:
                data.set_var(var, False)





# vetvenie programu podľa zadanej inštrukcie
def program(ins,data,input_file):
    opcode = ins.attrib["opcode"]

    if opcode   == "CREATEFRAME":
        createframe(data)
    elif opcode == "PUSHFRAME":
        pushframe(data)
    elif opcode == "POPFRAME":
        popframe(data)
    elif opcode == "DEFVAR":
        defvar(ins,data)
    elif opcode == "MOVE":
        move(ins,data)
    elif opcode == "CALL":
        call(ins,data)
    elif opcode == "RETURN":
        my_retrun(data)
    elif opcode == "WRITE":
        write(ins,data)
    elif opcode == "PUSHS":
        pushs(ins,data)
    elif opcode == "POPS":
        pops(ins,data)
    elif opcode == "ADD":
        add(ins,data)
    elif opcode == "SUB":
        sub(ins,data)
    elif opcode == "MUL":
        mul(ins,data)
    elif opcode == "IDIV":
        idiv(ins,data)
    elif opcode == "AND":
        my_and(ins,data)
    elif opcode == "OR":
        my_or(ins,data)
    elif opcode == "NOT":
        my_not(ins,data)
    elif opcode == "LT":
        my_compare(ins,data,"LT")
    elif opcode == "GT":
        my_compare(ins,data,"GT")
    elif opcode == "EQ":
        my_compare(ins,data,"EQ")
    elif opcode == "INT2CHAR":
        int2char(ins, data)
    elif opcode == "STRI2INT":
        str2int(ins, data)
    elif opcode == "SETCHAR":
        setchar(ins, data)
    elif opcode == "CONCAT":
        concat(ins, data)
    elif opcode == "GETCHAR":
        getchar(ins, data)
    elif opcode == "STRLEN":
        strlen(ins, data)
    elif opcode == "TYPE":
        my_type(ins, data)
    elif opcode == "DPRINT":
        dprint(ins, data)
    elif opcode == "BREAK":
        my_break( data)
    elif opcode == "JUMPIFEQ":
        jumpif(ins,data,"EQ")
    elif opcode == "JUMPIFNEQ":
        jumpif(ins,data,"NEQ")
    elif opcode == "JUMP":
        jump(ins,data)
    elif opcode == "READ":
        read(input_file,ins,data)
    elif opcode == "EXIT":
        my_exit(ins,data)




    #print(opcode)

    return True

# Hlavá funkcia programu
def main_func():
    # spracovanie argumentov programu
    parser = argparse.ArgumentParser(description='Interpreter pre IPPcode21.')
    parser.add_argument('--source', type=str,
                        help='Source file where code is stored')
    parser.add_argument('--input', type=str,
                        help='Input file for interpreter')

    args = parser.parse_args()


    if not args.input and not args.source:
        raise ArgMissing

    input_file = sys.stdin
    source_file = sys.stdin

    if args.input:
        input_file = open(args.input)

    if args.source:
        source_file = open(args.source)

    # parsonvanie xml súboru
    tree = ET.parse(source_file)

    root = tree.getroot()

    # ošetrienie validity xml
    data = Data()
    if not valid_program(root,data):
        raise BadXML


    data.labels = get_labels(root)

    instructions_ordered = list(map(int, list(data.ins_dict)))
    instructions_ordered.sort()

    if len(instructions_ordered) == 0:
        return 0

    # prechádzanie inštrukciami a ich spracovanie
    while data.program_counter <= int(instructions_ordered[-1]):
        curr_ins = root.find('./instruction[@order=\'{}\']'.format(data.program_counter))

        if curr_ins is not None:
            program(curr_ins, data,input_file)
        data.program_counter += 1





# ZACIATOK PROGRAMU ************************************

try:
    main_func()
except ArgMissing:
    print('Chyba pri argumentoch programu - nenaslo sa --input a ani --source', file=sys.stderr)
    exit(10)

except OSError:
    exit(11)

except ET.ParseError:
    exit(31)

except BadXML:
    print("Error pri XML strukture", file=sys.stderr)
    exit(32)

except SemanticError as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(52)

except BadOperand as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(53)

except VarDoesntExists as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(54)

except FrameDoesntExists as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(55)

except MissingValue as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(56)

except WrongNumber as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(57)

except BadString as e:
    print(f"{str(e)}", file=sys.stderr)
    exit(58)


