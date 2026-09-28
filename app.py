"""LumiStory Instagram card-news studio. Run: .venv\\Scripts\\streamlit run app.py"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from lumistory_cards import THEMES, fetch_article, list_articles, next_template_number, render_carousel
from lumistory_publish import publish_manifest, stage_manifest

st.set_page_config(page_title="루미스토리 인스타 카드뉴스", page_icon="✨", layout="wide")
for key, value in {"articles": [], "manifest": None, "manifest_data": None}.items():
    st.session_state.setdefault(key, value)

st.markdown("""
<style>
:root{--ink:#171719;--paper:#fffaf0;--red:#e8473f;--yellow:#ffe05a;--muted:#776f65}
.stApp{background:var(--paper);color:var(--ink)}[data-testid="stHeader"]{background:transparent}
[data-testid="stMainBlockContainer"]{max-width:1180px;padding-top:2.3rem}
.hero{border:4px solid var(--ink);border-radius:28px;background:var(--yellow);padding:1.7rem 2rem;box-shadow:9px 9px 0 var(--red);margin-bottom:1.5rem}
.hero small{font-weight:800;letter-spacing:.08em}.hero h1{margin:.25rem 0;font-size:2.45rem;line-height:1.1}.hero p{margin:0;font-size:1rem}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border:2px solid var(--ink);border-radius:20px;padding:1.25rem}
.note{color:var(--muted);font-size:.93rem}div.stButton>button[kind="primary"]{background:var(--red);border-color:var(--red);font-weight:800;min-height:3rem}
div.stButton>button[kind="secondary"]{border:2px solid var(--ink);font-weight:700}div[data-testid="stImage"] img{border:2px solid var(--ink);border-radius:12px}
</style>
<section class="hero"><small>LUMIESTORY · INSTAGRAM STUDIO</small><h1>사이트 글을<br>인스타 카드뉴스로</h1><p>글을 고르고 → 카드와 캡션을 확인하고 → 마지막에만 발행합니다.</p></section>
""", unsafe_allow_html=True)

def refresh_articles() -> None:
    with st.spinner("루미스토리의 스킬 글을 읽는 중입니다..."):
        st.session_state.articles = list_articles()

def load_manifest(path: Path) -> None:
    st.session_state.ready_to_stage = False
    st.session_state.ready_to_publish = False
    st.session_state.manifest = str(path)
    st.session_state.manifest_data = json.loads(path.read_text(encoding="utf-8"))

with st.expander("이전에 만든 미리보기 다시 열기"):
    from lumistory_cards import OUTPUT
    saved = []
    for candidate in sorted(OUTPUT.glob("*/manifest.json"), reverse=True):
        try:
            info = json.loads(candidate.read_text(encoding="utf-8"))
            if info.get("status") in {"preview", "staged"}:
                saved.append(candidate)
        except (OSError, ValueError):
            continue
    if saved:
        chosen = st.selectbox("저장된 카드뉴스", saved, format_func=lambda path: path.parent.name)
        if st.button("미리보기 열기"):
            load_manifest(chosen)
    else:
        st.caption("저장된 미발행 카드가 없습니다.")

with st.container(border=True):
    st.subheader("1. 사이트 글 고르기")
    if st.button("최신 글 불러오기", type="primary", use_container_width=True) or not st.session_state.articles:
        try:
            refresh_articles()
        except Exception as exc:
            st.error(f"글 목록을 불러오지 못했습니다: {exc}")
    articles = st.session_state.articles
    selected = None
    if articles:
        labels = {f"{item['title']}  ·  {item['description']}": item for item in articles}
        selected = labels[st.selectbox("카드뉴스로 만들 글", list(labels), label_visibility="collapsed")]

with st.container(border=True):
    st.subheader("2. 디자인 선택")
    recommended = next_template_number()
    options = {f"{i:02d}. {name} ({font})": i for i, (name, font, *_colors) in enumerate(THEMES, 1)}
    choice = st.selectbox("이번 카드뉴스 템플릿", list(options), index=recommended - 1, label_visibility="collapsed")
    template_number = options[choice]
    st.markdown(f"<p class='note'>이번 추천은 <b>{recommended:02d}번</b>입니다. 게시할 때마다 1~10번이 순서대로 바뀌며, 지금은 직접 고를 수도 있어요.</p>", unsafe_allow_html=True)
    include_dm = st.checkbox("댓글 DM 안내 문구 넣기 (직접 답장 또는 별도 DM 설정 필요)", value=False)
    if selected and st.button("카드뉴스 만들기", type="primary", use_container_width=True):
        try:
            with st.spinner("사이트 본문을 읽고 카드와 캡션을 만드는 중입니다..."):
                load_manifest(render_carousel(fetch_article(selected["url"]), template_number, include_dm=include_dm))
        except Exception as exc:
            st.error(f"카드뉴스 제작을 중단했습니다: {exc}")

manifest_path = Path(st.session_state.manifest) if st.session_state.manifest else None
data = st.session_state.manifest_data
if manifest_path and data:
    with st.container(border=True):
        st.subheader("3. 카드와 캡션 확인")
        st.caption(f"글: {data['article']['title']} · 템플릿: {data['template_number']:02d}. {data['template_name']}")
        columns = st.columns(4)
        for index, image in enumerate(data["images"]):
            with columns[index % 4]:
                st.image(image, use_container_width=True)
                st.caption(f"{index + 1} / {len(data['images'])}")
        st.text_area("인스타그램 캡션", data["caption"], height=260, disabled=True)
        st.info("무료 파일이 있는 글만 ‘무료 ZIP’ 문구를 씁니다. 무료파일 DM 자동응답은 인스타그램 DM 자동화 도구에서 별도로 연결해야 하며, 연결 전에는 직접 답장해 주세요.")

    with st.container(border=True):
        st.subheader("4. 인스타그램 발행")
        if data.get("status") == "preview":
            st.warning("아직 인스타그램에 올라가지 않았습니다. 아래 버튼은 이미지 업로드와 비공개 발행 준비까지만 합니다.")
            ready = st.checkbox("카드 7장과 캡션을 확인했습니다.", key="ready_to_stage")
            if st.button("발행 준비하기", type="primary", disabled=not ready, use_container_width=True):
                try:
                    with st.spinner("이미지를 업로드하고 인스타그램 발행 준비 중입니다..."):
                        st.session_state.manifest_data = stage_manifest(manifest_path)
                        st.rerun()
                except Exception as exc:
                    st.error(f"발행 준비에 실패했습니다: {exc}")
        elif data.get("status") == "staged":
            st.warning("발행 준비가 끝났습니다. 아래 버튼을 누르면 인스타그램에 공개됩니다. 이 동작은 되돌릴 수 없습니다.")
            confirmed = st.checkbox("이 카드뉴스를 지금 공개 발행하는 것을 확인합니다.", key="ready_to_publish")
            if st.button("지금 인스타그램에 발행", type="primary", disabled=not confirmed, use_container_width=True):
                try:
                    with st.spinner("인스타그램에 공개하는 중입니다..."):
                        publish_manifest(manifest_path)
                        st.session_state.manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
                        st.rerun()
                except Exception as exc:
                    st.error(f"발행에 실패했습니다: {exc}")
        elif data.get("status") == "published":
            st.success(f"발행 완료 · 게시물 ID: {data.get('published_post_id', '-')}")
            st.caption("게시 기록을 저장했습니다. 자동 예약은 같은 원문을 건너뜁니다.")
    st.caption(f"작업 폴더: {manifest_path.parent}")
else:
    st.markdown("<p class='note'>글을 고르고 ‘카드뉴스 만들기’를 누르면 여기에서 7장을 먼저 확인할 수 있어요.</p>", unsafe_allow_html=True)
