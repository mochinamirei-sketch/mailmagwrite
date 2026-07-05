import streamlit as st
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("パスワード", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input("パスワード", type="password", on_change=password_entered, key="password")
        st.error("パスワードが違います")
        st.stop()

check_password()
import json
import uuid
import copy
import os
import re
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="ハチカッテ ニュースレター作成ツール", layout="wide")

BANNER_DEFAULTS_FILE = os.path.join(os.path.dirname(__file__), "banner_defaults.json")

INITIAL_BANNER_DEFAULTS = [
    {
        "link_url": "https://littlevillage.snack.chillnn.com/?utm_source=newsletter&utm_medium=email&utm_campaign=20250628&mdkey={{MDKEY}}",
        "image_url": "https://8katte.com/pic-labo/minibanner_littlevillage_1.jpg",
    },
    {
        "link_url": "https://8katte.com/SHOP/hamara-2019-01.html?utm_source=newsletter&utm_medium=email&utm_campaign=20260627&mdkey={{MDKEY}}",
        "image_url": "https://8katte.com/pic-labo/mini_corn2024_01.jpg",
    },
]


def load_banner_defaults():
    if os.path.exists(BANNER_DEFAULTS_FILE):
        try:
            with open(BANNER_DEFAULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return copy.deepcopy(INITIAL_BANNER_DEFAULTS)


def save_banner_defaults(banners):
    with open(BANNER_DEFAULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(banners, f, ensure_ascii=False, indent=2)


def new_uid():
    return uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------
# 商品ページのスクレイピング
# ---------------------------------------------------------------------------

def fetch_product_info(url: str) -> dict:
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        def meta(prop):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            return tag["content"].strip() if tag and tag.get("content") else ""

        title = meta("og:title") or (soup.title.string.strip() if soup.title and soup.title.string else "")
        description = meta("og:description") or meta("description")
        image = meta("og:image")
        return {"title": title, "description": description, "image": image, "ok": True}
    except Exception as e:
        return {"title": "", "description": "", "image": "", "ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Claude APIでタイトル・本文を自動生成
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """あなたは「ハチカッテ」（八ヶ岳の産直ECサイト）のメールマガジン担当のコピーライターです。
渡された商品ページ情報とアピールしたい方向性をもとに、これまでのメルマガと同じ文体でタイトルと本文を書いてください。

本文の構成:
1. 導入（1〜2文程度）
2. 【おすすめの3ポイント】として3点。各ポイントは「1．見出し」の後に一文の説明を続ける
3. 締めの一文

出力は次のJSON形式のみを返してください。前後に説明文や```は付けないでください。
{"title": "タイトル文", "body": "本文全体。段落の区切りは\\n\\nで表現する"}
"""


def generate_copy_with_claude(product_info: dict, direction: str, url: str, api_key: str) -> dict:
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        user_msg = (
            f"商品ページタイトル: {product_info.get('title', '')}\n"
            f"商品説明: {product_info.get('description', '')}\n"
            f"商品URL: {url}\n"
            f"アピールしたい方向性: {direction}"
        )
        resp = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return {"title": data.get("title", ""), "body": data.get("body", ""), "ok": True}
        return {"title": "", "body": "", "ok": False, "error": "応答をJSONとして解釈できませんでした"}
    except Exception as e:
        return {"title": "", "body": "", "ok": False, "error": str(e)}


def fallback_copy(product_info: dict, direction: str) -> dict:
    title = product_info.get("title", "") or "（タイトル未取得：手動で入力してください）"
    body = product_info.get("description", "") or ""
    if direction:
        body = f"{body}\n\n（アピールポイント：{direction}）" if body else f"（アピールポイント：{direction}）"
    return {"title": title, "body": body}


# ---------------------------------------------------------------------------
# JSON生成パーツ
# ---------------------------------------------------------------------------

TOP_LEVEL_TEMPLATE = {
    "tagName": "mj-global-style",
    "attributes": {
        "h1:color": "#000",
        "h1:font-family": "Helvetica, sans-serif",
        "h2:color": "#000",
        "h2:font-family": "Ubuntu, Helvetica, Arial, sans-serif",
        "h3:color": "#000",
        "h3:font-family": "Ubuntu, Helvetica, Arial, sans-serif",
        ":color": "#000",
        ":font-family": "Ubuntu, Helvetica, Arial, sans-serif",
        ":line-height": "1.5",
        "a:color": "#24bfbc",
        "button:background-color": "#e85034",
        "containerWidth": 600,
        "fonts": "Helvetica,sans-serif,Ubuntu,Arial",
        "mj-text": {"line-height": 1.5, "font-size": 15, "font-family": "Ubuntu, sans-serif"},
        "mj-button": {"font-size": "13px"},
        "mj-preview": {"text": ""},
    },
    "children": [
        {
            "tagName": "mj-body",
            "attributes": {"background-color": "#FFFFFF", "containerWidth": 600},
            "children": [],
        }
    ],
    "fonts": ["Ubuntu, sans-serif", "Ubuntu, Helvetica, Arial"],
    "style": {
        "h1": {"font-family": "Ubuntu, sans-serif", "font-size": "22px", "font-weight": "bold"},
        "a": {"color": "#0000EE"},
        "h2": {"font-family": "Ubuntu, Helvetica, Arial", "font-size": "17px", "font-weight": "bold"},
        "h3": {"font-family": "Ubuntu, Helvetica, Arial", "font-size": "13px", "font-weight": "bold"},
        "p": {"font-family": "Ubuntu, sans-serif", "font-size": "11px"},
        "ul": {"font-size": "11px", "font-family": "Ubuntu, sans-serif"},
        "li": {"font-size": "11px", "font-family": "Ubuntu, sans-serif"},
        "ol": {"font-size": "11px", "font-family": "Ubuntu, sans-serif"},
        ".rounded>table": {"border-collapse": "separate"},
    },
    "feedBlocksApplyToAll": {},
}


def header_section(newsletter_date: str):
    return {
        "tagName": "mj-section",
        "attributes": {"full-width": "600px", "padding": "15px 0px 0px 0px", "mj-class": "section"},
        "children": [
            {
                "tagName": "mj-column",
                "attributes": {"width": "50%", "vertical-align": "top"},
                "children": [
                    {
                        "tagName": "mj-image",
                        "uid": new_uid(),
                        "attributes": {
                            "alt": "",
                            "containerWidth": 300,
                            "href": "",
                            "padding": "0px 15px 0px 15px",
                            "src": "https://d2q69ad2uaogi7.cloudfront.net/plugin-assets/29318/9ee54d0cfc0fa7849b65924b263ec367bfbeb6726c97767fb857cd61f586ae4a/logo.png",
                            "align": "left",
                            "fluid-on-mobile": "false",
                            "width": "180",
                        },
                    }
                ],
                "uid": new_uid(),
            },
            {
                "tagName": "mj-column",
                "attributes": {"width": "50%", "vertical-align": "top"},
                "children": [
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "42px 15px 0px 15px",
                            "line-height": 1.5,
                            "containerWidth": 300,
                        },
                        "content": f'<p style="text-align: right;">NEWSLETTER\u3000{newsletter_date}<br><!-- P--></p>',
                    }
                ],
                "uid": new_uid(),
            },
        ],
        "layout": 1,
        "backgroundColor": "",
        "backgroundImage": "",
        "paddingTop": 0,
        "paddingBottom": 0,
        "paddingLeft": 0,
        "paddingRight": 0,
        "uid": new_uid(),
    }


def points_section():
    return {
        "tagName": "mj-section",
        "attributes": {"full-width": "600px", "padding": "10px 0px 10px 0px", "mj-class": "section"},
        "children": [
            {
                "tagName": "mj-column",
                "attributes": {"width": "100%", "vertical-align": "top"},
                "children": [
                    {
                        "tagName": "mj-divider",
                        "uid": new_uid(),
                        "attributes": {
                            "border-color": "#000000",
                            "border-style": "solid",
                            "border-width": "1px",
                            "padding-top": 10,
                            "padding-right": None,
                            "padding": "10px 10px",
                            "padding-bottom": None,
                            "padding-left": None,
                            "containerWidth": 600,
                        },
                    },
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "0px 15px 0px 15px",
                            "line-height": 1.5,
                            "containerWidth": 600,
                        },
                        "content": (
                            '<p><span style="font-size: 12px;">ハチカッテ会員名 ： '
                            '{{NAM_SEI}} {{NAM_MEI}} 様</span><br>'
                            '<span style="font-size: 12px;">{{NAM_SEI}}様のログインID ： {{MEM_ID}}</span><br>'
                            '<span style="font-size: 12px;">お手持ちのポイントの残高 ： {{HOLD_PNT}}</span><br>'
                            '<span style="font-size: 12px;">お手持ちのポイントの有効期限 ： {{LOST_YMD}}</span><br>'
                            "<!-- P--></p>"
                        ),
                    },
                ],
                "uid": new_uid(),
            }
        ],
        "layout": 1,
        "backgroundColor": "",
        "backgroundImage": "",
        "paddingTop": 0,
        "paddingBottom": 0,
        "paddingLeft": 0,
        "paddingRight": 0,
        "uid": new_uid(),
    }


