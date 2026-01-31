import streamlit as st
import requests
import re
import time
from datetime import datetime
import pandas as pd

# ===================== 基础配置（手机适配核心）=====================
st.set_page_config(
    page_title="基金实时估值-手机版",
    page_icon="📈",
    layout="centered",  # 手机端居中布局
    initial_sidebar_state="collapsed"  # 手机端侧边栏默认折叠，滑出即可
)
# 自定义CSS（手机端放大按钮/字体，优化触控）
st.markdown("""
<style>
.stButton>button {width: 100%; font-size: 16px; padding: 10px 0;}
.stTextInput, .stSelectbox, .stNumberInput {font-size: 16px;}
.stMetric {padding: 10px;}
h1, h2, h3 {text-align: center;}
.stSidebar {width: 80% !important;}
</style>
""", unsafe_allow_html=True)

st.title("📈 基金实时估值工具（手机版）")
st.caption("💡 支持自定义添加基金 | 估值仅作参考，实际净值以基金公司公布为准")

# ===================== 全局状态（持久化保存，刷新不丢失）=====================
# 初始内置基金（可删除/修改）
INIT_FUNDS = {
    "161725": {"name": "招商中证白酒指数(LOF)A",
               "holdings": {"600519": {"name": "贵州茅台", "weight": 0.185},
                            "000858": {"name": "五粮液", "weight": 0.152},
                            "000568": {"name": "泸州老窖", "weight": 0.128},
                            "002304": {"name": "洋河股份", "weight": 0.102},
                            "000799": {"name": "酒鬼酒", "weight": 0.085}}},
    "001593": {"name": "天弘中证食品饮料ETF联接A",
               "holdings": {"600519": {"name": "贵州茅台", "weight": 0.213},
                            "000858": {"name": "五粮液", "weight": 0.167},
                            "000568": {"name": "泸州老窖", "weight": 0.105},
                            "601899": {"name": "紫金矿业", "weight": 0.072},
                            "002594": {"name": "比亚迪", "weight": 0.068}}},
    "000311": {"name": "景顺长城沪深300指数增强A",
               "holdings": {"600519": {"name": "贵州茅台", "weight": 0.082},
                            "601318": {"name": "中国平安", "weight": 0.075},
                            "000333": {"name": "美的集团", "weight": 0.068},
                            "601689": {"name": "拓普集团", "weight": 0.059},
                            "601012": {"name": "隆基绿能", "weight": 0.053}}},
    "001632": {"name": "天弘中证医药100ETF联接A",
               "holdings": {"600276": {"name": "恒瑞医药", "weight": 0.125},
                            "600518": {"name": "康美药业", "weight": 0.108},
                            "002007": {"name": "华兰生物", "weight": 0.096},
                            "300760": {"name": "迈瑞医疗", "weight": 0.089},
                            "603259": {"name": "药明康德", "weight": 0.078}}}
}

# 初始化全局状态（基金库/历史/自选/预警/缓存）
if "fund_db" not in st.session_state:
    st.session_state.fund_db = INIT_FUNDS  # 核心基金库（可自定义添加）
if "valuation_history" not in st.session_state:
    st.session_state.valuation_history = []  # 估值历史
if "favorites" not in st.session_state:
    st.session_state.favorites = []  # 自选基金
if "warn_up" not in st.session_state:
    st.session_state.warn_up = 1.0  # 上涨预警阈值(%)
if "warn_down" not in st.session_state:
    st.session_state.warn_down = -1.0  # 下跌预警阈值(%)
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}  # 数据缓存（30秒）

# 常量配置
CACHE_EXPIRE = 30  # 缓存过期时间（秒）
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Mobile; Android 14; SM-G9910) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
}

# ===================== 核心工具函数 =====================
# 1. 获取股票实时涨跌幅（带缓存，防频繁请求）
def get_stock_change(stock_code):
    # 检查缓存
    if stock_code in st.session_state.data_cache:
        cache_time, cache_val = st.session_state.data_cache[stock_code]
        if time.time() - cache_time < CACHE_EXPIRE:
            return cache_val
    # 请求接口
    prefix = "sh" if stock_code.startswith("6") else "sz"
    try:
        res = requests.get(f"https://hq.sinajs.cn/list={prefix}{stock_code}", headers=HEADERS, timeout=5)
        change = float(res.text.split(',')[3]) / 100  # 转换为小数
        # 更新缓存
        st.session_state.data_cache[stock_code] = (time.time(), change)
        return change
    except Exception as e:
        st.warning(f"股票{stock_code}数据获取失败，按0计算")
        return 0.0

# 2. 获取基金最新净值（带缓存，失败则手动输入）
def get_fund_net(fund_code):
    # 检查缓存
    if fund_code in st.session_state.data_cache:
        cache_time, cache_val = st.session_state.data_cache[fund_code]
        if time.time() - cache_time < CACHE_EXPIRE:
            return cache_val
    # 请求天天基金网接口
    try:
        res = requests.get(f"https://fund.eastmoney.com/{fund_code}.html", headers=HEADERS, timeout=8)
        # 解析净值
        net_text = re.findall(r'<span class="ui-font-large ui-color-red">(.*?)</span>', res.text)[0]
        net_value = float(net_text)
        # 更新缓存
        st.session_state.data_cache[fund_code] = (time.time(), net_value)
        return net_value
    except Exception as e:
        # 接口失败，弹窗让用户手动输入
        manual_net = st.number_input(f"基金{fund_code}净值获取失败，请手动输入", value=1.0, step=0.0001, key=f"manual_net_{fund_code}")
        return manual_net

