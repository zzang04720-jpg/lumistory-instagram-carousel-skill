"""Local preview first. External writes require explicit CLI flags."""
from __future__ import annotations
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def doctor() -> int:
    checks = {name: importlib.util.find_spec(module) is not None for name, module in {
        'Pillow': 'PIL', 'requests': 'requests', 'Beautiful Soup': 'bs4',
        'python-dotenv': 'dotenv', 'Streamlit': 'streamlit'}.items()}
    checks['Python >= 3.10'] = sys.version_info >= (3, 10)
    checks['bundled fonts (10)'] = len(list((ROOT / 'lumistory_fonts').glob('*.ttf'))) == 10
    for label, ok in checks.items():
        print(f"{'OK' if ok else 'MISSING'}: {label}")
    print('Offline inspection only; credentials and external API access were not tested.')
    return 0 if all(checks.values()) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Instagram carousel preview and reviewed publishing')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Offline dependency and font checks (no secrets read)')
    preview = sub.add_parser('preview', help='Create seven local PNGs and a manifest; no upload')
    source = preview.add_mutually_exclusive_group(required=True)
    source.add_argument('--url', help='Supported site /skills/<slug>/ URL')
    source.add_argument('--article-json', type=Path, help='Local Article JSON (see examples/article.json)')
    preview.add_argument('--theme', type=int, choices=range(1, 11), default=1)
    preview.add_argument('--output', type=Path)
    preview.add_argument('--include-dm', action='store_true', help='Include DM invitation only when replies are configured')
    stage = sub.add_parser('stage', help='Upload reviewed cards and create unpublished containers')
    stage.add_argument('manifest', type=Path)
    stage.add_argument('--reviewed', action='store_true', required=True)
    publish = sub.add_parser('publish', help='Publish a previously staged carousel publicly')
    publish.add_argument('manifest', type=Path)
    publish.add_argument('--confirm', action='store_true', required=True)
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        return doctor()
    try:
        if args.command == 'preview':
            from lumistory_cards import Article, OUTPUT, _article_url, fetch_article, render_carousel
            if args.article_json:
                article = Article(**json.loads(args.article_json.read_text(encoding='utf-8')))
                _article_url(article.url)
                if not article.title or not article.one_line or not article.why or not article.scenes:
                    raise ValueError('Article JSON is missing required content.')
            else:
                article = fetch_article(args.url)
            print(render_carousel(article, args.theme, args.output or OUTPUT, include_dm=args.include_dm))
        elif args.command == 'stage':
            from lumistory_publish import stage_manifest
            print(stage_manifest(args.manifest)['status'])
        else:
            from lumistory_publish import publish_manifest
            print(publish_manifest(args.manifest))
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