def body_to_html(body_text: str) -> str:
    paragraphs = [p.strip() for p in body_text.strip().split("\n\n") if p.strip()]
    html_parts = []
    for para in paragraphs:
        inner = para.replace("\n", "<br>")
        html_parts.append(f'<p><span style="font-size: 14px;">{inner}</span></p>')
    return "\n".join(html_parts)


def product_section(title: str, image_url: str, body_text: str, button_url: str, button_text: str = "ご購入はこちら"):
    return {
        "tagName": "mj-section",
        "attributes": {
            "full-width": "600px",
            "padding": "0px 0px 0px 0px",
            "border": "2px #000000 none",
            "mj-class": "section",
        },
        "children": [
            {
                "tagName": "mj-column",
                "attributes": {"width": "100%", "vertical-align": "top"},
                "children": [
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "0px 15px 15px 15px",
                            "line-height": 1.5,
                            "containerWidth": 600,
                        },
                        "content": (
                            '<h1 style="font-size: 15px !important; line-height: 1.5; '
                            'border-left: 4px solid #000; padding: 0.5rem 0.5rem; margin: 0 auto;">'
                            f'<span style="font-size: 22px;">{title}</span></h1>'
                        ),
                    },
                    {
                        "tagName": "mj-image",
                        "uid": new_uid(),
                        "attributes": {
                            "alt": "",
                            "containerWidth": 600,
                            "href": "",
                            "padding": "0px 15px 15px 15px",
                            "src": image_url,
                            "fluid-on-mobile": "false",
                            "border-radius": "0px 0px 0px 0px",
                        },
                    },
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "0px 15px 15px 15px",
                            "line-height": 1.5,
                            "containerWidth": 600,
                        },
                        "content": body_to_html(body_text),
                    },
                    {
                        "tagName": "mj-button",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "center",
                            "background-color": "#417505",
                            "color": "#ffffff",
                            "border-radius": "10px",
                            "font-size": "18px",
                            "padding": "15px 15px 15px 15px",
                            "inner-padding": "15px 90px 15px 90px",
                            "href": button_url,
                            "font-family": "Ubuntu, Helvetica, Arial, sans-serif, Helvetica, Arial, sans-serif",
                            "containerWidth": 600,
                            "border": "0px #000000 solid",
                            "line-height": "22.5px",
                            "font-weight": "normal",
                            "font-style": "normal",
                            "text-transform": "none",
                            "text-decoration": "none",
                        },
                        "content": f"<div><span style=\"font-size: 18px;\"><strong>{button_text}</strong></span></div>",
                    },
                    {
                        "tagName": "mj-spacer",
                        "uid": new_uid(),
                        "attributes": {"height": "50px", "containerWidth": 600},
                    },
                ],
                "uid": new_uid(),
            }
        ],
        "layout": 1,
        "backgroundColor": None,
        "backgroundImage": None,
        "paddingTop": 0,
        "paddingBottom": 0,
        "paddingLeft": 0,
        "paddingRight": 0,
        "uid": new_uid(),
    }


