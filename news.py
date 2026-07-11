import streamlit as st
import feedparser
import urllib.request  # 引入 Python 內建的網路請求套件，用來偽裝瀏覽器
from gtts import gTTS
import os
import base64

# 👇 加上這三行，強制關閉 Python 的 SSL 憑證驗證
import ssl

# 引入 Python 內建的記憶體串流套件（請加在程式碼上方或函式內皆可）
from io import BytesIO

import requests  # 記得在程式碼最上方確認有沒有 import requests，沒有的話請補上
import csv  # 確保有引入 Python 內建的 CSV 套件

ssl._create_default_https_context = ssl._create_unverified_context

# --- 1. 頁面基礎設定 (設定手機版外觀) ---
st.set_page_config(
    page_title="10分鐘多語時事學習",
    page_icon="🌐",
    layout="centered",  # 手機版最適合居中佈局
    initial_sidebar_state="collapsed"
)

# 自訂 CSS 讓手機版介面更美觀、字體更適合閱讀
st.markdown("""
    <style>
    .big-title { font-size:24px !important; font-weight: bold; color: #1E3A8A; margin-bottom: 10px; }
    .news-box { background-color: #F3F4F6; padding: 15px; border-radius: 10px; margin-bottom: 15px; }
    .vocab-card { border-left: 5px solid #10B981; background-color: #ECFDF5; padding: 10px; margin: 8px 0; border-radius: 0 10px 10px 0; }
    .grammar-box { border-left: 5px solid #3B82F6; background-color: #EFF6FF; padding: 10px; margin: 8px 0; border-radius: 0 10px 10px 0; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 各國語言新聞源定時抓取 (更新為目前最穩定的 RSS 網址) ---
NEWS_FEEDS = {
    "英文 (English)": {
        "url": "https://feeds.bbci.co.uk/news/world/rss.xml",  # 🎯 換回 BBC 國際新聞官方 RSS
        "lang_code": "en"
    }
}

def save_word_to_csv(word, pos, detail, example, news_title):
    file_exists = os.path.isfile("my_vocab.csv")

    # 讀取現有單字，避免重複儲存
    existing_words = set()
    if file_exists:
        with open("my_vocab.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳過標頭
            for row in reader:
                if row: existing_words.add(row[0].lower())

    # 如果單字還沒被存過，才寫入
    if word.lower() not in existing_words:
        with open("my_vocab.csv", "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                # 🎯 欄位最右邊多增加一個 "News Context" (時事參考例句)
                writer.writerow(["Word", "Part of Speech", "Definition", "Dictionary Example", "News Context"])
            # 🎯 寫入資料時，將當下的新聞標題一併寫入最後一欄
            writer.writerow([word, pos, detail, example, news_title])
        return True
    return False


def exclude_word_to_csv(word):
    file_exists = os.path.isfile("excluded_vocab.csv")

    # 讀取現有黑名單，避免重複寫入
    excluded_words = set()
    if file_exists:
        with open("excluded_vocab.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader, None)  # 跳過標頭
            for row in reader:
                if row: excluded_words.add(row[0].lower())

    # 若不在黑名單內才寫入
    if word.lower() not in excluded_words:
        with open("excluded_vocab.csv", "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Excluded Word"])  # 建立標頭
            writer.writerow([word])
        return True
    return False

def remove_word_from_csv(word_to_remove):
    if not os.path.isfile("my_vocab.csv"):
        return False

    updated_rows = []
    header = None
    removed = False

    # 1. 讀取現有資料，並跳過要刪除的單字
    with open("my_vocab.csv", "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # 抓取標頭
        for row in reader:
            if row:
                # 比較單字（忽略大小寫與前後空白）
                if row[0].strip().lower() == word_to_remove.strip().lower():
                    removed = True
                    continue  # 跳過它，不加入更新清單
                updated_rows.append(row)

    # 2. 如果有成功移除，將剩餘資料重新寫回檔案
    if removed:
        with open("my_vocab.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            writer.writerows(updated_rows)
        return True

    return False

# 模擬 AI 生成教材的函式streamlit run news.py
def real_dict_generator(title, lang_code):
    fallback_data = {
        "vocab": [{"word": "Review", "pos": "v.", "detail": "To study material studied before.",
                   "example": "Review the lessons today."}],
        "grammar": "【每日溫馨提醒】嘗試在上方的新聞摘要中，找出值得學習的核心單字，並觀察它是如何被運用在真實的國際報導句子中的。"
    }

    if lang_code != "en":
        return fallback_data

    try:
        # 1. 建立「過濾總清單」集合
        filter_words = set()

        # 讀取已收藏清單
        if os.path.isfile("my_vocab.csv"):
            with open("my_vocab.csv", "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row: filter_words.add(row[0].strip().lower())

        # 🎯 讀取已排除黑名單
        if os.path.isfile("excluded_vocab.csv"):
            with open("excluded_vocab.csv", "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row: filter_words.add(row[0].strip().lower())

        # 2. 從新聞標題中拆解出候選單字
        words_in_title = [w.strip(".,;:\"'()?!") for w in title.split()]
        candidate_words = [w for w in words_in_title if len(w) >= 6 and w.istitle() == False]

        if not candidate_words:
            candidate_words = [w for w in words_in_title if len(w) >= 4]

        unique_candidates = list(dict.fromkeys(candidate_words))

        # 🎯 同時過濾掉「已收藏」與「已排除」的單字
        fresh_words = [w for w in unique_candidates if w.lower() not in filter_words]

        if not fresh_words:
            return {
                "vocab": [],
                "grammar": "🎉 太棒了！這篇新聞標題中的核心單字你不是已經收藏，就是已經設定排除了！"
            }

        target_words = fresh_words[:3]

        vocab_list = []
        for word in target_words:
            api_url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
            response = requests.get(api_url, timeout=3)

            if response.status_code == 200:
                data = response.json()[0]
                meanings = data.get("meanings", [{}])[0]
                pos = meanings.get("partOfSpeech", "n.")
                definitions = meanings.get("definitions", [{}])[0]

                raw_definition = definitions.get("definition", "No definition found.")
                raw_example = definitions.get("example", f"Study the word '{word}' in the text above.")

                vocab_list.append({
                    "word": word.capitalize(),
                    "pos": f"{pos}.",
                    "detail": raw_definition,
                    "example": raw_example
                })

        if vocab_list:
            return {"vocab": vocab_list,
                    "grammar": "【精選核心句型】\n嘗試在上方的新聞摘要中，找出剛剛查到的核心單字，並觀察它是如何被運用在真實的國際報導句子中的。"}
        else:
            return fallback_data

    except Exception:
        return fallback_data

# TTS 語音發音產生器 (升級版：免除硬碟讀寫，防範 FileNotFoundError)
def speak_text(text, lang_code):
    try:
        # 1. 建立一個虛擬的記憶體檔案空間
        mp3_fp = BytesIO()

        # 2. 讓 gTTS 直接把聲音檔案寫進記憶體，而不是硬碟
        tts = gTTS(text=text, lang=lang_code, slow=False)
        tts.write_to_fp(mp3_fp)

        # 3. 將指標移回記憶體檔案的最開頭，並讀取二進位資料
        mp3_fp.seek(0)
        data = mp3_fp.read()
        return data
    except Exception as e:
        # 萬一真的因為網路或字元出錯，返回一個空的 bytes，不讓程式崩潰
        st.error(f" gTTS 語音轉換失敗，請稍後再試。錯誤原因: {e}")
        return b""

# 專門幫單字卡生成內嵌音訊的函式
def get_word_audio_base64(word, lang_code):
    try:
        tts = gTTS(text=word, lang=lang_code, slow=False)
        tts.save("word_temp.mp3")
        with open("word_temp.mp3", "rb") as f:
            data = f.read()
        os.remove("word_temp.mp3")
        b64 = base64.b64encode(data).decode()
        return f"data:audio/mp3;base64,{b64}"
    except Exception:
        return ""


# --- 3. App 前端介面 UI 設計 ---
st.markdown("""
    <!-- 1. 引入 Font Awesome 圖標庫，確保手機、電腦都能顯現 icon -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">

    <!-- 2. 主標題 HTML -->
    <div class="big-title">
        <i class="fas fa-globe-americas"></i> 10 mins BBC News
    </div>

    <!-- 3. 全局自訂介面樣式表 (包含你調整的 #606c38 質感墨綠色) -->
    <style>
    .big-title { 
        font-size:  32px !important; 
        font-weight: bold; 
        color: #f07167; 
        margin-bottom: 10px; 
    }
    .news-box { 
        background-color: #F3F4F6; 
        padding: 15px; 
        border-radius: 10px; 
        margin-bottom: 15px; 
        color: #1F2937 !important; 
    }
    .vocab-card { 
        border-left: 5px solid #10B981; 
        background-color: #ECFDF5; 
        padding: 10px; 
        margin: 8px 0; 
        border-radius: 0 10px 10px 0; 
        color: #065F46 !important; 
    }
    .vocab-card small { 
        color: #047857 !important; 
    }
    </style>
""", unsafe_allow_html=True)
st.caption("每天挑選一篇BBC國際時事練習聽力、單字．")

# 步驟一：選擇今天的目標語言
selected_lang = st.selectbox("🎯 請選擇今日挑戰語言：", list(NEWS_FEEDS.keys()))
feed_info = NEWS_FEEDS[selected_lang]

# 步驟二：抓取該語言的最新時事
with st.spinner("正在網羅最新時事..."):
    try:
        req = urllib.request.Request(
            feed_info["url"],
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req) as response:
            html_content = response.read()

        feed = feedparser.parse(html_content)
        articles = feed.entries[:5]
    except Exception as e:
        st.warning(f"除錯訊息（非報錯）：{e}")
        articles = []

if not articles:
    st.error("⚠️ 暫時無法取得該語言的新聞，請檢查網路連線，或試著切換其他語言看看！")
else:
    article_titles = [a.title for a in articles]
    chosen_title = st.selectbox("📰 選擇感興趣的新聞標題：", article_titles)
    chosen_article = next((a for a in articles if a.title == chosen_title), None)

    if chosen_article:
        # --- 4. 呈現教材內容 ---
        st.write("---")

        # 1. 處理摘要與原文連結（這兩個速度極快，優先顯示）
        summary_text = ""
        if hasattr(chosen_article, 'summary') and chosen_article.summary:
            summary_text = chosen_article.summary
        elif hasattr(chosen_article, 'description') and chosen_article.description:
            summary_text = chosen_article.description
        else:
            summary_text = "無新聞摘要，請點擊下方連結閱讀原文。"

        article_url = getattr(chosen_article, 'link', '#')

        st.markdown(f"""
                    <div class="news-box">
                        <strong>【新聞標題】</strong><br>{chosen_article.title}<br><br>
                        <strong>【新聞摘要】</strong><br>{summary_text[:400]}...
                    </div>
                    """, unsafe_allow_html=True)

        # 4. 🦥 把最花時間的「長篇新聞語音朗讀」移到最底下，讓它最後轉圈載入
        with st.spinner("🔊 正在背景為您準備新聞全文朗讀語音..."):
            audio_data = speak_text(chosen_article.title + ". " + summary_text[:200], feed_info["lang_code"])

        if audio_data:
            st.audio(audio_data, format="audio/mp3")

        st.link_button("🔗 閱讀新聞原文", article_url, use_container_width=True)

        # 2. 優先載入開源字典與渲染「核心單字卡」（直接先跳出來給使用者看！）
        ai_material = real_dict_generator(chosen_article.title, feed_info["lang_code"])

        # 顯示關鍵字卡
        # 🎯 偵測 HTML 內部按鈕傳出來的跳轉指令 (Query Parameters)
        query_params = st.query_params
        if "action" in query_params and "word" in query_params:
            action = query_params["action"]
            target_w = query_params["word"]

            # 找到對應單字的完整資料
            v_data = next((vocab for vocab in ai_material["vocab"] if vocab["word"].lower() == target_w.lower()), None)

            if v_data:
                if action == "save":
                    saved = save_word_to_csv(v_data['word'], v_data['pos'], v_data['detail'], v_data['example'],
                                             chosen_title)
                    if saved: st.toast(f"✅ 已將 {v_data['word']} 加到生字本！")
                elif action == "exclude":
                    excluded = exclude_word_to_csv(v_data['word'])
                    if excluded: st.toast(f"🗑️ 已將 {v_data['word']} 永久排除")

            # 動作執行完畢後，立刻把網址參數清空並重整，讓單字利落消失
            st.query_params.clear()
            st.rerun()

        if not ai_material["vocab"]:
            st.info("✨ 這篇新聞標題的關鍵單字你都已經收藏或排除了！")
        else:
            import streamlit.components.v1 as components

            for v in ai_material["vocab"]:
                audio_base64 = get_word_audio_base64(v['word'], feed_info["lang_code"])
                unique_id = v['word'].replace(" ", "_")

                # 🎯 步驟 1：動態估算合適的字卡高度 (依據總字數長度)
                # 基礎高度 75px + (內容總長度 / 估算每行字數) * 每行行高
                total_text_len = len(v['word']) + len(v['detail']) + len(v['example'])

                if total_text_len < 80:
                    dynamic_height = 95
                elif total_text_len < 150:
                    dynamic_height = 115
                else:
                    dynamic_height = 140

                # 🎯 步驟 2：極致穩定的自適應 HTML / CSS
                card_html = f"""
                                    <style>
                                        * {{
                                            box-sizing: border-box; /* 確保 padding 不會撐破高度 */
                                            margin: 0;
                                            padding: 0;
                                        }}
                                        body {{
                                            background-color: transparent;
                                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                                            overflow: hidden; /* 徹底杜絕卡片內部捲軸 */
                                        }}
                                        .vocab-card {{ 
                                            border-left: 5px solid #10B981; 
                                            background-color: #ECFDF5; 
                                            padding: 10px 12px; 
                                            border-radius: 0 10px 10px 0; 
                                            color: #065F46;
                                            display: flex; 
                                            flex-direction: column; 
                                            gap: 4px;
                                            width: 100%;
                                            min-height: 75px;
                                        }}
                                        .first-row {{
                                            display: flex;
                                            justify-content: space-between; 
                                            align-items: center;
                                            width: 100%;
                                        }}
                                        .word-title {{
                                            font-size: 17px;
                                            font-weight: bold;
                                        }}
                                        .word-pos {{
                                            font-size: 13px;
                                            font-style: italic;
                                            color: #047857;
                                            margin-left: 4px;
                                        }}
                                        .btn-group {{
                                            display: flex;
                                            flex-direction: row;
                                            gap: 6px;
                                            align-items: center;
                                        }}
                                        .btn-action {{
                                            background-color: #10B981; 
                                            color: white; 
                                            border: none; 
                                            width: 30px; /* 稍微縮小按鈕，更穩固空間 */
                                            height: 30px;
                                            border-radius: 50%; 
                                            font-size: 13px; 
                                            cursor: pointer;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                                            text-decoration: none;
                                            -webkit-appearance: none;
                                        }}
                                        .btn-action:active {{ background-color: #059669; }}
                                        .btn-save {{ background-color: #f59e0b; }}       
                                        .btn-save:active {{ background-color: #d97706; }}
                                        .btn-exclude {{ background-color: #ef4444; }}    
                                        .btn-exclude:active {{ background-color: #dc2626; }}

                                        .details-section {{
                                            font-size: 13.5px;
                                            line-height: 1.35;
                                            word-wrap: break-word; /* 避免過長英文單字爆開 */
                                        }}
                                        .example-text {{
                                            color: #047857; 
                                            font-size: 11.5px; 
                                            display: block; 
                                            margin-top: 2px;
                                        }}
                                    </style>

                                    <div class="vocab-card">
                                        <!-- 第一行：單字與詞性 + 三顆按鈕 -->
                                        <div class="first-row">
                                            <div>
                                                <span class="word-title">{v['word']}</span>
                                                <span class="word-pos">({v['pos']})</span>
                                            </div>
                                            <div class="btn-group">
                                                <audio src="{audio_base64}" id="audio_{unique_id}"></audio>
                                                <button class="btn-action" onclick="document.getElementById('audio_{unique_id}').play()">🔊</button>
                                                <a class="btn-action btn-save" href="?action=save&word={v['word'].lower()}" target="_parent">⭐</a>
                                                <a class="btn-action btn-exclude" href="?action=exclude&word={v['word'].lower()}" target="_parent">🚫</a>
                                            </div>
                                        </div>

                                        <!-- 第二行開始：英文說明與例句 -->
                                        <div class="details-section">
                                            <div>{v['detail']}</div>
                                            <span class="example-text">📝 {v['example']}</span>
                                        </div>
                                    </div>
                                    """

                # 🎯 步驟 3：餵入動態計算的高度，徹底解決高度不穩定與卡片跳動問題
                components.html(card_html, height=dynamic_height, scrolling=False)

        st.write("---")

        # ==================== 5. 側邊欄：專屬生字本展示與下載 ====================
        with st.sidebar:
            st.header("⭐ 收藏單字")

            if os.path.isfile("my_vocab.csv"):
                # 為了避免在讀取檔案時同時寫入造成衝突，改用 csv.reader 讀進記憶體處理
                rows = []
                with open("my_vocab.csv", "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    rows = [r for r in reader if r]

                if not rows:
                    st.info("目前還沒有收藏任何單字喔，快去點選單字底下的 ⭐ 收藏吧！")
                else:
                    st.write(f"目前已收藏 {len(rows)} 個單字：")

                    # 依序渲染每個已收藏的單字
                    for idx, w_info in enumerate(rows):
                        if len(w_info) >= 5:
                            # 建立一個水平並排的區塊，讓排版更精緻
                            col1, col2 = st.columns([4, 1])

                            with col1:
                                st.markdown(
                                    f"**{w_info[0]}** ({w_info[1]})\n- *Def:* {w_info[2]}\n- *💡 News:* {w_info[4]}")

                            with col2:
                                # 使用唯一的 key (利用索引值 idx) 避免 Streamlit 元件衝突
                                if st.button("❌", key=f"del_{idx}", help=f"將 {w_info[0]} 從生字本移除"):
                                    if remove_word_from_csv(w_info[0]):
                                        st.toast(f"🗑️ 已將 {w_info[0]} 移出生字本")
                                        st.rerun()  # 立即重整頁面，更新畫面清單

                            st.write("---")

                # 讀取整份檔案供下載使用（只有在檔案有內容時才顯示下載鈕）
                if rows:
                    with open("my_vocab.csv", "r", encoding="utf-8-sig") as f:
                        csv_data = f.read()
                    st.download_button(
                        label="📥 下載生字本 (CSV)",
                        data=csv_data,
                        file_name="my_vocab_list.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
            else:
                st.info("目前還沒有收藏任何單字喔，快去點選單字底下的 ⭐ 收藏吧！")