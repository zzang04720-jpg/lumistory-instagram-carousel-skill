import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ['SITE_URL'] = 'https://lumiestorytech.com'
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
import lumistory_cards as cards
from bs4 import BeautifulSoup


def article():
    return cards.Article('https://lumiestorytech.com/skills/test-guide/', 'test-guide',
        '반복 업무 정리', '업무 자동화', '반복 업무를 정리하는 가이드입니다.',
        '작업 순서를 정리하고 한 가지씩 시험합니다.', '같은 일을 반복할 때 도움이 됩니다.',
        ['파일 이름 정리', '자료를 표에 정리', '보고서 준비'], '자동 실행을 보장하지 않습니다.',
        ['폴더를 준비합니다', '파일을 확인합니다', '결과를 검토합니다'], ['결과 파일 확인'],
        'https://lumiestorytech.com/downloads/test.zip')

class CardsTests(unittest.TestCase):
    def test_heading_scope_extracts_nested_steps_without_next_section(self):
        soup = BeautifulSoup('<article><h2>따라 하기</h2><div><h3>1. 폴더 준비</h3><p>폴더를 만드세요.</p><h3>2. 실행</h3><p>미리보기를 실행하세요.</p></div><h2>다른 안내</h2><ul><li>포함 금지</li></ul></article>', 'html.parser')
        self.assertEqual(cards._section_items(soup, '따라 하기'), ['1. 폴더 준비', '2. 실행'])

    def test_draw_normalizes_kicker_and_preserves_title_newlines(self):
        from PIL import ImageDraw
        seen = []
        original = ImageDraw.ImageDraw.text
        def capture(draw, xy, text, *args, **kwargs):
            seen.append(text)
            return original(draw, xy, text, *args, **kwargs)
        with patch.object(ImageDraw.ImageDraw, 'text', capture):
            cards.render_slide(cards.Slide('body', '01 · WHY', '설치·사용\n안내', ['확인 → 시작']), 1, 2, 7)
        self.assertTrue(any('01 / WHY' == text for text in seen))
        self.assertFalse(any('·' in text or '→' in text for text in seen))

    def test_preview_all_themes_never_access_network(self):
        with tempfile.TemporaryDirectory() as tmp, patch('requests.sessions.Session.request', side_effect=AssertionError('preview used network')):
            for theme in range(1, 11):
                path = cards.render_carousel(article(), theme, Path(tmp))
                data = json.loads(path.read_text(encoding='utf-8'))
                self.assertEqual(data['status'], 'preview')
                self.assertEqual(len(data['images']), 7)
                self.assertNotIn('DM', data['caption'])
                self.assertNotIn('carousel_id', data)
                from PIL import Image
                for value in data['images']:
                    with Image.open(value) as im:
                        self.assertEqual(im.size, (1080, 1350))

    def test_cli_requires_confirmation_flags(self):
        import instagram_cli
        for command in ('stage', 'publish'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                instagram_cli.main([command, 'manifest.json'])
            self.assertEqual(error.exception.code, 2)

    def test_auto_and_dm_are_disabled_without_opt_in(self):
        import lumistory_auto
        import lumistory_dm_auto
        with patch.dict(os.environ, {'IG_AUTO_PUBLISH': '0', 'IG_AUTO_DM': '0'}), patch('requests.sessions.Session.request', side_effect=AssertionError('network used')):
            with self.assertRaises(SystemExit):
                lumistory_auto.main()
            with self.assertRaises(SystemExit):
                lumistory_dm_auto.main()

    def test_imports_without_site_credentials_or_playwright(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('SITE_', 'IG_', 'CLOUDINARY_'))}
        code = "import lumistory_cards, lumistory_publish, lumistory_auto, lumistory_dm_auto; import sys; assert 'playwright' not in sys.modules"
        result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

class PublishingTests(unittest.TestCase):
    def test_unknown_state_cannot_upload(self):
        import lumistory_publish as publishing
        with tempfile.TemporaryDirectory() as tmp:
            path = cards.render_carousel(article(), 1, Path(tmp))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["status"] = "invalid"
            path.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(publishing, "sign_cloudinary_upload") as upload:
                with self.assertRaises(ValueError):
                    publishing.stage_manifest(path)
                upload.assert_not_called()

    def test_publish_requires_staged_and_is_idempotent(self):
        import lumistory_publish as publishing
        with tempfile.TemporaryDirectory() as tmp:
            path = cards.render_carousel(article(), 1, Path(tmp))
            with patch.object(publishing, "publish_container") as publish:
                with self.assertRaises(ValueError):
                    publishing.publish_manifest(path)
                publish.assert_not_called()
            with patch.object(publishing, "ensure_config"), patch.object(publishing, "find_recent_duplicate_publish", return_value=None), patch.object(publishing, "sign_cloudinary_upload", return_value="https://example.com/card.png") as upload, patch.object(publishing, "create_item_container", return_value="item"), patch.object(publishing, "create_carousel_container", return_value="carousel"), patch.object(publishing.time, "sleep"):
                publishing.stage_manifest(path)
                self.assertEqual(upload.call_count, 7)
                publishing.stage_manifest(path)
                self.assertEqual(upload.call_count, 7)
            with patch.object(publishing, "BASE_DIR", Path(tmp)), patch.object(publishing, "publish_container", return_value="post-1") as publish, patch.object(publishing.requests, "get", side_effect=RuntimeError("permalink unavailable")):
                self.assertEqual(publishing.publish_manifest(path), "post-1")
                self.assertEqual(publishing.publish_manifest(path), "post-1")
                publish.assert_called_once()
                history = json.loads((Path(tmp) / "published_log.json").read_text(encoding="utf-8"))
                self.assertEqual(history[0]["published_post_id"], "post-1")

    def test_corrupt_duplicate_history_blocks(self):
        import publish_pipeline as pipeline
        with tempfile.TemporaryDirectory() as tmp, patch.object(pipeline, "BASE_DIR", Path(tmp)):
            (Path(tmp) / "published_log.json").write_text("broken", encoding="utf-8")
            with self.assertRaises(ValueError):
                pipeline.find_recent_duplicate_publish("caption")

if __name__ == '__main__':
    unittest.main()
