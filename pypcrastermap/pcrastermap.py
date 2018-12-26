from ctypes import *
import struct


class PcrasterMap:

    def __init__(self):
        
        # main header fields
        self.signature = 0          # offset  0, 32 bytes
        self.version = 0            # offset 32, uint2
        self.gis_file_id = 0         # offset 34, uint4
        self.projection = 0         # offset 38, unit2
        self.attr_table_offset = 0  # offset 40, uint4
        self.map_type = 0            # offset 44, uint2
        self.byte_order = 0          # offset 46, uint4
     
    def open(self, path):
        self.f = open(path, "rb")
        self.read_main_header()
        self.read_attr_table()

    def read_main_header(self):
        header = self.f.read(50)
        print(header)

        (self.signature, self.version, self.gis_file_id, self.projection,
        self.attr_table_offset, self.map_type, self.byte_order) = struct.unpack("=32sHIHIHI", header)
    
    def read_attr_table(self):
        attrs = []
        next = self.attr_table_offset

        while next != 0:
            self.f.seek(next)
            block = self.f.read(10*10 + 4)  # attribute blocks contain 10 entries of 10 bytes;
                                            # final 4 bytes are the pointer to the next attribute block
            if len(block) != 104:
                break

            off = 0
            while off < 100:
                attr = {}
                (attr['id'], attr['offset'], attr['size']) = struct.unpack('=HII', block[off:off+10])
                if attr['id'] == 0xffff: # terminator
                    break
                if attr['id'] != 0:
                    attrs.append(attr)
                off += 10
            (next,) = struct.unpack('=I', block[100:104])

        self.attrs = attrs

    def get_attr_info(self, attr_id):
        for attr in self.attrs:
            if attr['id'] == attr_id:
                return attr
        return None

    def get_legend_entry_count(self):
        attr = self.get_attr_info(6)
        if attr is None:
            return 0
        return (attr['size'] / 64)

    def get_legend_entries(self):
        ret = []

        attr = self.get_attr_info(6)
        if attr is None:
            return ret
        
        cnt = attr['size'] / 64

        if attr['offset'] == 0 or cnt == 0:
            return ret
        
        self.f.seek(attr['offset'])
        block = self.f.read(attr['size'])
        
        offset = 0
        while offset < cnt*64:
            entry = {}
            (entry['id'], entry['name']) = struct.unpack("=I60s", block[offset:offset+64])
            entry['name'] = entry['name'].rstrip('\x00')
            ret.append(entry)
            offset += 64

        return ret    

        


m = PcrasterMap()
m.open(map_path)
print("Nr of legend entries: " + str(m.get_legend_entry_count()))
print(m.get_legend_entries())