def banner_section(banners: list):
    return {
        "tagName": "mj-section",
        "attributes": {"full-width": "full-width", "padding": "10px 15px 10px 15px", "in-group": False, "mj-class": "section"},
        "children": [
            {
                "tagName": "mj-column",
                "attributes": {"width": "50%", "vertical-align": "top", "border-radius": "0px", "padding": "10px 10px 10px 10px", "css-class": None},
                "children": [
                    {
                        "tagName": "mj-image",
                        "uid": new_uid(),
                        "attributes": {
                            "alt": "",
                            "containerWidth": 300,
                            "href": banners[0]["link_url"],
                            "padding": "0px 0px 0px 0px",
                            "src": banners[0]["image_url"],
                            "fluid-on-mobile": "true",
                            "width": "290",
                            "border-radius": "0px 0px 0px 0px",
                        },
                    }
                ],
                "uid": new_uid(),
            },
            {
                "tagName": "mj-column",
                "attributes": {"width": "50%", "vertical-align": "top", "padding": "0px 0px 0px 0px"},
                "children": [
                    {
                        "tagName": "mj-image",
                        "uid": new_uid(),
                        "attributes": {
                            "alt": "",
                            "containerWidth": 300,
                            "href": banners[1]["link_url"],
                            "padding": "10px 10px 10px 10px",
                            "src": banners[1]["image_url"],
                            "fluid-on-mobile": "true",
                            "width": "290",
                            "border-radius": "0px 0px 0px 0px",
                        },
                    }
                ],
                "uid": new_uid(),
            },
        ],
        "layout": 1,
        "backgroundColor": "",
        "backgroundImage": "",
        "paddingTop": 0,
        "paddingBottom": 0,
        "paddingLeft": 0,
        "paddingRight": 0,
        "uid": new_uid(),
    }


