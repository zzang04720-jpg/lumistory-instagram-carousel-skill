"""UI preview smoke test: mocked source and no network allowed."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['PYTHON_DOTENV_DISABLED'] = '1'
from streamlit.testing.v1 import AppTest
import lumistory_cards as cards

class AppTests(unittest.TestCase):
    def test_preview_requires_review_before_external_upload(self):
        root = Path(__file__).resolve().parents[1]
        article = cards.Article(**json.loads((root / 'examples/article.json').read_text(encoding='utf-8')))
        render = cards.render_carousel
        with tempfile.TemporaryDirectory() as tmp, patch.object(cards, 'list_articles', return_value=[{'title':article.title,'description':article.description,'url':article.url}]), patch.object(cards,'fetch_article',return_value=article), patch.object(cards, 'render_carousel', side_effect=lambda a, t, **kw: render(a,t,Path(tmp),**kw)), patch('requests.sessions.Session.request',side_effect=AssertionError('network forbidden')):
            app = AppTest.from_file(str(root / 'app.py')).run(timeout=20)
            self.assertFalse(app.exception)
            next(b for b in app.button if b.label == '카드뉴스 만들기').click().run(timeout=20)
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state.manifest_data['status'], 'preview')
            self.assertTrue(next(b for b in app.button if b.label == '발행 준비하기').disabled)
