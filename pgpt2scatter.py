# Scatter Creator for MTK flash/dump
# Credits to Younes BENSITEL - SEA.


import collections
import struct
import sys
import uuid
import argparse

def parseArguments():
    # Create argument parser
    parser = argparse.ArgumentParser()

    # Positional mandatory arguments
    parser.add_argument("pgpt", help="PGPT partition to convert to scatter file, the 0x8000 first bytes of your raw memory", type=str)

    # Print version
    parser.add_argument("--version", action="version", version='%(prog)s - Version 1.0')

    # Parse arguments
    args = parser.parse_args()

    return args


GPT_HEADER_FORMAT = """
8s signature
4s revision
L header_size
L crc32
4x _
Q current_lba
Q backup_lba
Q first_usable_lba
Q last_usable_lba
16s disk_guid
Q part_entry_start_lba
L num_part_entries
L part_entry_size
L crc32_part_array
"""

# http://en.wikipedia.org/wiki/GUID_Partition_Table#Partition_entries_.28LBA_2.E2.80.9333.29
GPT_PARTITION_FORMAT = """
16s type
16s unique
Q first_lba
Q last_lba
Q flags
72s name
"""

def _make_fmt(name, format, extras=[]):
    type_and_name = [l.split(None, 1) for l in format.strip().splitlines()]
    fmt = ''.join(t for (t,n) in type_and_name)
    fmt = '<'+fmt
    tupletype = collections.namedtuple(name, [n for (t,n) in type_and_name if n!='_']+extras)
    return (fmt, tupletype)

class GPTError(Exception):
    pass

def read_header(fp, lba_size=512):
    # skip MBR
    fp.seek(1*lba_size)
    fmt, GPTHeader = _make_fmt('GPTHeader', GPT_HEADER_FORMAT)
    data = fp.read(struct.calcsize(fmt))
    header = GPTHeader._make(struct.unpack(fmt, data))
    if header.signature != 'EFI PART':
        raise GPTError('Bad signature: %r' % header.signature)
    if header.revision != '\x00\x00\x01\x00':
        raise GPTError('Bad revision: %r' % header.revision)
    if header.header_size < 92:
        raise GPTError('Bad header size: %r' % header.header_size)
    # TODO check crc32
    header = header._replace(
        disk_guid=str(uuid.UUID(bytes_le=header.disk_guid)),
        )
    return header

def read_partitions(fp, header, lba_size=512):
    fp.seek(header.part_entry_start_lba * lba_size)
    fmt, GPTPartition = _make_fmt('GPTPartition', GPT_PARTITION_FORMAT, extras=['index'])
    for idx in xrange(1, 1+header.num_part_entries):
        data = fp.read(header.part_entry_size)
        if len(data) < struct.calcsize(fmt):
            raise GPTError('Short partition entry')
        part = GPTPartition._make(struct.unpack(fmt, data) + (idx,))
        if part.type == 16*'\x00':
            continue
        part = part._replace(
            type=str(uuid.UUID(bytes_le=part.type)),
            unique=str(uuid.UUID(bytes_le=part.unique)),
            # do C-style string termination; otherwise you'll see a
            # long row of NILs for most names
            name=part.name.decode('utf-16').split('\0', 1)[0],
            )
        yield part




known_partitions = ["system","recovery","vbmeta_system","vbmeta_vendor","md1img","spmfw","scp1","scp2","sspm_1","sspm_2","lk","lk2","boot","logo","dtbo","tee1","tee2","super","vbmeta","cache","userdata"]
known_partitions2 = ["system.img","recovery.img","vbmeta_system.img","vbmeta_vendor.img","md1img.img","spmfw.img","scp.img","scp.img","sspm.img","sspm.img","lk.img","lk.img","boot.img","logo.bin","dtbo.img","tee.img","tee.img","super.img","vbmeta.img","cache.img","userdata.img"]
boundary_check_false = ["otp","flashinfo","sgpt"]
is_reserved_true = ["otp","flashinfo","sgpt"]
is_protected = ["persist","proinfo","nvcfg","protect1","protect2"]
binregion = ["nvram"]
is_invisible = ["gz1","gz2","boot_para","para","expdb","frp","nvdata","md_udc","metadata","seccfg","sec1","sec2"]
empty_boot_needed = ["lk","logo","tee1","tee2"]

if __name__ == '__main__':

	args = parseArguments()
	file = args.pgpt
	print("Opening file "+file)

	block_size = 512
	pgpt=open(file,"rb")
	# scatter_file = open(file+"_scatter.txt","w")
	scatter = open("template.txt","r").read()
	header = read_header(pgpt)

	#print(header)
	for part in read_partitions(pgpt, header):
		conf = str(part).split(",")
		start= int(conf[2].split("=")[1])*block_size
		end = int(conf[3].split("=")[1])*block_size+block_size
		index = int(conf[6].split("=")[1].split(")")[0])+1
		partition_size = end-start
		partition_name = conf[5].split("'")[1]

		partition = "\n\n"
		partition+= "- partition_index: SYS"+str(index)+"\n"
		partition+= "  partition_name: "+partition_name+"\n"
		partition+= "  file_name: "
		if partition_name in known_partitions:
			partition+=known_partitions2[known_partitions.index(partition_name)]+"\n"
			partition+= "  is_download: true\n"
		else:
			partition+="NONE"+"\n"
		if(partition_name not in known_partitions):
			if (partition_name not in is_protected and partition_name not in binregion and partition_name not in is_invisible and partition_name not in is_reserved_true):
				partition+= "  is_download: true\n"
			else:
				partition+= "  is_download: false\n"
		partition+= "  type: NORMAL_ROM\n"
		start_hex= str(hex(start))
		if("L" in start_hex):
			start_hex = start_hex[0:-1]
		partition+= "  linear_start_addr: "+start_hex+"\n"
		partition+= "  physical_start_addr: "+start_hex+"\n"
		partition_size_hex= str(hex(partition_size))
		if("L" in partition_size_hex):
			partition_size_hex = partition_size_hex[0:-1]
		partition+= "  partition_size: "+partition_size_hex+"\n"
		partition+= "  region: EMMC_USER\n"
		partition+= "  storage: HW_STORAGE_EMMC\n"
		partition+="  boundary_check: "
		if(partition_name in boundary_check_false):
			partition+="false"
		else:
			partition+="true"
		partition+="\n"
		partition+="  is_reserved: "
		if(partition_name in is_reserved_true):
			partition+="true"
		else:
			partition+="false"
		partition+="\n"
		partition+= "  operation_type: "
		if(partition_name in is_reserved_true):
			partition+= "RESERVED\n"
			partition+="  is_upgradable: false\n"
		elif(partition_name in is_invisible):
			partition+= "INVISIBLE\n"
			partition+="  is_upgradable: false\n"
		elif(partition_name in is_protected):
			partition+= "PROTECTED\n"
			partition+="  is_upgradable: false\n"

		elif(partition_name in binregion):
			partition+= "BINREGION\n"
			partition+="  is_upgradable: false\n"		
		else:
			partition+= "UPDAT"+"E\n"
			partition+="  is_upgradable: true\n"
		partition+="  empty_boot_needed: false\n"
		partition+="  reserve: 0x00"


		scatter+=partition
	scatter_file = open(file+"_scatter.txt","w")
	scatter_file.write(scatter)
	scatter_file.close()
	print("Saved as "+file+"_scatter.txt")