def thanks_section():
    return {
        "tagName": "mj-section",
        "attributes": {"full-width": "full-width", "padding": "10px 0px 10px 0px", "mj-class": "section"},
        "children": [
            {
                "tagName": "mj-column",
                "attributes": {"width": "100%", "vertical-align": "top"},
                "children": [
                    {
                        "tagName": "mj-divider",
                        "uid": new_uid(),
                        "attributes": {
                            "border-color": "#000000",
                            "border-style": "solid",
                            "border-width": "1px",
                            "padding-top": 14,
                            "padding-right": None,
                            "padding": "14px 0px",
                            "padding-bottom": None,
                            "padding-left": None,
                            "containerWidth": 600,
                        },
                    },
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "15px 15px 15px 15px",
                            "line-height": 1.5,
                            "containerWidth": 600,
                        },
                        "content": (
                            "<p>最後までお読みいただきありがとうございます。</p>\n"
                            "<p>商品のご感想・ご意見などありましたら、ぜひお問い合わせフォームやメール、"
                            "SNSを通して皆様のお声をお聞かせください。<br>"
                            "皆様からの声が何よりの励みになります。<br>"
                            'お問い合わせフォーム： <a href="https://cart6.shopserve.jp/8katte.yu/FORM/contact.cgi" '
                            'target="_blank" rel="noopener">こちら</a><br>'
                            'メールアドレス： <a href="mailto:info@8katte.com" target="_blank" '
                            'rel="noopener">info@8katte.com</a><br>'
                            '<span style="font-size: 10px;">（※お名前やご注文番号も一緒に記載くださいますようお願いいたします。）</span></p>\n'
                            "<p><br><!-- P--></p>"
                        ),
                    },
                    {
                        "tagName": "mj-image",
                        "uid": new_uid(),
                        "attributes": {
                            "alt": "",
                            "containerWidth": 600,
                            "href": "",
                            "padding": "0px 0px 0px 0px",
                            "src": "https://d2q69ad2uaogi7.cloudfront.net/plugin-assets/29318/9ee54d0cfc0fa7849b65924b263ec367bfbeb6726c97767fb857cd61f586ae4a/logo.png",
                            "fluid-on-mobile": "false",
                            "width": "280",
                        },
                    },
                    {
                        "tagName": "mj-social",
                        "uid": new_uid(),
                        "attributes": {
                            "padding": "10px 10px 10px 10px",
                            "icon-size": "35px",
                            "align": "center",
                            "icon-padding": "8px",
                            "text-mode": "false",
                            "containerWidth": 600,
                        },
                        "children": [
                            {
                                "tagName": "mj-social-element",
                                "attributes": {
                                    "src": "https://s3-eu-west-1.amazonaws.com/ecomail-assets/editor/social-icos/ikony-black/simpleblack/facebook.png",
                                    "name": "facebook-noshare",
                                    "alt": "Facebook",
                                    "href": "https://www.facebook.com/8katte.shop",
                                    "background-color": "transparent",
                                    "show": True,
                                },
                            },
                            {
                                "tagName": "mj-social-element",
                                "attributes": {
                                    "src": "https://s3-eu-west-1.amazonaws.com/ecomail-assets/editor/social-icos/ikony-black/simpleblack/instagram.png",
                                    "name": "instagram",
                                    "alt": "Instagram",
                                    "href": "https://www.instagram.com/8katte/",
                                    "background-color": "transparent",
                                    "show": True,
                                },
                            },
                            {
                                "tagName": "mj-social-element",
                                "attributes": {
                                    "src": "https://s3-eu-west-1.amazonaws.com/ecomail-assets/editor/social-icos/ikony-black/simpleblack/x.png",
                                    "name": "x-noshare",
                                    "alt": "X",
                                    "href": "https://twitter.com/8katte_shop",
                                    "background-color": "transparent",
                                    "show": True,
                                },
                            },
                        ],
                        "style": "ikony-black/simpleblack",
                    },
                ],
                "uid": new_uid(),
            }
        ],
        "layout": 1,
        "backgroundColor": "",
        "backgroundImage": "",
        "paddingTop": 0,
        "paddingBottom": 0,
        "paddingLeft": 0,
        "paddingRight": 0,
        "uid": new_uid(),
    }


