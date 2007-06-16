"""Tokenization help for Python-like HomEvenT programs."""

__author__ = 'Matthias Urlichs <matthias@urlichs.de>'
__credits__ = \
    'GvR, ESR, Tim Peters, Thomas Wouters, Fred Drake, Skip Montanaro, Ka-Ping Yee'

import string, re
from token import *
import tokenize as t

COMMENT = t.COMMENT
NL = t.NL
group = t.group
any = t.any
maybe = t.maybe
Whitespace = t.Whitespace
Comment = t.Comment
Ignore = t.Ignore
TokenError = t.TokenError
StopTokenizing = t.StopTokenizing
Intnumber = t.Intnumber
Floatnumber = t.Floatnumber
ContStr = t.ContStr
PseudoExtras = t.PseudoExtras
single3prog = t.single3prog
double3prog = t.double3prog
endprogs = t.endprogs
triple_quoted = t.triple_quoted
single_quoted = t.single_quoted

import token
__all__ = [x for x in dir(token) if x[0] != '_'] + ["COMMENT","NL",
           "generate_tokens"]
del x
del token


Name = r'\w+'
Number = group(Floatnumber, Intnumber)

# Because of leftmost-then-longest match semantics, be sure to put the
# longest operators first (e.g., if = came before ==, == would get
# recognized as two instances of =).
#Operator = group(r"\*\*=?", r">>=?", r"<<=?", r"<>", r"!=",
#                 r"//=?", r"[+\-*/%&|^=<>]=?", r"~")
Operator =  r"[+\-]"

Var = group(r"\*"+maybe(Name), r"\$"+Name)

Funny = group(Var, Operator, t.Bracket, t.Special)

PlainToken = group(Number, Funny, t.String, Name)
Token = Ignore + PlainToken

# First (or only) line of ' or " string.
PseudoToken = Whitespace + group(PseudoExtras, Number, Funny, ContStr, Name)

def _comp(exp):
	return re.compile(exp, re.UNICODE)
tokenprog, pseudoprog = map(
    _comp, (Token, PseudoToken))

tabsize = 8

def generate_tokens(readline):
    """see tokenize.generate_tokens."""

    lnum = parenlev = continued = 0
    namechars, numchars = string.ascii_letters + '_', '0123456789'
    contstr, needcont = '', 0
    contline = None
    indents = [0]

    while 1:                                   # loop over lines in stream
        try:
            line = readline()
        except StopIteration:
            line = ''
        lnum = lnum + 1
        pos, max = 0, len(line)

        if contstr:                            # continued string
            if not line:
                raise TokenError, ("EOF in multi-line string", strstart)
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                yield (STRING, contstr + line[:end],
                           strstart, (lnum, end), contline + line)
                contstr, needcont = '', 0
                contline = None
            elif needcont and line[-2:] != '\\\n' and line[-3:] != '\\\r\n':
                yield (ERRORTOKEN, contstr + line,
                           strstart, (lnum, len(line)), contline)
                contstr = ''
                contline = None
                continue
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        elif parenlev == 0 and not continued:  # new statement
            if not line: break
            column = 0
            while pos < max:                   # measure leading whitespace
                if line[pos] == ' ': column = column + 1
                elif line[pos] == '\t': column = (column/tabsize + 1)*tabsize
                elif line[pos] == '\f': column = 0
                else: break
                pos = pos + 1
            if pos == max: break

            if line[pos] in '#\r\n':           # skip comments or blank lines
                yield ((NL, COMMENT)[line[pos] == '#'], line[pos:],
                           (lnum, pos), (lnum, len(line)), line)
                continue

            if column > indents[-1]:           # count indents or dedents
                indents.append(column)
                yield (INDENT, line[:pos], (lnum, 0), (lnum, pos), line)
            while column < indents[-1]:
                if column not in indents:
                    raise IndentationError(
                        "unindent does not match any outer indentation level",
                        ("<tokenize>", lnum, pos, line))
                indents = indents[:-1]
                yield (DEDENT, '', (lnum, pos), (lnum, pos), line)

        else:                                  # continued statement
            if not line:
                raise TokenError, ("EOF in multi-line statement", (lnum, 0))
            continued = 0

        while pos < max:
            pseudomatch = pseudoprog.match(line, pos)
            if pseudomatch:                                # scan for tokens
                start, end = pseudomatch.span(1)
                spos, epos, pos = (lnum, start), (lnum, end), end
                token, initial = line[start:end], line[start]

                if initial in numchars or \
                   (initial == '.' and token != '.'):      # ordinary number
                    yield (NUMBER, token, spos, epos, line)
                elif initial in '\r\n':
                    yield (parenlev > 0 and NL or NEWLINE,
                               token, spos, epos, line)
                elif initial == '#':
                    yield (COMMENT, token, spos, epos, line)
                elif token in triple_quoted:
                    endprog = endprogs[token]
                    endmatch = endprog.match(line, pos)
                    if endmatch:                           # all on one line
                        pos = endmatch.end(0)
                        token = line[start:pos]
                        yield (STRING, token, spos, (lnum, pos), line)
                    else:
                        strstart = (lnum, start)           # multiple lines
                        contstr = line[start:]
                        contline = line
                        break
                elif initial in single_quoted or \
                    token[:2] in single_quoted or \
                    token[:3] in single_quoted:
                    if token[-1] == '\n':                  # continued string
                        strstart = (lnum, start)
                        endprog = (endprogs[initial] or endprogs[token[1]] or
                                   endprogs[token[2]])
                        contstr, needcont = line[start:], 1
                        contline = line
                        break
                    else:                                  # ordinary string
                        yield (STRING, token, spos, epos, line)
                elif initial in namechars:                 # ordinary name
                    yield (NAME, token, spos, epos, line)
                elif initial == '\\':                      # continued stmt
                    continued = 1
                else:
                    if initial in '([{': parenlev = parenlev + 1
                    elif initial in ')]}': parenlev = parenlev - 1
                    yield (OP, token, spos, epos, line)
            else:
                yield (ERRORTOKEN, line[pos],
                           (lnum, pos), (lnum, pos+1), line)
                pos = pos + 1

    for indent in indents[1:]:                 # pop remaining indent levels
        yield (DEDENT, '', (lnum, 0), (lnum, 0), '')
    yield (ENDMARKER, '', (lnum, 0), (lnum, 0), '')

