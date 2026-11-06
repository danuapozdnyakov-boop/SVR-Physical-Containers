"""Lossless block-level Skyrim SE NIF editing. Original indices remain stable."""
import struct

class Nif:
    def __init__(self,data):
        p=data.index(b'\n')+1;self.line=data[:p]
        def take(n):
            nonlocal p
            x=data[p:p+n];p+=n;assert len(x)==n;return x
        def u():return struct.unpack('<I',take(4))[0]
        self.version=u();self.endian=take(1);self.user=u();n=u();self.bs=u()
        assert (self.version,self.user,self.bs)==(0x14020007,12,100)
        self.exports=[take(take(1)[0]) for _ in range(3)]
        types=[take(u()).decode() for _ in range(struct.unpack('<H',take(2))[0])]
        indices=struct.unpack('<'+'H'*n,take(2*n));sizes=[u() for _ in range(n)]
        ns=u();u();self.strings=[take(u()).decode('utf-8') for _ in range(ns)]
        self.groups=[u() for _ in range(u())]
        self.blocks=[(types[i],bytearray(take(size))) for i,size in zip(indices,sizes)]
        self.footer=data[p:]
    def add(self,kind,raw):
        i=len(self.blocks);self.blocks.append((kind,bytearray(raw)));return i
    def string(self,name):
        if name not in self.strings:self.strings.append(name)
        return self.strings.index(name)
    def encode(self):
        types=list(dict.fromkeys(t for t,_ in self.blocks));u=lambda x:struct.pack('<I',x)
        out=self.line+u(self.version)+self.endian+u(self.user)+u(len(self.blocks))+u(self.bs)
        out+=b''.join(bytes([len(s)])+s for s in self.exports)
        out+=struct.pack('<H',len(types))+b''.join(u(len(t))+t.encode() for t in types)
        out+=b''.join(struct.pack('<H',types.index(t)) for t,_ in self.blocks)
        out+=b''.join(u(len(b)) for _,b in self.blocks)
        encoded=[s.encode('utf-8') for s in self.strings]
        out+=u(len(encoded))+u(max(map(len,encoded),default=0))+b''.join(u(len(s))+s for s in encoded)
        out+=u(len(self.groups))+b''.join(u(g) for g in self.groups)
        out+=b''.join(b for _,b in self.blocks)+self.footer
        return out

def node_offsets(raw):
    n=struct.unpack_from('<I',raw,4)[0];return {'controller':8+4*n,'flags':12+4*n,'translation':16+4*n,'rotation':28+4*n,'scale':64+4*n,'collision':68+4*n,'children':72+4*n}

def children(raw):
    o=node_offsets(raw)['children'];n=struct.unpack_from('<I',raw,o)[0]
    return list(struct.unpack_from('<'+'i'*n,raw,o+4))

def set_children(raw,items):
    o=node_offsets(raw)['children'];n=struct.unpack_from('<I',raw,o)[0]
    raw[o:o+4+4*n]=struct.pack('<I',len(items))+b''.join(struct.pack('<i',i) for i in items)

def clean_node(raw,name,collision,items):
    # Keep the original transform, without extra data or animation controllers.
    o=node_offsets(raw);p=bytearray(struct.pack('<iIi',name,0,-1)+raw[o['flags']:o['collision']]+struct.pack('<iI',collision,len(items)))
    p+=b''.join(struct.pack('<i',i) for i in items)+struct.pack('<I',0)
    return p