def footer_section():
    return {
        "tagName": "mj-section",
        "attributes": {"full-width": "full-width", "padding": "10px 0px 10px 0px", "mj-class": "section"},
        "children": [
            {
                "tagName": "mj-column",
                "attributes": {"width": "100%", "vertical-align": "top"},
                "children": [
                    {
                        "tagName": "mj-divider",
                        "uid": new_uid(),
                        "attributes": {
                            "border-color": "#000000",
                            "border-style": "solid",
                            "border-width": "1px",
                            "padding-top": 15,
                            "padding-right": None,
                            "padding": "15px 0px",
                            "padding-bottom": None,
                            "padding-left": None,
                            "containerWidth": 600,
                        },
                    },
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "5px 5px 5px 5px",
                            "line-height": 1.5,
                            "containerWidth": 600,
                        },
                        "content": (
                            '<p style="text-align: center;">'
                            '<a href="https://cart6.shopserve.jp/8katte.yu/FORM/contact.cgi" '
                            'target="_blank" rel="noopener">お問い合わせ</a> / '
                            '<a href="https://8katte.com/SHOP/mailmag.html" target="_blank" '
                            'rel="noopener">メルマガ停止</a><br><!-- P--></p>'
                        ),
                    },
                    {
                        "tagName": "mj-divider",
                        "uid": new_uid(),
                        "attributes": {
                            "border-color": "#000000",
                            "border-style": "solid",
                            "border-width": "1px",
                            "padding-top": 15,
                            "padding-right": None,
                            "padding": "15px 0px",
                            "padding-bottom": None,
                            "padding-left": None,
                            "containerWidth": 600,
                        },
                    },
                    {
                        "tagName": "mj-text",
                        "uid": new_uid(),
                        "attributes": {
                            "align": "left",
                            "padding": "15px 15px 15px 15px",
                            "line-height": 1.5,
                            "containerWidth": 600,
                        },
                        "content": (
                            '<p style="text-align: center;">このメールはハチカッテのメンバーに登録していただいている'
                            "お客様に配信しています。<br>"
                            "発行：株式会社ヤツガタケシゴトニン<br>"
                            "(c) 8katte<br><br><!-- P--></p>"
                        ),
                    },
                    {
                        "tagName": "mj-raw",
                        "uid": new_uid(),
                        "content": "<tr>\n\t<td>\n\t\t\n\t</td>\n</tr>",
                        "attributes": {"containerWidth": 600},
                    },
                ],
                "uid": new_uid(),
            }
        ],
        "layout": 1,
        "backgroundColor": "",
        "backgroundImage": "",
        "paddingTop": 0,
        "paddingBottom": 0,
        "paddingLeft": 0,
        "paddingRight": 0,
        "uid": new_uid(),
    }


