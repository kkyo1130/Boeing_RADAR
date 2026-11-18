"""Seeded exposure, bloom, reflections and sensor/compression artefacts."""
import io
import cv2
import numpy as np
from PIL import Image


def camera_effects(image, rng):
    rgb=np.asarray(image.convert('RGB'),dtype=np.float32)/255
    height,width=rgb.shape[:2]
    exposure=rng.uniform(.85,1.45);strength=rng.uniform(.15,.8);sigma=rng.uniform(.0015,.006)*width
    bright=np.maximum(rgb-.55,0)
    halo=cv2.GaussianBlur(bright,(0,0),sigma)+.45*cv2.GaussianBlur(bright,(0,0),sigma*3)
    rgb=rgb*exposure+halo*strength
    reflection=None
    if rng.random()<.45:
        angle=rng.uniform(-1.2,1.2);center=rng.uniform(.1,.9);spread=rng.uniform(.025,.12);opacity=rng.uniform(.04,.20)
        yy,xx=np.mgrid[:height,:width];distance=(xx/width*np.cos(angle)+yy/height*np.sin(angle))-center
        rgb+=np.exp(-distance**2/(2*spread**2))[:,:,None].astype(np.float32)*opacity
        reflection=dict(angle=angle,center=center,width=spread,opacity=opacity)
    noise=rng.uniform(0,.012)
    pixels=np.clip(np.clip(rgb,0,1)+np.random.default_rng(rng.randrange(2**32)).normal(0,noise,rgb.shape),0,1)
    result=Image.fromarray(np.uint8(pixels*255));quality=rng.randrange(65,96);buffer=io.BytesIO()
    result.save(buffer,format='JPEG',quality=quality);result=Image.open(buffer).convert('RGB')
    return result,dict(exposure=exposure,bloom_strength=strength,bloom_sigma=sigma,reflection=reflection,noise_sigma=noise,jpeg_quality=quality)
