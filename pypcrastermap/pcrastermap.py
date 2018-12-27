import struct
import sys


class PcrasterMap:

    def __init__(self):
        
        # main header fields
        self.signature = 0           # offset  0, 32 characters
        self.version = 0             # offset 32, uint2
        self.gis_file_id = 0         # offset 34, uint4
        self.projection = 0          # offset 38, unit2
        self.attr_table_offset = 0   # offset 40, uint4
        self.map_type = 0            # offset 44, uint2
        self.byte_order = 0          # offset 46, uint4

        self.attrs = {}
     
    def open(self, path):
        self.f = open(path, "r+b")
        self.read_main_header()
        self.read_attr_table()

    def read_main_header(self):
        self.f.seek(0)
        header = self.f.read(50)
        (self.signature, self.version, self.gis_file_id, self.projection,
        self.attr_table_offset, self.map_type, self.byte_order) = struct.unpack("=32sHIHIHI", header)
    
    def delete_attr(self, attr_id):
        next = self.attr_table_offset
        while next != 0:
            self.f.seek(next)
            block = self.f.read(10*10 + 4)  # attribute blocks contain 10 entries of 10 bytes;
                                            # final 4 bytes are the pointer to the next attribute block
            if len(block) != 104:
                break
            off = 0
            while off < 100:
                (id,offset,size) = struct.unpack('=HII', block[off:off+10])
                if id == 0xffff: # terminator
                    break
                if id == attr_id:
                    id = 0
                    new_block = struct.pack('=HII', id, offset, size)
                    self.f.seek(next+off)
                    self.f.write(new_block)
                    self.read_attr_table()
                    return True # delete successful
                off += 10
            (next,) = struct.unpack('=I', block[100:104])
        return False # not found
    
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
        return self.attrs

    def dump_attr_table(self):
        attrs = []
        next = self.attr_table_offset
        print("Main header attr table offset: " + str(next))
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
                print(attr)
                if attr['id'] == 0xffff: # terminator
                    break
                if attr['id'] != 0:
                    attrs.append(attr)
                off += 10
            (next,) = struct.unpack('=I', block[100:104])
            print("Next block: " + str(next))
        self.attrs = attrs

    def create_attr_table_block(self):
        block = b"\0" * 104
        self.f.seek(0, 2) # seek to end
        new_block_offset = self.f.tell()
        self.f.write(block)
        
        self.read_main_header()

        # find the file offset of the attr block pointer to update
        next = self.attr_table_offset
        next_ptr_offset = 40  # in main header
        while next != 0:
            self.f.seek(next)
            block = self.f.read(10*10 + 4)  # attribute blocks contain 10 entries of 10 bytes;
                                            # final 4 bytes are the pointer to the next attribute block
            if len(block) != 104:
                return None
            next_ptr_offset = next + 100
            (next,) = struct.unpack('=I', block[100:104])

        buffer = struct.pack("=I", new_block_offset)
        self.f.seek(next_ptr_offset)
        self.f.write(buffer)
        if next_ptr_offset == 40:
            self.attr_table_offset = offset

        return new_block_offset
    

    def write_attr_table(self, attrs = None):

        if attrs is None:
            attrs = self.attrs
        
        self.read_main_header()

        # if we have no attributes to write and there is presently no attribute table, we're done
        if self.attr_table_offset == 0 and len(attrs) == 0:
            return True
        
        # create an array with the attributes to write, including terminator entry
        attrs_to_write = []
        for a in attrs:
            attrs_to_write.append(a)
        attrs_to_write.append({'id': 0xffff, 'offset': 0, 'size': 0}) # add terminator

        # write them one by one
        block_offset = self.attr_table_offset
        if block_offset == 0:
            block_offset = self.create_attr_table_block()
        self.f.seek(block_offset)
        entry_nr = 0
        cnt = 0
        for attr in attrs_to_write:
            chunk = struct.pack('=HII', attr['id'], attr['offset'], attr['size'])
            self.f.write(chunk)

            entry_nr += 1
            cnt += 1
            if entry_nr == 10:
                if cnt < len(attrs_to_write):
                    block_offset = self.create_attr_table_block()
                    self.f.seek(block_offset)
                    entry_nr = 0



    def get_attr_info(self, attr_id):
        for attr in self.attrs:
            if attr['id'] == attr_id:
                return attr
        return None

    def set_attr_info(self, attr_id, offset, size):
        self.read_main_header()
        self.read_attr_table()
        for attr in self.attrs:
            if attr['id'] == attr_id:
                attr['offset'] = offset
                attr['size'] = size
                self.write_attr_table()
                return True
        self.attrs.append({'id': attr_id, 'offset': offset, 'size': size})
        self.write_attr_table()
        return True

    def get_legend_entry_count(self):
        attr = self.get_attr_info(6)
        if attr is None or attr['size'] % 64 != 0:
            return 0
        return int(attr['size'] / 64)

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

        if len(block) % 64 != 0:
            # invalid legend length
            return ret
        
        offset = 0
        while offset < cnt*64:
            (id, name) = struct.unpack("=I60s", block[offset:offset+64])
            if sys.hexversion >= 0x3000000:
                name = name.decode('ascii') # python 3 will yield bytes
            else:
                name = name.encode('ascii') # python 2 will yield unicode string
            name = name.rstrip('\x00')
            ret.append({'id':id,'name':name})
            offset += 64

        return ret

    def set_legend_entries(self, legend_entries):

        # create legend block
        block = b''
        for entry in legend_entries:
            id = entry['id']
            name = entry['name']
            if sys.hexversion >= 0x3000000:
                name = name.encode('ascii') # python 3 wants bytes, not a string
            block += struct.pack("=I60s", id, name)

        attr = self.get_attr_info(6)
        if attr is not None and len(block) <= attr['size']:
            data_len = len(block)
            block += b"\0" * (attr['size'] - len(block))  # pad out rest with zeros
            self.f.seek(attr['offset'])
            self.f.write(block)
            self.set_attr_info(attr_id=6, offset=attr['offset'], size=data_len)
        else:
            self.f.seek(0, 2) # seek to end
            offset = self.f.tell()
            self.f.write(block)
            self.set_attr_info(attr_id=6, offset=offset, size=len(block))

        return True




if __name__ == "__main__":
    
    from shutil import copyfile
    copyfile("./test.map", "./t.map")
    
    m = PcrasterMap()
    m.open("./t.map")
    m.dump_attr_table()

    attrs = m.read_attr_table();
    for i in range(1,99):
        attrs.append({'id': i, 'offset': i, 'size': i})
    m.write_attr_table(attrs)
    m = None

    m = PcrasterMap()
    m.open("./t.map")
    #m.delete_attr(6)
    m.dump_attr_table()


    print("Nr of legend entries: " + str(m.get_legend_entry_count()))
    legend = m.get_legend_entries()
    print(legend)
    new_legend = [ legend[4],legend[4],legend[4],legend[4],legend[4],legend[4],legend[4],legend[4],legend[4] ]
    m.set_legend_entries(new_legend)
    legend = m.get_legend_entries()
    print(legend)