def build_json(newsletter_date: str, products: list, banners: list) -> str:
    tmpl = copy.deepcopy(TOP_LEVEL_TEMPLATE)
    children = [header_section(newsletter_date), points_section()]
    for p in products:
        children.append(product_section(p["title"], p["image_url"], p["body"], p["button_url"]))
    children.append(thanks_section())
    children.append(banner_section(banners))
    children.append(footer_section())
    tmpl["children"][0]["children"] = children
    return json.dumps(tmpl, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# テキスト出力
# ---------------------------------------------------------------------------

TXT_HEADER = """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ハチカッテをご利用いただきまして、誠にありがとうございます。
このメールは、当店をご利用いただいたお客様だけに、お送りさせて
いただいております。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
メールの配信停止・登録情報の変更はこちらから
http://8katte.com/SHOP/mailmag.html
ハチカッテ会員名 ： {{NAM_SEI}} {{NAM_MEI}} 様
会員様のログインＩＤ ： {{MEM_ID}}
お手持ちのポイントの残高 ： {{HOLD_PNT}}ポイント
お手持ちのポイントの有効期限 ： {{LOST_YMD}}

"""

TXT_FOOTER = """

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
◇◆◇◆◇◆◇　8katte[ハチカッテ]-八ヶ岳の通販セレクトショップ-　◇◆◇◆◇◆◇
　発行者・運営会社 ： 株式会社ヤツガタケシゴトニン
　TEL ： 0266-74-2299
　営業時間 ： 11:00～18:00　7月、8月は9：00～18：00 定休日：土日祝
　（ご注文は24時間いつでも承っております。）
 - Facebook
https://www.facebook.com/yatsugatake8katte/
 - お問い合わせフォームはこちら
https://cart6.shopserve.jp/8katte.yu/FORM/contact.cgi
 - メルマガ登録・解除はこちら
http://8katte.com/SHOP/mailmag.html
 - ※パスワードをお忘れの方、パスワードのご変更はこちら
https://cart6.shopserve.jp/8katte.yu/forget.php
 - ※マイページのログイン、登録情報の変更はこちら
https://cart6.shopserve.jp/8katte.yu/login.php
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

TITLE_BAR = "-----------・-----------・----------------------・-----------"


def compose_text(products: list, banners: list) -> str:
    parts = []
    for i, p in enumerate(products):
        parts.append(TITLE_BAR)
        parts.append(p["title"])
        parts.append(TITLE_BAR)
        parts.append("")
        parts.append(p["body"].strip())
        parts.append("")
        parts.append("▼ご購入はこちら▼")
        parts.append(p["button_url"])
        parts.append("")
    parts.append(TITLE_BAR)
    parts.append("おすすめ情報")
    parts.append(TITLE_BAR)
    for b in banners:
        parts.append(b["link_url"])
    body_txt = "\n".join(parts).rstrip("\n")
    return TXT_HEADER + body_txt + TXT_FOOTER


def build_utm_url(base_url: str, campaign_date: str) -> str:
    if not base_url:
        return base_url
    utm = f"utm_source=newsletter&utm_medium=email&utm_campaign={campaign_date}&mdkey={{{{MDKEY}}}}"
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}{utm}"


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.title("ハチカッテ ニュースレター作成ツール")
st.caption("配信日・商品URL・アピールしたい方向性を入れるだけで、JSONとテキスト本文を自動生成します。")

with st.sidebar:
    st.subheader("設定")
    default_key = ""
    try:
        default_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        default_key = ""
    api_key = st.text_input(
        "Anthropic APIキー（自動生成に使用）",
        value=default_key,
        type="password",
        help="未入力の場合は自動生成せず、商品ページの情報をそのまま仮の本文として使用します。",
    )

if "banners" not in st.session_state:
    st.session_state.banners = load_banner_defaults()
if "products" not in st.session_state:
    st.session_state.products = [
        {"title": "", "body": "", "image_url": "", "button_url": ""} for _ in range(3)
    ]

col_a, col_b = st.columns(2)
with col_a:
    delivery_date = st.text_input("配信日（例: 2026/07/04）", value="2026/07/04")
campaign_date = re.sub(r"\D", "", delivery_date)
with col_b:
    st.text_input(
        "キャンペーンID（自動生成・編集不要）",
        value=f"?utm_source=newsletter&utm_medium=email&utm_campaign={campaign_date}&mdkey={{{{MDKEY}}}}",
        disabled=True,
    )

st.divider()
st.subheader("紹介したい商品（最大3つ）")

product_inputs = []
for i in range(3):
    with st.container(border=True):
        st.markdown(f"**商品 {i + 1}**")
        c1, c2 = st.columns(2)
        with c1:
            url = st.text_input("商品URL", key=f"purl_{i}")
        with c2:
            direction = st.text_input("アピールしたい方向性", key=f"pdir_{i}")
        product_inputs.append({"url": url, "direction": direction})

st.divider()
st.subheader("レコメンドバナー（前回の内容を引き継ぎます）")

banner_inputs = []
for i in range(2):
    with st.container(border=True):
        st.markdown(f"**バナー {i + 1}**")
        c1, c2 = st.columns(2)
        with c1:
            link_url = st.text_input(
                "リンクURL", value=st.session_state.banners[i]["link_url"], key=f"blink_{i}"
            )
        with c2:
            image_url = st.text_input(
                "画像URL", value=st.session_state.banners[i]["image_url"], key=f"bimg_{i}"
            )
        banner_inputs.append({"link_url": link_url, "image_url": image_url})

if st.button("この内容を次回のデフォルトとして保存"):
    save_banner_defaults(banner_inputs)
    st.session_state.banners = banner_inputs
    st.success("バナーの内容を保存しました。次回起動時から引き継がれます。")

st.divider()

if st.button("商品情報を取得してタイトル・本文を作成", type="primary"):
    results = []
    for i, item in enumerate(product_inputs):
        if not item["url"].strip():
            continue
        with st.spinner(f"商品{i + 1}の情報を取得中..."):
            info = fetch_product_info(item["url"])
            if api_key:
                copy_result = generate_copy_with_claude(info, item["direction"], item["url"], api_key)
                if not copy_result.get("ok"):
                    st.warning(f"商品{i + 1}: 自動生成に失敗したため仮の内容を使用します（{copy_result.get('error', '')}）")
                    copy_result = fallback_copy(info, item["direction"])
            else:
                copy_result = fallback_copy(info, item["direction"])

            results.append(
                {
                    "title": copy_result.get("title", ""),
                    "body": copy_result.get("body", ""),
                    "image_url": info.get("image", ""),
                    "button_url": build_utm_url(item["url"], campaign_date),
                }
            )
    st.session_state.products = results
    st.session_state.drafted = True

if st.session_state.get("drafted"):
    st.subheader("生成された内容（必要に応じて編集してください）")
    edited_products = []
    for i, p in enumerate(st.session_state.products):
        with st.container(border=True):
            st.markdown(f"**商品 {i + 1}（編集可）**")
            title = st.text_input("タイトル", value=p["title"], key=f"et_{i}")
            image_url = st.text_input("画像URL", value=p["image_url"], key=f"ei_{i}")
            body = st.text_area("本文", value=p["body"], height=200, key=f"eb_{i}")
            button_url = st.text_input("ボタンURL", value=p["button_url"], key=f"eu_{i}")
            edited_products.append({"title": title, "image_url": image_url, "body": body, "button_url": button_url})

    if st.button("JSONとテキストを生成する", type="primary"):
        final_banners = banner_inputs
        json_output = build_json(delivery_date, edited_products, final_banners)
        text_output = compose_text(edited_products, final_banners)
        st.session_state["json_output"] = json_output
        st.session_state["text_output"] = text_output

if "json_output" in st.session_state:
    st.divider()
    tab1, tab2 = st.tabs(["テキストプレビュー", "JSONプレビュー"])
    with tab1:
        st.text_area("テキスト出力", st.session_state["text_output"], height=400)
        st.download_button(
            "output.txt をダウンロード",
            data=st.session_state["text_output"],
            file_name="output.txt",
            mime="text/plain",
        )
    with tab2:
        st.text_area("JSON出力", st.session_state["json_output"], height=400)
        st.download_button(
            "output.json をダウンロード",
            data=st.session_state["json_output"],
            file_name="output.json",
            mime="application/json",
        )
