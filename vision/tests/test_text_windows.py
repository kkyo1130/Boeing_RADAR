from vision.text_windows import labelled_regions


def rows():
    return [dict(text='250',score=1,box=[.1,.4,.2,.5]),
            dict(text='HDG',score=1,box=[.3,.3,.4,.36]),
            dict(text='ALT',score=1,box=[.5,.3,.6,.36]),
            dict(text='270',score=1,box=[.3,.4,.4,.5]),
            dict(text='03000',score=1,box=[.48,.4,.62,.5])]


def test_labels_anchor_observed_windows_without_selecting_ias():
    rois=labelled_regions(rows(),(1000,500))
    assert rois['hdg'][0]>250 and rois['alt'][0]>450
    data=rows();data[3]['text']='000';data[4]['text']='35000'
    assert labelled_regions(data,(1000,500))==rois


def test_missing_ambiguous_or_invalid_spans_stay_unknown():
    data=rows();data[3]['text']='999';assert labelled_regions(data,(1000,500)) is None
    data=rows();data[3]['score']=.1;assert labelled_regions(data,(1000,500)) is None
    data=rows();data.append(dict(data[3]));assert labelled_regions(data,(1000,500)) is None
    data=rows();data[1]['text']='IAS';assert labelled_regions(data,(1000,500)) is None


def test_missing_numeric_ocr_can_still_propose_window_from_labels_and_neighbor():
    data=rows();data.pop()  # ALT text was not recognized; do not require ALT OCR to find its box.
    rois=labelled_regions(data,(1000,500))
    assert rois is not None
    assert rois['alt'][0]<550<rois['alt'][2]
    assert rois['alt'][1]<=200 and rois['alt'][3]>=250
    data=[r for r in data if r['text']!='270']
    assert labelled_regions(data,(1000,500)) is None