# 3. 计算基金实时估值（核心）
def calculate_fund_val(fund_code):
    if fund_code not in st.session_state.fund_db:
        st.error(f"基金{fund_code}未在基金库中，请先添加！")
        return
    # 获取基金基础信息
    fund_info = st.session_state.fund_db[fund_code]
    fund_name = fund_info["name"]
    holdings = fund_info["holdings"]
    # 获取最新净值
    latest_net = get_fund_net(fund_code)
    # 计算加权涨跌幅
    total_change = 0.0
    for stock_code, stock_info in holdings.items():
        stock_change = get_stock_change(stock_code)
        total_change += stock_change * stock_info["weight"]
    # 计算估算净值
    est_net = latest_net * (1 + total_change)
    change_percent = total_change * 100  # 转换为百分比

    # 触发涨跌预警
    if change_percent >= st.session_state.warn_up:
        st.warning(f"📈 上涨预警！当前涨幅{change_percent:.2f}%，达到阈值{st.session_state.warn_up}%")
    if change_percent <= st.session_state.warn_down:
        st.warning(f"📉 下跌预警！当前跌幅{change_percent:.2f}%，达到阈值{st.session_state.warn_down}%")

    # 展示估值结果（手机端双列布局，简洁直观）
    st.subheader(f"{fund_name}（{fund_code}）")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("最新净值", f"{latest_net:.4f}")
    with col2:
        st.metric("估算涨跌幅", f"{change_percent:.2f}%", f"{change_percent:.2f}%", delta_color="inverse")
    st.metric("实时估算净值", f"{est_net:.4f}")

    # 展示重仓股持仓
    st.subheader("📋 重仓股持仓权重")
    holdings_data = []
    for s_code, s_info in holdings.items():
        holdings_data.append({
            "股票代码": s_code,
            "股票名称": s_info["name"],
            "持仓权重": f"{s_info['weight']:.3f}",
            "实时涨跌幅": f"{get_stock_change(s_code)*100:.2f}%"
        })
    holdings_df = pd.DataFrame(holdings_data)
    st.dataframe(holdings_df, index=False, use_container_width=True)

    # 记录估值历史
    st.session_state.valuation_history.append({
        "估值时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "基金代码": fund_code,
        "基金名称": fund_name,
        "最新净值": round(latest_net, 4),
        "估算涨跌幅(%)": round(change_percent, 2),
        "估算净值": round(est_net, 4)
    })
    st.success(f"✅ {fund_name}估值完成，已记录历史！")

# 4. 批量估值计算
def batch_calculate(fund_codes):
    valid_codes = [code.strip() for code in fund_codes if code.strip() in st.session_state.fund_db]
    if not valid_codes:
        st.error("无有效基金代码，请检查！")
        return
    st.subheader(f"📦 批量估值（共{len(valid_codes)}只）")
    for code in valid_codes:
        calculate_fund_val(code)
        st.divider()

# ===================== 功能板块（手机端按顺序展示，滑屏操作）=====================
# 👉 板块1：快速估值（核心，默认展示）
st.divider()
st.header("⚡ 快速估值")
# 选择基金（下拉框，显示所有基金库中的基金）
fund_code_select = st.selectbox(
    "选择要估值的基金",
    options=list(st.session_state.fund_db.keys()),
    format_func=lambda x: f"{x} - {st.session_state.fund_db[x]['name']}",
    key="fund_select"
)
if st.button("📊 开始计算实时估值", key="single_calc"):
    calculate_fund_val(fund_code_select)

# 👉 板块2：自定义添加/删除基金（核心新增）
st.divider()
st.header("📝 基金管理（添加/删除）")
tab1, tab2 = st.tabs(["📥 添加自定义基金", "📤 删除基金"])

