import numpy as np
from PIL import Image, ImageFont
from vision.generate_photo_mcp import transformed_box, replace_number


def test_projected_boxes_follow_geometry_and_clip_at_frame():
    h=np.array([[1,0,10],[0,1,-5],[0,0,1]],dtype=np.float64)
    assert transformed_box([5,10,30,40],h,(100,100))==[15,5,40,35]
    assert transformed_box([0,0,10,10],h,(15,15))==[10,0,15,5]


def test_numeric_replacement_does_not_change_surrounding_photo():
    im=Image.new('RGB',(200,100),(12,14,16));before=np.asarray(im).copy()
    font=ImageFont.load_default(size=40)
    replace_number(im,[10,10,100,70],'123',font)
    after=np.asarray(im)
    assert np.array_equal(before[:,110:],after[:,110:])
    assert np.any(before[10:70,10:100]!=after[10:70,10:100])


def test_versioned_character_preprocessing_rejects_border_without_filling_missing_digits():
    from PIL import ImageDraw
    from vision.mcp_character_ocr import segment,PREPROCESSING,BORDER_PREPROCESSING
    im=Image.new('RGB',(200,60),(12,14,16));draw=ImageDraw.Draw(im)
    for i in range(5):draw.rectangle((15+i*30,12,27+i*30,47),fill=(255,180,50))
    draw.line((185,5,185,54),fill=(255,180,50))
    assert segment(im,'alt',PREPROCESSING) is None
    assert len(segment(im,'alt',BORDER_PREPROCESSING)[0])==5
    draw.rectangle((15,0,28,59),fill=(12,14,16))
    assert segment(im,'alt',BORDER_PREPROCESSING) is None


def test_checkpoint_selection_prefers_fewer_wrong_outputs_then_coverage():
    from vision.train_character_ocr import selection_score
    def metric(accepted,correct):return dict(accepted=accepted,accepted_correct=correct,samples=20,exact_accuracy=.9)
    safe={k:metric(10,10) for k in ('hdg','alt')}
    wrong={k:metric(19,18) for k in ('hdg','alt')}
    covered={k:metric(15,15) for k in ('hdg','alt')}
    assert selection_score(safe)>selection_score(wrong)
    assert selection_score(covered)>selection_score(safe)


def test_components_mode_removes_two_pixel_edge_but_does_not_guess_missing_glyph():
    from PIL import ImageDraw
    from vision.mcp_character_ocr import segment,BORDER_PREPROCESSING,ARTIFACT_PREPROCESSING
    im=Image.new('RGB',(200,60),(12,14,16));draw=ImageDraw.Draw(im)
    for i in range(5):draw.rectangle((15+i*30,12,27+i*30,47),fill=(255,180,50))
    draw.rectangle((185,5,186,24),fill=(255,180,50))
    assert segment(im,'alt',BORDER_PREPROCESSING) is None
    assert len(segment(im,'alt',ARTIFACT_PREPROCESSING)[0])==5
    draw.rectangle((15,0,28,59),fill=(12,14,16))
    assert segment(im,'alt',ARTIFACT_PREPROCESSING) is None
