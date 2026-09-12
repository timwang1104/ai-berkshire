#!/usr/bin/env python3
"""微信公众号发布工具（官方「草稿箱 + 发布」能力）。

将一篇 Markdown 文章转换为微信公众号排版 HTML，走官方 API 建草稿，
可选直接发布（freepublish）。默认只建草稿，由人工在公众号后台确认后发布
（更安全，且不消耗订阅号"每天群发 1 次"的额度）。

依赖（均可选，缺封面/图片功能时降级）：
    requests   — 必需
    markdown   — Markdown -> HTML（建议安装）
    bs4        — 为 HTML 注入微信内联样式（建议安装）
    Pillow     — 自动生成封面图（--cover auto 时必需）

用法：
    python3 tools/wechat_mp_publish.py --article 文章.md [--cover auto|封面.png] [--publish] [--env .env] [--dry-run]
    python3 tools/wechat_mp_publish.py --check [--env .env]      # 只验证凭证与接口权限

配置（--env 指定的 .env 文件，或环境变量；.env 已被仓库 .gitignore 排除）：
    WECHAT_MP_APPID=wx...
    WECHAT_MP_SECRET=...
    # 可选：正文图片/封面如需直传，把脚本运行机 IP 加入公众号后台 IP 白名单。

说明：
    - token 缓存与封面素材缓存写入 {repo}/ai-berkshire/local/wechat_mp/（local/ 不入库）。
    - 只建草稿时不消耗"群发"次数；草稿出现在公众号后台「草稿箱」，人工确认后点发布即可。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
API_HOST = "https://api.weixin.qq.com"

# 本地状态目录（token 缓存 / 封面素材缓存 / 最近草稿记录），不入库
REPO_ROOT = Path(__file__).resolve().parent.parent
LOCAL_DIR = REPO_ROOT / "local" / "wechat_mp"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(msg, flush=True)


def _parse_resp(resp: requests.Response) -> dict:
    """解析微信响应 JSON。

    微信接口响应可能不带 charset，requests 的 .json() 会退化为按
    ISO-8859-1 解码（resp.text 默认 latin-1），导致中文显示为 mojibake
    （è¥æ¶...）。统一用 UTF-8 显式解码后再解析。
    """
    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    text = resp.content.decode("utf-8", errors="replace")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise RuntimeError(f"响应不是 JSON 对象: {text[:200]}")
    return data


def api_get(path: str, params: dict) -> dict:
    resp = requests.get(f"{API_HOST}{path}", params=params, timeout=30)
    data = _parse_resp(resp)
    if data.get("errcode"):
        raise RuntimeError(f"微信接口错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def api_post(path: str, access_token: str, json_body: dict) -> dict:
    # 重要：不能使用 requests 的 json= 参数。它默认 ensure_ascii=True，
    # 会把中文序列化成 \uXXXX 字面量发送；微信草稿箱/发布接口存在 bug，
    # 会把这些转义序列原样存库，导致后台显示 \uXXXX 而非中文。
    # 必须手动 dumps(ensure_ascii=False) 后以 UTF-8 原文发送。
    resp = requests.post(
        f"{API_HOST}{path}",
        params={"access_token": access_token},
        data=json.dumps(json_body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30,
    )
    data = _parse_resp(resp)
    if data.get("errcode"):
        raise RuntimeError(f"微信接口错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def api_upload(path: str, access_token: str, file_field: str, file_path: Path) -> dict:
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{API_HOST}{path}",
            params={"access_token": access_token},
            files={file_field: (file_path.name, f)},
            timeout=60,
        )
    data = _parse_resp(resp)
    if data.get("errcode"):
        raise RuntimeError(f"微信接口错误 {data.get('errcode')}: {data.get('errmsg')}")
    return data


def load_env(env_file: Path | None) -> dict:
    """读取 .env 文件（KEY=VALUE），环境变量优先。"""
    env: dict = {}
    if env_file and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("WECHAT_MP_APPID", "WECHAT_MP_SECRET"):
        if os.environ.get(key):
            env[key] = os.environ[key]
    return env


# ---------------------------------------------------------------------------
# access_token
# ---------------------------------------------------------------------------
def get_access_token(appid: str, secret: str) -> str:
    """获取并缓存 access_token（有效期 7200s）。"""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = LOCAL_DIR / "token.json"
    token: str | None = None
    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("appid") == appid and cached.get("expires_at", 0) > time.time() + 300:
                token = cached.get("access_token")
        except (json.JSONDecodeError, OSError):
            token = None

    if not token:
        data = api_get(
            "/cgi-bin/token",
            {
                "grant_type": "client_credential",
                "appid": appid,
                "secret": secret,
            },
        )
        token = str(data["access_token"])
        cache_file.write_text(
            json.dumps(
                {
                    "appid": appid,
                    "access_token": token,
                    "expires_at": int(time.time()) + int(data.get("expires_in", 7200)),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    return token


# ---------------------------------------------------------------------------
# Markdown -> 微信 HTML
# ---------------------------------------------------------------------------
_WX_SECTION_STYLE = (
    "font-size:15px;color:#3f3f3f;line-height:1.75;letter-spacing:0.5px;"
    "word-break:break-word;text-align:justify;"
)
_TAG_STYLES: dict[str, str] = {
    "p": "margin:0 0 14px;",
    "h1": "font-size:19px;font-weight:bold;color:#111;margin:22px 0 12px;line-height:1.4;",
    "h2": "font-size:17px;font-weight:bold;color:#111;margin:20px 0 12px;line-height:1.4;",
    "h3": "font-size:16px;font-weight:bold;color:#111;margin:18px 0 10px;line-height:1.4;",
    "h4": "font-size:15px;font-weight:bold;color:#111;margin:16px 0 8px;line-height:1.4;",
    "blockquote": (
        "border-left:4px solid #07c160;background:#f7fbf8;padding:10px 14px;"
        "color:#555;margin:14px 0;font-size:14px;"
    ),
    "table": "width:100%;border-collapse:collapse;margin:14px 0;font-size:13px;",
    "th": "border:1px solid #ddd;padding:8px 6px;background:#f2f2f2;font-weight:bold;text-align:left;",
    "td": "border:1px solid #ddd;padding:8px 6px;",
    "ul": "margin:0 0 14px;padding-left:20px;",
    "ol": "margin:0 0 14px;padding-left:20px;",
    "li": "margin:3px 0;",
    "code": "background:#f5f5f5;border-radius:3px;padding:2px 5px;font-size:13px;color:#c7254e;",
    "pre": "background:#f7f7f7;border-radius:4px;padding:12px;overflow-x:auto;font-size:13px;margin:14px 0;",
    "hr": "border:none;border-top:1px solid #e5e5e5;margin:18px 0;",
    "img": "max-width:100%;border-radius:4px;margin:12px 0;",
    "strong": "color:#111;",
    "a": "color:#07c160;text-decoration:none;",
}


def markdown_to_wechat_html(
    md_text: str,
    base_dir: Path,
    upload_image_paths: list[Path] | None = None,
) -> str:
    """Markdown -> 带内联样式的微信正文 HTML；本地图片上传换取线上 URL。"""
    import markdown as md_lib  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore

    upload_image_paths = upload_image_paths or []

    html = md_lib.markdown(
        md_text,
        extensions=["extra", "tables", "sane_lists", "nl2br"],
    )
    soup = BeautifulSoup(html, "html.parser")

    # 注入内联样式
    for tag, style in _TAG_STYLES.items():
        for node in soup.find_all(tag):
            existing = node.get("style", "")
            node["style"] = (style + existing) if existing else style
    # 表格嵌套 style 自动去 px 前的空格等不处理，微信接受这种写法

    # 本地图片 -> 上传换取线上 URL（正文图片必须为 http url）
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if not src or src.startswith(("http://", "https://", "//")):
            continue
        rel = Path(src)
        candidate = (base_dir / rel).resolve()
        if candidate.exists():
            if not upload_image_paths:
                raise RuntimeError(
                    f"正文含本地图片 {src}，但未提供 upload_image_paths（当前流程未接入图片上传）"
                )
            # 找到对应该路径的上传结果
            matched = next(
                (u for u in upload_image_paths if u.path == candidate),
                None,
            )
            if matched and matched.url:
                img["src"] = matched.url

    body = str(soup.body) if soup.body else str(soup)
    body = re.sub(r"^<body[^>]*>|</body>$", "", body, flags=re.IGNORECASE).strip()
    return f'<section style="{_WX_SECTION_STYLE}">{body}</section>'


# ---------------------------------------------------------------------------
# 封面图
# ---------------------------------------------------------------------------
def generate_cover(title: str, out_path: Path) -> None:
    """生成一张 900x383 封面（公众号推荐比例 2.35:1）。"""
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "自动生成封面需要 Pillow；请 `pip install Pillow` 或改用 --cover 指定图片"
        ) from exc

    W, H = 900, 383
    img = Image.new("RGB", (W, H), (7, 193, 96))  # 微信绿
    draw = ImageDraw.Draw(img)
    # 找可用中文字体
    font_candidates = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    font = None
    for fp in font_candidates:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 44)
                break
            except OSError:
                continue
    if font is None:
        font = ImageFont.load_default()

    # 渐变底色（上深下浅）
    for y in range(H):
        shade = int(90 * (1 - y / H))
        draw.line(
            [(0, y), (W, y)],
            fill=(7 + shade, 193 - shade, 96),
        )
    draw.rectangle([(40, 32), (W - 40, H - 32)], outline=(255, 255, 255), width=2)
    title_short = title if len(title) <= 20 else title[:20] + "…"
    draw.text((W // 2, H // 2), title_short, fill=(255, 255, 255), font=font, anchor="mm")
    img.save(out_path, "PNG")


def ensure_cover_media_id(access_token: str, appid: str, title: str, cover_arg: str) -> str:
    """获取封面图素材 media_id；按源文件 md5 缓存到 local/wechat_mp/。"""
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = LOCAL_DIR / "cover.json"

    if cover_arg == "auto":
        src_path = LOCAL_DIR / "cover.png"
        generate_cover(title, src_path)
        # v2：封面版式（无署名文字）——更新版式时递增版本号，强制缓存失效
        source_id = f"auto:v2:{hashlib.md5(title.encode()).hexdigest()[:16]}"
    else:
        src_path = Path(cover_arg).resolve()
        if not src_path.exists():
            raise RuntimeError(f"封面图不存在: {src_path}")
        with open(src_path, "rb") as f:
            source_id = "file:" + hashlib.md5(f.read()).hexdigest()

    if cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if cached.get("appid") == appid and cached.get("source_id") == source_id:
                return str(cached["media_id"])
        except (json.JSONDecodeError, OSError):
            pass

    data = api_upload(
        "/cgi-bin/material/add_material",
        access_token,
        "media",
        src_path,
    )
    media_id = str(data["media_id"])
    cache_file.write_text(
        json.dumps({"appid": appid, "source_id": source_id, "media_id": media_id}, ensure_ascii=False),
        encoding="utf-8",
    )
    return media_id


# ---------------------------------------------------------------------------
# 草稿 / 发布
# ---------------------------------------------------------------------------
def _truncate_utf8(text: str, max_bytes: int) -> str:
    """按 UTF-8 字节数截断（微信按字节计上限），避免截断多字节字符。"""
    if len(text.encode("utf-8")) <= max_bytes:
        return text
    result = ""
    for ch in text:
        if len((result + ch).encode("utf-8")) > max_bytes:
            break
        result += ch
    return result


def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    """解析 --- 分隔 frontmatter（title/digest/author）。

    兼容 claude 输出前可能的说明文字：取第一个 --- 块作为 frontmatter，
    并丢弃其之前的内容；全文无 --- 时按普通 Markdown 处理。
    """
    meta: dict = {}
    m = re.search(r"^---\s*\n(.*?)\n---\s*\n", md_text, flags=re.DOTALL | re.MULTILINE)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                meta[key.strip().lower()] = value.strip().strip('"').strip("'")
        md_text = md_text[m.end():]
    return meta, md_text


def create_draft(
    access_token: str,
    title: str,
    digest: str,
    content_html: str,
    thumb_media_id: str,
    author: str = "",
    source_url: str = "",
) -> str:
    """新增草稿，返回草稿 media_id。

    微信字段上限按 UTF-8 字节计：title 64B、digest 120B、author 8B。
    """
    article = {
        "title": _truncate_utf8(title, 64),
        "author": _truncate_utf8(author, 8) if author else "",
        "digest": _truncate_utf8(digest, 120) if digest else "",
        "content": content_html,
        "content_source_url": source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }
    data = api_post("/cgi-bin/draft/add", access_token, {"articles": [article]})
    return str(data["media_id"])


def publish_draft(access_token: str, draft_media_id: str) -> str:
    """发布草稿（freepublish/submit），返回 publish_id。"""
    data = api_post("/cgi-bin/freepublish/submit", access_token, {"media_id": draft_media_id})
    return str(data.get("publish_id", ""))


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="微信公众号发布工具（草稿 + 可选发布）")
    parser.add_argument("--article", type=str, help="Markdown 文章路径")
    parser.add_argument("--cover", type=str, default="auto", help="封面图路径或 auto（默认 auto 生成）")
    parser.add_argument("--publish", action="store_true", help="建草稿后直接发布（默认只建草稿，人工确认）")
    parser.add_argument("--env", type=str, default=None, help=".env 配置文件路径（默认 {repo}/.env）")
    parser.add_argument("--dry-run", action="store_true", help="只做 Markdown->HTML 转换，不调用微信接口")
    parser.add_argument("--check", action="store_true", help="只校验凭证/接口权限，不建草稿")
    parser.add_argument("--title", type=str, default=None, help="覆盖文章标题（默认取 frontmatter 或首行）")
    parser.add_argument("--digest", type=str, default=None, help="摘要（默认取 frontmatter 或正文前 100 字）")
    parser.add_argument("--author", type=str, default="", help="作者")
    parser.add_argument("--source-url", type=str, default="", help="原文链接")
    args = parser.parse_args()

    env_file = Path(args.env) if args.env else REPO_ROOT / ".env"
    env = load_env(env_file)

    if args.check:
        # 无需文章即可 check
        if not env.get("WECHAT_MP_APPID") or not env.get("WECHAT_MP_SECRET"):
            log("[ERROR] 缺少凭证：请在 .env 配置 WECHAT_MP_APPID / WECHAT_MP_SECRET，或设置环境变量")
            log(f"        .env 路径: {env_file}")
            return 2
        token = get_access_token(env["WECHAT_MP_APPID"], env["WECHAT_MP_SECRET"])
        log("[OK] access_token 获取成功（接口权限连通，IP 白名单正常）")
        return 0

    if not args.article:
        parser.error("--article 必填（--check 除外）")
    article_path = Path(args.article).resolve()
    if not article_path.exists():
        log(f"[ERROR] 文章不存在: {article_path}")
        return 2

    md_text = article_path.read_text(encoding="utf-8")
    meta, md_body = parse_frontmatter(md_text)
    title = args.title or meta.get("title") or (md_body.strip().splitlines()[0].lstrip("#").strip() if md_body.strip() else Path(article_path).stem)
    digest = args.digest or meta.get("digest") or re.sub(r"\s+", " ", md_body.strip())[:100]

    # Markdown -> HTML（dry-run 或真实流程都需要）
    content_html = markdown_to_wechat_html(md_body, article_path.parent, upload_image_paths=[])
    log(f"[1/4] Markdown -> HTML 完成（{len(content_html)} 字符）")
    if args.dry_run:
        out = article_path.with_suffix(".html")
        out.write_text(content_html, encoding="utf-8")
        log(f"[dry-run] HTML 已写出: {out}（未调用微信接口）")
        log(f"[dry-run] 标题: {title}")
        log(f"[dry-run] 摘要: {digest}")
        return 0

    if not env.get("WECHAT_MP_APPID") or not env.get("WECHAT_MP_SECRET"):
        log("[ERROR] 缺少凭证：请在 .env 配置 WECHAT_MP_APPID / WECHAT_MP_SECRET，或设置环境变量")
        log(f"        .env 路径: {env_file}")
        return 2
    appid = env["WECHAT_MP_APPID"]
    secret = env["WECHAT_MP_SECRET"]
    token = get_access_token(appid, secret)
    log("[2/4] access_token 获取成功")

    thumb_media_id = ensure_cover_media_id(token, appid, title, args.cover)
    log(f"[3/4] 封面素材就绪 media_id={thumb_media_id}")

    draft_media_id = create_draft(
        token,
        title=title,
        digest=digest,
        content_html=content_html,
        thumb_media_id=thumb_media_id,
        author=args.author,
        source_url=args.source_url,
    )
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    (LOCAL_DIR / "last_draft.json").write_text(
        json.dumps(
            {
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "title": title,
                "digest": digest,
                "draft_media_id": draft_media_id,
                "article_file": str(article_path),
                "published": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log(f"[4/4] ✅ 草稿已创建 media_id={draft_media_id}")
    log(f"      → 请到公众号后台「草稿箱」人工确认后发布")
    log(f"      → 记录: {LOCAL_DIR / 'last_draft.json'}")

    if args.publish:
        publish_id = publish_draft(token, draft_media_id)
        log(f"      → 已发布 publish_id={publish_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())