# 子板块2-1：添加自定义基金（支持多只重仓股，最少1只）
with tab1:
    st.subheader("添加基金基础信息")
    new_fund_code = st.text_input("基金代码（如161725）", placeholder="输入纯数字基金代码", key="new_fund_code")
    new_fund_name = st.text_input("基金名称", placeholder="如：招商中证白酒指数(LOF)A", key="new_fund_name")
    st.subheader("添加重仓股（最少1只，权重0-1）")
    # 支持添加5只重仓股（手机端足够用，可自行增加）
    stock_datas = []
    for i in range(5):
        col1, col2, col3 = st.columns(3)
        with col1:
            s_code = st.text_input(f"股票代码{i+1}", placeholder="如600519", key=f"s_code_{i}")
        with col2:
            s_name = st.text_input(f"股票名称{i+1}", placeholder="如贵州茅台", key=f"s_name_{i}")
        with col3:
            s_weight = st.number_input(f"持仓权重{i+1}", 0.001, 1.0, 0.1, step=0.001, key=f"s_weight_{i}")
        if s_code and s_name:  # 非空才添加
            stock_datas.append({"code": s_code, "name": s_name, "weight": s_weight})
    # 确认添加基金
    if st.button("✅ 确认添加基金", key="add_fund"):
        if not new_fund_code or not new_fund_name or not stock_datas:
            st.error("基金代码、名称、重仓股（至少1只）不能为空！")
        elif new_fund_code in st.session_state.fund_db:
            st.error(f"基金{new_fund_code}已存在，无需重复添加！")
        else:
            # 构造基金数据
            fund_holdings = {}
            for s in stock_datas:
                fund_holdings[s["code"]] = {"name": s["name"], "weight": s["weight"]}
            st.session_state.fund_db[new_fund_code] = {
                "name": new_fund_name,
                "holdings": fund_holdings
            }
            st.success(f"✅ 基金{new_fund_code} - {new_fund_name}添加成功！")
            # 刷新页面，更新下拉框
            st.rerun()

# 子板块2-2：删除基金（支持删除内置/自定义基金）
with tab2:
    del_fund_code = st.selectbox(
        "选择要删除的基金",
        options=list(st.session_state.fund_db.keys()),
        format_func=lambda x: f"{x} - {st.session_state.fund_db[x]['name']}",
        key="del_fund_select"
    )
    if st.button("❌ 确认删除基金", key="del_fund"):
        del st.session_state.fund_db[del_fund_code]
        # 若删除的是自选基金，同步从自选移除
        if del_fund_code in st.session_state.favorites:
            st.session_state.favorites.remove(del_fund_code)
        st.success(f"✅ 基金{del_fund_code}删除成功！")
        st.rerun()

# 👉 板块3：自选基金（快速收藏，无需反复选择）
st.divider()
st.header("❤️ 自选基金")
col1, col2 = st.columns(2)
with col1:
    if st.button("⭐ 添加当前基金到自选", key="add_fav"):
        if fund_code_select not in st.session_state.favorites:
            st.session_state.favorites.append(fund_code_select)
            st.success(f"✅ {fund_code_select}添加到自选成功！")
        else:
            st.info(f"ℹ️ {fund_code_select}已在自选中！")
with col2:
    if st.button("❌ 清空自选基金", key="clear_fav"):
        st.session_state.favorites = []
        st.success("✅ 自选基金已清空！")
# 展示自选基金并快速估值
if st.session_state.favorites:
    st.subheader("我的自选基金")
    for fav_code in st.session_state.favorites:
        if st.button(f"{fav_code} - {st.session_state.fund_db[fav_code]['name']}", key=f"fav_calc_{fav_code}"):
            calculate_fund_val(fav_code)

# 👉 板块4：批量估值
st.divider()
st.header("📦 批量估值")
batch_codes_input = st.text_input(
    "输入基金代码（英文逗号分隔，如161725,001593）",
    placeholder="多只基金代码用,分开，无需空格",
    key="batch_codes"
)
if st.button("🚀 开始批量估值", key="batch_calc"):
    batch_calculate(batch_codes_input.split(','))

# 👉 板块5：估值历史+导出
st.divider()
st.header("📜 估值历史")
if st.session_state.valuation_history:
    history_df = pd.DataFrame(st.session_state.valuation_history)
    st.dataframe(history_df, index=False, use_container_width=True)
    # 导出Excel（手机端可保存到本地/云盘）
    csv_data = history_df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 导出历史数据到Excel",
        data=csv_data,
        file_name=f"基金估值历史_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv",
        mime="text/csv",
        key="download_history"
    )
    # 清空历史
    if st.button("🗑️ 清空估值历史", key="clear_history"):
        st.session_state.valuation_history = []
        st.success("✅ 估值历史已清空！")
        st.rerun()
else:
    st.info("ℹ️ 暂无估值历史，计算基金后自动记录！")

# 👉 板块6：预警设置（滑到页面底部，按需设置）
st.divider()
st.header("🚨 涨跌预警设置")
col1, col2 = st.columns(2)
with col1:
    new_warn_up = st.number_input("上涨预警阈值(%)", min_value=0.0, step=0.1, value=st.session_state.warn_up, key="new_warn_up")
with col2:
    new_warn_down = st.number_input("下跌预警阈值(%)", max_value=0.0, step=0.1, value=st.session_state.warn_down, key="new_warn_down")
if st.button("✅ 保存预警阈值", key="save_warn"):
    st.session_state.warn_up = new_warn_up
    st.session_state.warn_down = new_warn_down
    st.success(f"✅ 预警阈值保存成功！上涨：{new_warn_up}% | 下跌：{new_warn_down}%")

# 底部提示
st.divider()
st.markdown("""
<center>
© 2025 基金实时估值工具 | 数据来源：新浪财经、天天基金网<br>
⚠️ 请勿频繁点击计算，数据缓存30秒 | 投资有风险，入市需谨慎
</center>
""", unsafe_allow_html=True)