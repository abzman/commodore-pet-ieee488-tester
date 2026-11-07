"""Build an option-ROM image ($9000-$AFFF) that unpacks IEEETEST into BASIC RAM and RUNs it.

Compressed stream format (decoded by the 6502 stub):
  c = $00            end
  c = $01-$7F        c literal bytes follow
  c = $80-$FF        match: length (c & $7F)+3, then 16-bit little-endian distance back
"""
import sys
from petbasic import load, make_prg, squeeze

ORG = 0x9000
ZP = dict(src=0x54, dst=0x56, ref=0x58, off=0x5A, cnt=0x5C)

def compress(data):
    out = bytearray(); lits = bytearray(); i = 0; n = len(data)
    index = {}
    def flush():
        nonlocal lits
        while lits:
            chunk = lits[:127]; out.append(len(chunk)); out.extend(chunk); lits = lits[127:]
    while i < n:
        best_len = 0; best_d = 0
        if i + 3 <= n:
            for j in reversed(index.get(bytes(data[i:i+3]), [])[-512:]):
                l = 0
                while i + l < n and l < 130 and data[j + l] == data[i + l]: l += 1
                if l > best_len: best_len, best_d = l, i - j
                if l == 130: break
        if best_len >= 3 and i + 1 + 3 <= n:
            nl = 0
            for j in reversed(index.get(bytes(data[i+1:i+4]), [])[-512:]):
                l = 0
                while i + 1 + l < n and l < 130 and data[j + l] == data[i + 1 + l]: l += 1
                nl = max(nl, l)
            if nl > best_len + 1: best_len = 0
        if best_len >= 3:
            flush(); out.append(0x80 | (best_len - 3)); out += bytes((best_d & 255, best_d >> 8))
            for k in range(i, i + best_len):
                index.setdefault(bytes(data[k:k+3]), []).append(k)
            i += best_len
        else:
            index.setdefault(bytes(data[i:i+3]), []).append(i)
            lits.append(data[i]); i += 1
    flush(); out.append(0)
    return bytes(out)

# --- tiny assembler: instructions as tuples, labels as strings ---
OPS = {('LDA', 'imm'): 0xA9, ('LDA', 'zp'): 0xA5, ('LDA', 'izy'): 0xB1, ('LDA', 'abx'): 0xBD,
       ('STA', 'zp'): 0x85, ('STA', 'izy'): 0x91, ('STA', 'abx'): 0x9D,
       ('LDX', 'imm'): 0xA2, ('LDY', 'imm'): 0xA0, ('DEX', 'imp'): 0xCA,
       ('JSR', 'abs'): 0x20, ('RTS', 'imp'): 0x60, ('JMP', 'abs'): 0x4C,
       ('CMP', 'imm'): 0xC9, ('AND', 'imm'): 0x29, ('ADC', 'imm'): 0x69, ('SBC', 'zp'): 0xE5,
       ('CLC', 'imp'): 0x18, ('SEC', 'imp'): 0x38, ('INC', 'zp'): 0xE6, ('DEC', 'zp'): 0xC6,
       ('BEQ', 'rel'): 0xF0, ('BNE', 'rel'): 0xD0, ('BMI', 'rel'): 0x30, ('BPL', 'rel'): 0x10}
SIZE = {'imm': 2, 'zp': 2, 'izy': 2, 'abx': 3, 'abs': 3, 'imp': 1, 'rel': 2}

