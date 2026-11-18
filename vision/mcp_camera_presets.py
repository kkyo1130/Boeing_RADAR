V6_TRAIN = [('123','04500'),('287','13700'),('054','21000'),('349','07800'),
            ('201','15400'),('308','06300'),('076','19800'),('195','32700')]
V6_TEST = [('032','00600'),('264','28400')]

def collection_plan(legacy=False, v6=None):
    from mcp_display_sync import PRESETS
    if legacy and v6:
        raise ValueError('Choose one preset plan')
    if v6:
        return (V6_TRAIN if v6 == 'train' else V6_TEST), 20, v6
    return (PRESETS,15,'train') if legacy else (None,15,'train')
