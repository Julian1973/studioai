#!/usr/bin/env python3
"""Throwaway validation renderer — renders one test scenario from the filed character sheets via Nano.
Usage: python3 wf_render.py <solo|pose|face|pair>  -> media/WF_zenny_<key>.png"""
import sys, cb_gen
Z = "media/CB_Zenny_turn4.png"; F = "media/CB_Fuzzby_turn4.png"
COM = (" Premium 3D-CGI Pixar feature quality, one clean 16:9 film still. Render ONE coherent scene only — "
       "do NOT reproduce any model-sheet panels, multiple views, turnaround layout, labels, scale or text.")
S = {
 "solo": ("REFERENCE: [Image 1] = Zenny's turnaround. Copy her EXACT design: round glasses, LONG eyelashes, "
          "rosy blush cheeks, yellow-and-black fuzzy stripes, brown stubby arms (no fingers), BOTH translucent "
          "wings. TASK: ONE Zenny hovering in a sunny rainforest clearing, full body." + COM, [Z]),
 "pose": ("REFERENCE: [Image 1] = Zenny's turnaround. Copy her exactly (glasses, long eyelashes, rosy blush "
          "cheeks, both wings, brown stubby arms with NO fingers). TASK: ONE Zenny standing on a big leaf, "
          "waving one short brown stubby arm (rounded nub end, NO fingers, NOT yellow), happy smile, full "
          "body, rainforest." + COM, [Z]),
 "face": ("REFERENCE: [Image 1] = Zenny's turnaround. Copy her exactly. TASK: a close-up of ONE Zenny's face "
          "and shoulders, clearly showing her long eyelashes, rosy blush cheeks and round glasses, soft "
          "rainforest bokeh behind." + COM, [Z]),
 "pair": ("REFERENCES: [Image 1] = Fuzzby's sheet (the BIGGER male bee — bulbous tan nose, glasses); "
          "[Image 2] = Zenny's turnaround (the SMALLER female bee — long eyelashes, rosy blush cheeks, glasses). "
          "TASK: BOTH Fuzzby and Zenny together, hovering side by side in a sunny rainforest clearing, full "
          "body. Fuzzby is slightly BIGGER than Zenny (he is 36 cm, she is 30 cm — a clear but gentle height "
          "difference, NOT identical, NOT a huge gap). Keep them DISTINCT: Fuzzby has the bulbous tan nose and "
          "no eyelashes; Zenny has long eyelashes and rosy blush cheeks. Both have brown stubby arms (no "
          "fingers) and both wings." + COM, [F, Z]),
}
k = sys.argv[1]; prompt, refs = S[k]
out = cb_gen.generate_image(prompt, refs=refs, out=f"WF_zenny_{k}.png", image_size="2K")
print("rendered", out)
