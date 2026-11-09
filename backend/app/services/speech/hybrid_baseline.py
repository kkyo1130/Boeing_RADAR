"""Frozen comparison rule baseline. Prefix data provenance: HYBRID_DATA_NOTICE.txt."""
import json
from pathlib import Path

NUM=set('zero oh one two three four five six seven eight nine niner ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand'.split())
NATO=set('alfa alpha bravo charlie delta echo foxtrot golf hotel india juliett juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey whisky xray yankee zulu'.split())
PREFIXES = [tuple(p) for p in json.loads(Path(__file__).with_name("hybrid_prefixes.json").read_text())]

def rules(words):
 w=[x.lower().strip('.,;:') for x in words];tags=['O']*len(w)
 def put(a,b,label):
  if a<b and all(x=='O' for x in tags[a:b]):
   for j in range(a,b):tags[j]=('B-' if j==a else 'I-')+label
 def nums(i):
  j=i
  while j<len(w) and (w[j] in NUM or w[j].isdigit()):j+=1
  return j
 for i in range(len(w)):
  for p in PREFIXES:
   if tuple(w[i:i+len(p)])!=p:continue
   j=i+len(p)
   while j<len(w) and (w[j] in NUM|NATO or w[j].isdigit()):j+=1
   put(i,j,'CALLSIGN');break
 # Longest command expressions first; literal grammar frozen before test inference.
 patterns=[('turn','to','the','left'),('turn','to','the','right'),('turn','left'),('turn','right'),('left','turn'),('right','turn'),('to','the','left'),('to','the','right')]
 for i in range(len(w)):
  for p in patterns:
   if tuple(w[i:i+len(p)])==p:put(i,i+len(p),'ACTION');break
  if w[i] in {'climb','descend','fly','set'}:put(i,i+1,'ACTION')
  if w[i]=='maintain' and i+1<len(w) and (w[i+1] in NUM or w[i+1] in {'flight','altitude'}):put(i,i+1,'ACTION')
  if w[i] in {'left','right'} and i+1<len(w) and w[i+1]=='heading':put(i,i+1,'ACTION')
  if w[i:i+2]==['flight','level']:
   j=nums(i+2);put(i,j,'ALT') if j>i+2 else None
  if w[i]=='heading':
   j=nums(i+1);put(i+1,j,'HDG')
  if w[i] in {'climb','descend','maintain'}:
   a=i+1
   while a<len(w) and w[a] in {'to','and','maintain','altitude'}:a+=1
   j=nums(a)
   if j>a:
    if j<len(w) and w[j]=='feet':j+=1
    put(a,j,'ALT')
 return tags
