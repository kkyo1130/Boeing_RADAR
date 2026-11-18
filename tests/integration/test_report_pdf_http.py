"""Downloaded PDF uses the same frozen record over a real localhost HTTP server."""
from io import BytesIO
from pypdf import PdfReader
from test_validation_regression_http import establish_normal


def test_summary_and_register_download_after_end(producer):
    p = producer
    establish_normal(p)
    p.request('POST', p.path + '/end')
    before = p.request('GET', p.path + '/report.json')
    response = p.client.get(p.path + '/report.pdf')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['cache-control'] == 'no-store'
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) == 2
    assert 'OVERALL FLIGHT SUMMARY' in reader.pages[0].extract_text()
    log = reader.pages[1].extract_text()
    assert 'Complete instruction register' in log and 'I001' in log and 'I002' in log
    assert 'ALT 3000' in log and 'HDG 270' in log
    assert p.request('GET', p.path + '/report.json') == before