def program(data_label='data'):
    s, d, r, o, c = (ZP[k] for k in ('src', 'dst', 'ref', 'off', 'cnt'))
    return [
        ('LDA', 'imm', ('lo', data_label)), ('STA', 'zp', s),
        ('LDA', 'imm', ('hi', data_label)), ('STA', 'zp', s + 1),
        ('LDA', 'imm', 0x01), ('STA', 'zp', d), ('LDA', 'imm', 0x04), ('STA', 'zp', d + 1),
        'loop',
        ('LDY', 'imm', 0), ('LDA', 'izy', s), ('JSR', 'abs', 'incsrc'),
        ('CMP', 'imm', 0), ('BEQ', 'rel', 'done'), ('BMI', 'rel', 'match'),
        ('STA', 'zp', c),
        'lit',
        ('LDA', 'izy', s), ('STA', 'izy', d), ('JSR', 'abs', 'incsrc'), ('JSR', 'abs', 'incdst'),
        ('DEC', 'zp', c), ('BNE', 'rel', 'lit'), ('JMP', 'abs', 'loop'),
        'match',
        ('AND', 'imm', 0x7F), ('CLC', 'imp'), ('ADC', 'imm', 3), ('STA', 'zp', c),
        ('LDA', 'izy', s), ('STA', 'zp', o), ('JSR', 'abs', 'incsrc'),
        ('LDA', 'izy', s), ('STA', 'zp', o + 1), ('JSR', 'abs', 'incsrc'),
        ('SEC', 'imp'), ('LDA', 'zp', d), ('SBC', 'zp', o), ('STA', 'zp', r),
        ('LDA', 'zp', d + 1), ('SBC', 'zp', o + 1), ('STA', 'zp', r + 1),
        'mcp',
        ('LDA', 'izy', r), ('STA', 'izy', d),
        ('INC', 'zp', r), ('BNE', 'rel', 'mcp2'), ('INC', 'zp', r + 1),
        'mcp2',
        ('JSR', 'abs', 'incdst'), ('DEC', 'zp', c), ('BNE', 'rel', 'mcp'), ('JMP', 'abs', 'loop'),
        'done',   # BASIC 2(upgrade)/4: TXTTAB $28, VARTAB $2A, ARYTAB $2C, STREND $2E
        ('LDA', 'imm', 0x01), ('STA', 'zp', 0x28), ('LDA', 'imm', 0x04), ('STA', 'zp', 0x29),
        ('LDA', 'zp', d), ('STA', 'zp', 0x2A), ('STA', 'zp', 0x2C), ('STA', 'zp', 0x2E),
        ('LDA', 'zp', d + 1), ('STA', 'zp', 0x2B), ('STA', 'zp', 0x2D), ('STA', 'zp', 0x2F),
        ('LDX', 'imm', 3),
        'kb',
        ('LDA', 'abx', 'runtxt'), ('STA', 'abx', 0x026F), ('DEX', 'imp'), ('BPL', 'rel', 'kb'),
        ('LDA', 'imm', 4), ('STA', 'zp', 0x9E), ('RTS', 'imp'),
        'incsrc', ('INC', 'zp', s), ('BNE', 'rel', 'is1'), ('INC', 'zp', s + 1), 'is1', ('RTS', 'imp'),
        'incdst', ('INC', 'zp', d), ('BNE', 'rel', 'id1'), ('INC', 'zp', d + 1), 'id1', ('RTS', 'imp'),
        'runtxt', b'RUN\r',
        'data',
    ]

def assemble(prog, org):
    labels = {}; pc = org
    for it in prog:
        if isinstance(it, str): labels[it] = pc
        elif isinstance(it, bytes): pc += len(it)
        else: pc += SIZE[it[1]]
    out = bytearray(); pc = org
    def val(x):
        if isinstance(x, tuple): v = labels[x[1]]; return v & 255 if x[0] == 'lo' else v >> 8
        return labels[x] if isinstance(x, str) else x
    for it in prog:
        if isinstance(it, str): continue
        if isinstance(it, bytes): out += it; pc += len(it); continue
        op, mode = it[0], it[1]; out.append(OPS[(op, mode)])
        if mode == 'rel':
            dlt = labels[it[2]] - (pc + 2); assert -128 <= dlt <= 127; out.append(dlt & 255)
        elif SIZE[mode] == 2: out.append(val(it[2]) & 255)
        elif SIZE[mode] == 3: v = val(it[2]); out += bytes((v & 255, v >> 8))
        pc += SIZE[mode]
    return bytes(out)

if __name__ == '__main__':
    L = load(open('ieeetest.bas').read())
    prg = make_prg({n: squeeze(t) for n, t in L.items()})
    body = prg[2:]                     # strip load address; lands at $0401
    stub = assemble(program(), ORG)
    comp = compress(body)
    img = stub + comp
    print(f'program {len(body)} bytes, compressed {len(comp)}, stub {len(stub)}, image {len(img)} / 8192')
    assert len(img) <= 8192
    img = img + b'\xff' * (8192 - len(img))
    open('ieeetest_9000-AFFF_8k.bin', 'wb').write(img)
    open('ieeetest_UD12_9000.bin', 'wb').write(img[:4096])
    open('ieeetest_UD11_A000.bin', 'wb').write(img[4096:])
