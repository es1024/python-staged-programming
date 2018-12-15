import macropy.activate
from img import *
import sys

def doblur(a):
    blur_x = (a.shift(-1,0) + a + a.shift(1,0))*(1.0/3.0)
    blur_y = (blur_x.shift(0,-1) + blur_x + blur_x.shift(0,1))*(1.0/3.0) 
    return blur_y

r = (doblur(Image.input(0)))

method, ifile, ofile = sys.argv[1:]
inputimage = ConcreteImage()
inputimage.load(ifile)
result = r.run(method, inputimage)
result.save(ofile)

