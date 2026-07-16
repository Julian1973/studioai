#!/usr/bin/env python3
"""Print the WHOLE character-master library (cb_prompts.masters_index) as JSON — read-only, informational,
for the studio to display + audit (masters_index's own stated intent). Never feeds a render prompt.
Usage: python3 masters_preview.py   (run from engine/)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE); sys.path.insert(0, HERE)
import cb_prompts as P

def main():
    try:
        print(json.dumps({"masters": P.masters_index()}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))

main()
