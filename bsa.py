"""Read-only TES5 v104/v105 BSA index and targeted extraction."""
from pathlib import Path
import struct,zlib

def lz4_block(data, expected):
    out=bytearray();p=0
    def length(initial):
        nonlocal p
        n=initial
        if n==15:
            while True:
                x=data[p];p+=1;n+=x
                if x!=255:break
        return n
    while p<len(data):
        token=data[p];p+=1;n=length(token>>4)
        out.extend(data[p:p+n]);p+=n
        if p==len(data):break
        offset=struct.unpack_from('<H',data,p)[0];p+=2
        if not offset or offset>len(out):raise ValueError('Invalid LZ4 offset')
        n=length(token&15)+4
        for _ in range(n):out.append(out[-offset])
    if len(out)!=expected:raise ValueError('LZ4 size mismatch')
    return bytes(out)

class BSA:
    def __init__(self,path):
        self.path=Path(path);self.files={}
        with self.path.open('rb') as f:
            h=struct.unpack('<4s8I',f.read(36))
            if h[0]!=b'BSA\x00' or h[1] not in (104,105):raise ValueError(h[:2])
            self.version=h[1];self.flags=h[3]
            f.seek(h[2]);folders=[]
            for _ in range(h[4]):
                r=f.read(24 if self.version==105 else 16)
                folders.append(struct.unpack_from('<I',r,8)[0])
            entries=[]
            for count in folders:
                name=f.read(f.read(1)[0]).rstrip(b'\x00').decode('cp1252')
                for _ in range(count):
                    _,size,offset=struct.unpack('<QII',f.read(16))
                    entries.append((name,size,offset))
            names=f.read(h[7]).split(b'\x00')
            assert len(entries)==h[5]
            for (folder,size,offset),name in zip(entries,names):
                key=(folder+'\\'+name.decode('cp1252')).replace('/','\\').lower()
                self.files[key]=(size,offset)
    def read(self,name):
        size,offset=self.files[name.replace('/','\\').lower()]
        compressed=bool(size&0x40000000)^bool(self.flags&4)
        with self.path.open('rb') as f:
            f.seek(offset);data=f.read(size&0x3fffffff)
        if self.flags&0x100:data=data[1+data[0]:]
        if compressed:
            expected=struct.unpack_from('<I',data)[0]
            data=lz4_block(data[4:],expected) if self.version==105 else zlib.decompress(data[4:])
            assert len(data)==expected
        return data
