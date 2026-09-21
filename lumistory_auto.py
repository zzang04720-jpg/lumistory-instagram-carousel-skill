"""Scheduled entry point for the existing Windows task.

It intentionally has no question/interactive input: the task itself is the
user's opt-in. Do not run this file by hand unless a real automatic post is
wanted; it can publish publicly when IG_AUTO_PUBLISH=1.
"""

from __future__ import annotations

import os

from lumistory_cards import next_template_number, next_unpublished_article, render_carousel
from lumistory_publish import publish_manifest, stage_manifest
from publish_pipeline import log_line


def main() -> None:
    if os.environ.get("IG_AUTO_PUBLISH") != "1":
        raise SystemExit("자동 발행 안전장치: IG_AUTO_PUBLISH=1 일 때만 실행됩니다.")
    article = next_unpublished_article()
    if article is None:
        log_line("루미스토리 자동 발행 종료: 무료 ZIP이 있는 미발행 스킬 글이 없습니다.")
        return
    template = next_template_number()
    log_line(f"루미스토리 자동 발행 시작: {article.title} / 템플릿 {template:02d}")
    manifest = render_carousel(article, template)
    stage_manifest(manifest)
    post_id = publish_manifest(manifest)
    log_line(f"루미스토리 자동 발행 완료: {article.title} / post_id={post_id}")


if __name__ == "__main__":
    main()
