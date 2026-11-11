"""Inference only for saved v3 models; no training or data writes."""
from pathlib import Path
import numpy as np
import torch
from torch import nn
from .preprocess_mcp_ocr import align

class DigitCNN(nn.Module):
    def __init__(self, n):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1,32,3,padding=1),nn.BatchNorm2d(32),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(32,64,3,padding=1),nn.BatchNorm2d(64),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(64,128,3,padding=1),nn.BatchNorm2d(128),nn.ReLU(),
            nn.Conv2d(128,128,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d((1,n)))
        self.head=nn.Linear(128,10)
    def forward(self,x):
        return self.head(self.features(x).squeeze(2).transpose(1,2))

class OCRv3:
    def __init__(self, checkpoints=None):
        checkpoints=Path(checkpoints or Path(__file__).parent/'checkpoints/mcp_ocr_v3')
        self.models={}
        for kind,n in (('hdg',3),('alt',5)):
            saved=torch.load(checkpoints/f'{kind}_best.pt',map_location='cpu',weights_only=True)
            if saved.get('kind')!=kind or saved.get('digits')!=n:
                raise ValueError(f'Unexpected checkpoint metadata: {kind}')
            model=DigitCNN(n);model.load_state_dict(saved['model']);model.eval()
            self.models[kind]=model
    def infer(self,image,kind):
        from PIL import Image
        aligned=align(image.convert('RGB'),kind)
        if aligned is None:
            return {'value':None,'model_score':None,'reason':'NO_AMBER_DIGITS'}
        n=3 if kind=='hdg' else 5
        image=aligned.convert('L').resize((36*n,48),Image.Resampling.BILINEAR)
        x=torch.from_numpy(np.asarray(image,dtype=np.float32).copy())[None,None]/255.
        with torch.inference_mode(): probabilities=self.models[kind](x).softmax(-1)[0]
        value=''.join(map(str,probabilities.argmax(-1).tolist()))
        score=float(probabilities.max(-1).values.min())
        if score < .75:
            return {'value':None,'model_score':score,'reason':'LOW_MODEL_SCORE'}
        if not (len(value)==n and value.isascii() and value.isdigit()) or (kind=='hdg' and int(value)>359):
            return {'value':None,'model_score':score,'reason':'OUT_OF_RANGE'}
        return {'value':value,'model_score':score,'reason':None}
