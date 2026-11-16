import importlib.util
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'city-download.py'
spec = importlib.util.spec_from_file_location('city_download', SCRIPT)
city_download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(city_download)

MEETING_HTML = '''
<a href="documents/g25450/Public reports pack 14th-Jul-2026.pdf?T=10">Public reports pack</a>
<table><tr>
  <td class="mgItemNumberCell"><p class="mgAiTitleTxt"><a name="AI1"></a>10.</p></td>
  <td><p class="mgAiTitleTxt"><a class="mgAiTitleLnk" href="documents/s235511/Hampstead Heath Outturn 2025-26.pdf"
      title="Link to document '&#42;Hampstead Heath 2025&#47;26 Outturn' pdf file">*Hampstead Heath 2025/26 Outturn</a></p>
    <ul><li><a href="documents/s235512/Outturn Appendix 1.pdf"
      title="Link to document 'Outturn Appendix 1' pdf file">Outturn Appendix 1</a></li></ul></td>
</tr><tr>
  <td class="mgItemNumberCell"><p class="mgAiTitleTxt">3a.</p></td>
  <td><p class="mgAiTitleTxt"><a class="mgAiTitleLnk" href="documents/s235500/Minutes.pdf"
      title="Link to document 'Draft minutes' pdf file">Draft minutes</a></p></td>
</tr></table>
'''


class FakeSession:
    def get(self, url, timeout):
        class Response:
            status_code = 200
            text = '' if 'mgChooseDocPack' in url else MEETING_HTML

            def raise_for_status(self):
                pass
        return Response()


def test_find_documents_names_files_by_meeting_and_agenda_item(monkeypatch) -> None:
    monkeypatch.setattr(city_download, 'REQUEST_DELAY_SECONDS', 0)
    meeting = city_download.Meeting(25450, date(2026, 7, 14), 'https://example.test/meeting')
    documents = city_download.find_documents(FakeSession(), meeting, True, True)
    assert [(doc.path, doc.doc_type, doc.item, doc.item_title) for doc in documents] == [
        ('2026-0714/reports-pack.pdf', 'reports-pack', '', ''),
        ('2026-0714/10-s235511-hampstead-heath-2025-26-outturn.pdf', 'document', '10',
         '*Hampstead Heath 2025/26 Outturn'),
        ('2026-0714/10-s235512-outturn-appendix-1.pdf', 'document', '10', '*Hampstead Heath 2025/26 Outturn'),
        ('2026-0714/03a-s235500-draft-minutes.pdf', 'document', '3a', 'Draft minutes'),
    ]


def test_fetch_retries_transient_server_errors(monkeypatch) -> None:
    monkeypatch.setattr(city_download, 'REQUEST_DELAY_SECONDS', 0)
    monkeypatch.setattr(city_download, 'RETRY_DELAYS_SECONDS', (0, 0))
    statuses = [504, 503, 200]

    class Response:
        def __init__(self, status_code):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise city_download.requests.HTTPError(str(self.status_code))

    class Session:
        def get(self, url, timeout):
            return Response(statuses.pop(0))

    assert city_download.fetch(Session(), 'https://example.test/doc.pdf').status_code == 200
    assert statuses == []
