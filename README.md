# pgpt2scatter
 Create a MTK scatter file from a pgpt partition dump. The PGPT partition can generally be found in the 0x8000 first bytes of the flash memory.

## Requirement

- Python 2.7 Required
- EMMC and not UFS

## Use

- Modify the 7th line of template.txt and replace it by your MTK model

Command line : 

```
python pgpt2scatter.py pgpt_dump.bin
```
