import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'engine'))
import cb_gen, cb_render as R
refs=[str(Path('engine/media/Ep3_S1_plate_candidate_c66c0c33.jpeg').resolve())]+[str(Path('cb-seed/assets/final_turnarounds')/('CB_'+n+'.jpeg')) for n in ['Keen','Zenny','Fuzzby']]+[str(Path('engine/media/asset-registry/Ep3_S1_woodland_catapult.jpeg').resolve())]
prompt='''Create one 16:9 cinematic opening keyframe, before release, for Crystal Bears Scene1 Shot1.
Primary outcome: clearly establish a correctly oriented catapult launching from Keen in the foreground toward the honeycomb at the distant back tree.
References: Image1 is the outdoor Buzzing Nook environment authority; preserve tree and stream geography and morning lighting. Image2 is @Keen identity only; Image3 is @Zenny identity only; Image4 is @Fuzzby identity only. Preserve exact identities and accessories from complete turnaround references, without duplicating their views. Image5 supplies the wooden catapult design and materials; replace its ball with a real blueberry.
Composition: wide three-quarter view beside and behind @Keen in foreground left, with face readable in concentrated profile, one eye closed and tongue out. Catapult next to him on near bank. Its base points diagonally away from Keen toward the distant tree at upper right. Tall upright stop frame is on the forward target-facing end. Pivot is low; long throwing arm is cocked BACK toward Keen, blueberry cup on rearward end nearest Keen, BEHIND the forward stop. On release it will swing forward/up toward the honeycomb. Keen stands behind the machine holding release rope. This image is before firing: blueberry remains in cup. Across several Keen body lengths of open middle ground, a separate portable golden honeycomb hangs from a low branch at back tree, with @Fuzzby sleeping on top. @Zenny sits cross-legged on a leaf nearby at that same distant tree, slightly below and beside target, eyes closed, face clean. Exactly these three characters. Make distance and unobstructed launch corridor readable, with believable scale and deep enough focus to identify bees. Honeycomb must be portable enough for Keen's later snatch, distinct from background houses.
Visual direction: expressive feature-animation 3D CGI matching references, plush surfaces, rounded forms, warm harmonious palette and soft volumetric morning light.
Physical integration: consistent perspective, contact shadows, rope tension and grounded wooden supports; believable throwing mechanism aimed away from operator. Keep background target readable.
Preserve: reference identities, environment, three characters, foreground-to-background distance and pre-release state.
Exclude: additional cuffs or limbs, duplicate characters, backward catapult, handheld slingshot, giant wool ball, doors or windows on portable honeycomb, impact, juice, airborne berry, flight trails, arrows, text, watermark, multiple panels.'''
record={'episode':'Ep3','scene':'1','shot':'S1.SH1','status':'unapproved-comparison','model':cb_gen.SEEDREAM_MODEL_ID,'prompt':prompt,'references':refs}
Path('cb-output/image-trials/Ep3_S1_SH1_seedream_trial.json').write_text(json.dumps(record,indent=2))
R._require_confirmed_billing('byteplus')
out=cb_gen.generate_image(prompt,refs=refs,out='Ep3_S1_SH1_seedream_prompt_trial_v01.png',image_size='2K',production_route='cb_render')
record['output']=out
Path('cb-output/image-trials/Ep3_S1_SH1_seedream_trial.json').write_text(json.dumps(record,indent=2))
print(out)
