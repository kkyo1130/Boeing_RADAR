"""Own synthetic fixtures only. Not a cockpit accuracy benchmark."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

root = Path(__file__).parent
font = ImageFont.load_default(size=64)
labels = []
for name, altitude, heading in [("normal", "3000", "270"), ("changed", "3500", "290"),
                               ("north", "16000", "000"), ("invalid_heading", "3000", "360")]:
    image = Image.new("RGB", (800, 300), "#20252b")
    draw = ImageDraw.Draw(image)
    draw.text((35, 35), "SELECTED ALT (FT)", fill="white")
    draw.text((445, 35), "SELECTED HDG", fill="white")
    draw.rectangle((30,100,379,209), fill="black")
    draw.rectangle((440,100,769,209), fill="black")
    draw.text((50,115), altitude, font=font, fill="white")
    draw.text((460,115), heading, font=font, fill="white")
    image.save(root / "fixtures" / (name + ".png"))
    labels.append({"image":name+".png", "altitude":int(altitude), "heading":int(heading) if int(heading)<360 else None})
    if name == "normal":
        covered = image.copy()
        ImageDraw.Draw(covered).rectangle((30,100,379,209), fill="black")
        covered.save(root / "fixtures" / "occluded.png")
        labels.append({"image":"occluded.png","altitude":None,"heading":270})
        image.filter(ImageFilter.GaussianBlur(8)).save(root / "fixtures" / "blurred.png")
        labels.append({"image":"blurred.png","altitude":None,"heading":None,"evaluate":"exploratory; no fixed expectation"})
(root / "labels.json").write_text(json.dumps(labels, indent=2))
