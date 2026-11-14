import math,urllib.request,os,io
from PIL import Image
def t(lon,lat,z):
  n=2**z; x=(lon+180)/360*n; y=(1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n
  return x,y
def stitch(name,z,lon0,lat0,lon1,lat1):
  x0,y0=t(lon0,lat1,z); x1,y1=t(lon1,lat0,z)
  tx0,ty0,tx1,ty1=int(x0),int(y0),int(x1),int(y1)
  W=(tx1-tx0+1)*256; H=(ty1-ty0+1)*256
  im=Image.new('RGB',(W,H),(255,255,255))
  for tx in range(tx0,tx1+1):
    for ty in range(ty0,ty1+1):
      fn=f'tiles/{z}_{tx}_{ty}.png'
      if not os.path.exists(fn):
        urllib.request.urlretrieve(f'https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{tx}/{ty}.png',fn)
      im.paste(Image.open(fn).convert('RGB'),((tx-tx0)*256,(ty-ty0)*256))
  # bounds of stitched image in tile coords
  im.save(f'{name}.jpg',quality=72,optimize=True)
  def inv(x,y):
    n=2**z; lon=x/n*360-180; lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n)))); return lon,lat
  lonA,latA=inv(tx0,ty0); lonB,latB=inv(tx1+1,ty1+1)
  print(name,z,W,H,os.path.getsize(f'{name}.jpg'),[lonA,latA,lonB,latB])
  return [lonA,latA,lonB,latB]
b1=stitch('base_local',14,139.49,35.53,139.70,35.635)
b2=stitch('base_wide',12,139.42,35.43,139.82,35.72)
import json;json.dump({'local':b1,'wide':b2},open('tilebounds.json','w'))
