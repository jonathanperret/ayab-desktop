"""
Creates .qm files from master translation file.

Usage:

Run this script with a tab-delimited datafile in Unix format named
ayab-translation-master.tsv located in the same directory.

The script will generate .ts files for each language column found in the master
file. It then uses Qt's `lrelease` tool to create binary .qm files from the
generated .ts files. Finally, all temporary .ts files are removed.
"""

import os
import csv
import glob
from xml.sax.saxutils import escape

# Change the current directory to the script's directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Input file path
master = "ayab-translation-master.tsv"

# Read the entire master file into memory
with open(master, "r", encoding="utf-8") as file:
    reader = csv.reader(file, delimiter="\t")
    data = list(reader)

# Extract headers and data
headers = data[0]
rows = data[1:]

# Extract context column (first column)
context = [row[0] for row in rows]

# Extract source column (second column)
source = [row[1] for row in rows]

# Process each language column starting from the second column
for column in range(1, len(headers)):
    lang = headers[column]
    translations = [row[column] for row in rows]

    ts_filename = f"ayab_trans.{lang}.ts"
    with open(ts_filename, "w", encoding="utf-8") as ts_file:
        ts_file.write('<?xml version="1.0" encoding="utf-8"?>\n')
        ts_file.write("<!DOCTYPE TS>\n")
        ts_file.write(f'<TS version="2.1" language="{lang}">\n')

        last_context = None
        for idx in range(len(context)):
            curr_context = context[idx]
            if last_context is not None and last_context != curr_context:
                ts_file.write("</context>\n")

            if last_context != curr_context:
                ts_file.write(f"<context>\n<name>{escape(curr_context)}</name>\n")

            ts_file.write("<message>\n")
            ts_file.write(f"<source>{escape(source[idx])}</source>\n")
            trans = translations[idx]

            if trans:
                ts_file.write(f"<translation>{escape(trans)}</translation>\n")
            else:
                ts_file.write('<translation type="unfinished"/>\n')

            ts_file.write("</message>\n")
            last_context = curr_context

        if last_context is not None:
            ts_file.write("</context>\n")

        ts_file.write("</TS>\n")

# Run `pyside6-lrelease` to create binary `.qm` files
os.system("pyside6-lrelease *.ts")

# Remove all `.ts` files from the current directory
for f in glob.glob("*.ts"):
    os.remove(f)
