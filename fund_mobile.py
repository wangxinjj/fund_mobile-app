import streamlit as st
import requests
import re
import time
from datetime import datetime
import pandas as pd

# ===================== 基础配置（手机适配核心）=====================
st.set_page_config(
    page_title="基金实时估值-持仓盈亏版",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 自定义CSS（手机端优化：卡片、盈亏颜色、按钮放大）
st.markdown("""
<style>
.stButton>button {width: 100%; font-size: 16px; padding: 10px 0; margin: 5px 0;}
.stTextInput, .stSelectbox, .stNumberInput {font-size: 16px; margin: 5px 0;}
.stMetric {padding: 8px; font-size: 14px;}
h1, h2, h3 {text-align: center; margin: 10px 0;}
.stSidebar {width: 80% !important;}
.fund-card {border: 1px solid #e0e0e0; border-radius: 10px; padding: 10px; margin: 10px 0; background: #f9f9f9;}
.fund-title {font-weight: bold; font-size: 16px; margin-bottom: 8px; text-align: left;}
.red {color: #ff4d4f; font-weight: 500;}
.green {color: #52c41a; font-weight: 500;}
.gray {color: #888;}
.batch-container {overflow-x: auto; padding: 5px 0;}
.profit-card {margin: 5px 0; padding: 8px; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)

st.title("📈 基金实时估值工具（持仓盈亏版）")
st.caption("💡 持仓金额管理 | 当日/累计盈亏计算 | 多基金同屏 | 盈亏历史记录")

# ===================== 全局状态（持久化保存，所有数据刷新不丢）=====================
INIT_FUNDS = {
    "161725": {"name": "招商中证白酒指数(LOF)A",
               "holdings": {"600519": {"name": "贵州茅台", "weight": 0.185},
                            "000858": {"name": "五粮液", "weight": 0.152},
                            "000568": {"name": "泸州老窖", "weight": 0.128},
                            "002304": {"name": "洋河股份", "weight": 0.102},
                            "000799": {"name": "酒鬼酒", "weight": 0.085}},
               "position": {"amount": 0.0, "cost_price": 0.0, "buy_date": datetime.now().strftime("%Y-%m-%d")}},
    "001593": {"name": "天弘中证食品饮料ETF联接A",
               "holdings": {"600519": {"name": "贵州茅台", "weight": 0.213},
                            "000858": {"name": "五粮液", "weight": 0.167},
                            "000568": {"name": "泸州老窖", "weight": 0.105},
                            "601899": {"name": "紫金矿业", "weight": 0.072},
                            "002594": {"name": "比亚迪", "weight": 0.068}},
               "position": {"amount": 0.0, "cost_price": 0.0, "buy_date": datetime.now().strftime("%Y-%m-%d")}},
    "000311": {"name": "景顺长城沪深300指数增强A",
               "holdings": {"600519": {"name": "贵州茅台", "weight": 0.082},
                            "601318": {"name": "中国平安", "weight": 0.075},
                            "000333": {"name": "美的集团", "weight": 0.068},
                            "601689": {"name": "拓普集团", "weight": 0.059},
                            "601012": {"name": "隆基绿能", "weight": 0.053}},
               "position": {"amount": 0.0, "cost_price": 0.0, "buy_date": datetime.now().strftime("%Y-%m-%d")}}
}

# 初始化全局状态（新增position持仓信息、profit_history盈亏历史）
if "fund_db" not in st.session_state:
    st.session_state.fund_db = INIT_FUNDS
if "valuation_history" not in st.session_state:
    st.session_state.valuation_history = []
if "profit_history" not in st.session_state:  # 新增：盈亏历史记录
    st.session_state.profit_history = []
if "favorites" not in st.session_state:
    st.session_state.favorites = list(INIT_FUNDS.keys())
if "warn_up" not in st.session_state:
    st.session_state.warn_up = 1.0
if "warn_down" not in st.session_state:
    st.session_state.warn_down = -1.0
if "data_cache" not in st.session_state:
    st.session_state.data_cache = {}
if "current_fund_code" not in st.session_state:
    st.session_state.current_fund_code = list(INIT_FUNDS.keys())[0]

# 常量配置
CACHE_EXPIRE = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Mobile; Android 14; SM-G9910) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
}

# ===================== 核心工具函数（新增盈亏计算逻辑）=====================
# 1. 一键搜索基金
def search_fund(fund_keyword):
    search_url = f"https://fund.eastmoney.com/api/FundSearchApi.ashx?keyword={fund_keyword}&page=1&pageSize=1"
    try:
        res = requests.get(search_url, headers=HEADERS, timeout=8)
        data = res.json()
        if data["totalCount"] == 0:
            st.error("未找到该基金，请检查代码/名称是否正确！")
            return None
        fund_info = data["data"][0]
        fund_code = fund_info["code"]
        fund_name = fund_info["name"]
        holdings_url = f"https://fund.eastmoney.com/{fund_code}.html"
        holdings_res = requests.get(holdings_url, headers=HEADERS, timeout=8)
        stock_pattern = re.compile(r'<td class="tol"><a href=".*?" target="_blank">(.*?)</a></td>.*?<td class="tol"><a href=".*?" target="_blank">(.*?)</a></td>.*?<td class="tor">(.*?)%</td>')
        stocks = stock_pattern.findall(holdings_res.text)
        holdings = {}
        if stocks:
            total_weight = 0
            for stock_code, stock_name, weight in stocks[:5]:
                weight = float(weight)/100
                holdings[stock_code] = {"name": stock_name, "weight": weight}
                total_weight += weight
            if total_weight > 0:
                for s_code in holdings:
                    holdings[s_code]["weight"] = round(holdings[s_code]["weight"] / total_weight, 3)
        # 新增：搜索的基金默认持仓金额为0
        return {"code": fund_code, "name": fund_name, "holdings": holdings,
                "position": {"amount": 0.0, "cost_price": 0.0, "buy_date": datetime.now().strftime("%Y-%m-%d")}}
    except Exception as e:
        st.error(f"搜索失败：{str(e)[:50]}")
        return None

# 2. 获取股票实时涨跌幅
def get_stock_change(stock_code):
    if stock_code in st.session_state.data_cache:
        cache_time, cache_val = st.session_state.data_cache[stock_code]
        if time.time() - cache_time < CACHE_EXPIRE:
            return cache_val
    prefix = "sh" if stock_code.startswith("6") else "sz"
    try:
        res = requests.get(f"https://hq.sinajs.cn/list={prefix}{stock_code}", headers=HEADERS, timeout=5)
        change = float(res.text.split(',')[3]) / 100
        st.session_state.data_cache[stock_code] = (time.time(), change)
        return change
    except:
        return 0.0

# 3. 获取基金最新净值
def get_fund_net(fund_code):
    if fund_code in st.session_state.data_cache:
        cache_time, cache_val = st.session_state.data_cache[fund_code]
        if time.time() - cache_time < CACHE_EXPIRE:
            return cache_val
    try:
        res = requests.get(f"https://fund.eastmoney.com/{fund_code}.html", headers=HEADERS, timeout=8)
        net_text = re.findall(r'<span class="ui-font-large ui-color-red">(.*?)</span>', res.text)[0]
        net_value = float(net_text)
        st.session_state.data_cache[fund_code] = (time.time(), net_value)
        return net_value
    except:
        manual_net = st.number_input(f"{fund_code}净值手动输入", value=1.0, step=0.0001, key=f"manual_net_{fund_code}")
        st.session_state.data_cache[fund_code] = (time.time(), manual_net)
        return manual_net

# 4. 计算单只基金估值+盈亏（核心新增：当日/累计盈亏计算）
def calculate_fund_val(fund_code, show_detail=False):
    if fund_code not in st.session_state.fund_db or not st.session_state.fund_db[fund_code]["holdings"]:
        return None, f"基金{fund_code}无重仓股，无法估值"
    
    st.session_state.current_fund_code = fund_code
    fund_info = st.session_state.fund_db[fund_code]
    fund_name = fund_info["name"]
    holdings = fund_info["holdings"]
    # 持仓信息：金额、成本价、买入日期
    position = fund_info["position"]
    hold_amount = position["amount"]  # 持仓金额（元）
    cost_price = position["cost_price"]  # 持仓成本价
    buy_date = position["buy_date"]
    
    latest_net = get_fund_net(fund_code)
    total_change = 0.0
    for stock_code, stock_info in holdings.items():
        total_change += get_stock_change(stock_code) * stock_info["weight"]
    est_net = round(latest_net * (1 + total_change), 4)  # 实时估算净值
    change_percent = round(total_change * 100, 2)  # 当日涨跌幅（%）
    
    # ===================== 新增：盈亏计算核心逻辑 =====================
    day_profit = 0.0  # 当日盈亏（元）
    day_profit_pct = 0.0  # 当日盈亏（%）
    total_profit = 0.0  # 累计盈亏（元）
    total_profit_pct = 0.0  # 累计盈亏（%）
    hold_value = round(hold_amount / cost_price * est_net, 2) if cost_price > 0 else 0.0  # 当前持仓市值
    
    if hold_amount > 0 and cost_price > 0:
        # 当日盈亏 = 持仓份额 × (当日估算净值 - 昨日净值) → 简化：持仓金额 × 当日涨跌幅
        day_profit = round(hold_amount * total_change, 2)
        day_profit_pct = change_percent
        # 累计盈亏 = 当前市值 - 持仓本金
        total_profit = round(hold_value - hold_amount, 2)
        # 累计盈亏率 = (累计盈亏 / 持仓本金) × 100%
        total_profit_pct = round((total_profit / hold_amount) * 100, 2) if hold_amount > 0 else 0.0
    
    # 涨跌预警
    warn_msg = ""
    if change_percent >= st.session_state.warn_up:
        warn_msg = f"📈 涨{st.session_state.warn_up}%预警"
    elif change_percent <= st.session_state.warn_down:
        warn_msg = f"📉 跌{st.session_state.warn_down}%预警"
    
    # 记录估值+盈亏历史
    val_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.valuation_history.append({
        "估值时间": val_time, "基金代码": fund_code, "基金名称": fund_name,
        "最新净值": round(latest_net,4), "估算净值": est_net, "当日涨跌幅(%)": change_percent,
        "持仓金额(元)": hold_amount, "成本价": cost_price, "当前市值(元)": hold_value,
        "当日盈亏(元)": day_profit, "当日盈亏(%)": day_profit_pct,
        "累计盈亏(元)": total_profit, "累计盈亏(%)": total_profit_pct, "预警": warn_msg if warn_msg else "无"
    })
    # 新增：单独记录盈亏历史（按日期去重）
    st.session_state.profit_history.append({
        "日期": datetime.now().strftime("%Y-%m-%d"), "时间": val_time,
        "基金代码": fund_code, "基金名称": fund_name,
        "持仓金额(元)": hold_amount, "成本价": cost_price, "估算净值": est_net,
        "当日盈亏(元)": day_profit, "当日盈亏(%)": day_profit_pct,
        "累计盈亏(元)": total_profit, "累计盈亏(%)": total_profit_pct, "当前市值(元)": hold_value
    })
    
    # 展示详情
    if show_detail:
        st.subheader(f"{fund_name}（{fund_code}）| 买入日期：{buy_date}")
        # 基础估值信息
        col1, col2 = st.columns(2)
        with col1:
            st.metric("最新净值", f"{round(latest_net,4):.4f}")
            st.metric("估算净值", f"{est_net:.4f}", f"{change_percent:.2f}%", delta_color="inverse")
        with col2:
            st.metric("持仓本金(元)", f"{hold_amount:.2f}")
            st.metric("当前市值(元)", f"{hold_value:.2f}" if hold_value >0 else "0.00")
        # 盈亏信息（重点标色）
        st.subheader("💰 盈亏详情")
        col3, col4 = st.columns(2)
        with col3:
            day_color = "red" if day_profit >0 else "green" if day_profit <0 else "gray"
            st.markdown(f"""
            <div class="profit-card">
                <div style="font-size:14px;">当日盈亏</div>
                <div class="{day_color}" style="font-size:18px;">{day_profit:.2f}元 ({day_profit_pct:.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        with col4:
            total_color = "red" if total_profit >0 else "green" if total_profit <0 else "gray"
            st.markdown(f"""
            <div class="profit-card">
                <div style="font-size:14px;">累计盈亏</div>
                <div class="{total_color}" style="font-size:18px;">{total_profit:.2f}元 ({total_profit_pct:.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)
        # 重仓股详情
        st.subheader("📋 重仓股持仓")
        holdings_data = []
        for s_code, s_info in holdings.items():
            s_change = round(get_stock_change(s_code)*100, 2)
            holdings_data.append({
                "股票代码": s_code, "股票名称": s_info["name"],
                "持仓权重": f"{s_info['weight']:.3f}", "实时涨跌幅(%)": f"{s_change:.2f}"
            })
        st.dataframe(pd.DataFrame(holdings_data), index=False, use_container_width=True)
        st.success(f"✅ 估值+盈亏计算完成！{warn_msg if warn_msg else ''}")
    
    # 返回结果（用于同屏展示）
    return {
        "code": fund_code, "name": fund_name, "net": round(latest_net,4), "est_net": est_net,
        "change": change_percent, "warn": warn_msg,
        "hold_amount": hold_amount, "cost_price": cost_price, "hold_value": hold_value,
        "day_profit": day_profit, "day_profit_pct": day_profit_pct,
        "total_profit": total_profit, "total_profit_pct": total_profit_pct
    }, None

# 5. 批量计算自选基金估值+盈亏
def batch_calc_favorites():
    fund_results = []
    for fund_code in st.session_state.favorites:
        res, err = calculate_fund_val(fund_code)
        if res:
            fund_results.append(res)
        elif err:
            st.warning(err)
    return fund_results

# ===================== 新增：持仓金额管理函数（添加/修改）=====================
def update_position(fund_code, amount, cost_price, buy_date):
    """更新基金持仓信息：金额、成本价、买入日期"""
    if fund_code in st.session_state.fund_db:
        st.session_state.fund_db[fund_code]["position"] = {
            "amount": round(float(amount), 2),
            "cost_price": round(float(cost_price), 4),
            "buy_date": buy_date
        }
        return True, f"✅ {fund_code}持仓信息更新成功！"
    return False, "❌ 基金不存在，更新失败！"

# ===================== 核心功能1：自选基金同屏估值+盈亏展示（首页）=====================
st.divider()
st.header("❤️ 自选基金同屏（估值+实时盈亏）")
if st.button("🔄 刷新所有自选基金（估值+盈亏）", key="refresh_all", type="primary"):
    st.session_state.data_cache = {}
    batch_calc_favorites()

# 同屏展示基金卡片（含盈亏信息）
fund_results = batch_calc_favorites()
if fund_results:
    for fund in fund_results:
        # 颜色区分：涨跌/盈亏
        change_color = "red" if fund["change"] >0 else "green" if fund["change"] <0 else "gray"
        day_profit_color = "red" if fund["day_profit"] >0 else "green" if fund["day_profit"] <0 else "gray"
        total_profit_color = "red" if fund["total_profit"] >0 else "green" if fund["total_profit"] <0 else "gray"
        
        # 基金卡片（含持仓+盈亏）
        st.markdown(f"""
        <div class="fund-card">
            <div class="fund-title">{fund['code']} | {fund['name']}</div>
            <div style="display: flex; justify-content: space-between; font-size:14px; margin:5px 0;">
                <div>持仓本金：{fund['hold_amount']:.2f}元</div>
                <div>当前市值：{fund['hold_value']:.2f}元</div>
            </div>
            <div style="font-size:14px; margin:5px 0;">
                估算净值：{fund['est_net']:.4f} | 
                当日涨跌幅：<span class="{change_color}">{fund['change']:.2f}%</span> {fund['warn']}
            </div>
            <div style="display: flex; justify-content: space-between; font-size:14px; margin-top:8px;">
                <div>当日盈亏：<span class="{day_profit_color}">{fund['day_profit']:.2f}元</span></div>
                <div>累计盈亏：<span class="{total_profit_color}">{fund['total_profit']:.2f}元 ({fund['total_profit_pct']:.2f}%)</span></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        # 查看详情/修改持仓按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"📊 查看{fund['code']}详情", key=f"detail_{fund['code']}"):
                calculate_fund_val(fund['code'], show_detail=True)
        with col2:
            if st.button(f"✏️ 修改{fund['code']}持仓", key=f"edit_{fund['code']}"):
                # 触发持仓修改弹窗（通过session_state标记）
                st.session_state.edit_fund = fund['code']
                st.rerun()
else:
    st.info("ℹ️ 自选基金为空/无重仓股，先添加基金并加入自选吧！")

# ===================== 核心功能2：持仓金额添加/修改（弹窗式，手机适配）=====================
if "edit_fund" in st.session_state and st.session_state.edit_fund:
    st.divider()
    st.header(f"✏️ 编辑基金持仓 | {st.session_state.edit_fund} - {st.session_state.fund_db[st.session_state.edit_fund]['name']}")
    fund_code = st.session_state.edit_fund
    current_pos = st.session_state.fund_db[fund_code]["position"]
    
    # 持仓信息输入框
    col1, col2 = st.columns(2)
    with col1:
        hold_amount = st.number_input("持仓本金（元）", min_value=0.0, step=10.0, value=current_pos["amount"], key="edit_amount")
        cost_price = st.number_input("持仓成本价", min_value=0.0, step=0.0001, value=current_pos["cost_price"], key="edit_cost")
    with col2:
        buy_date = st.date_input("买入日期", value=pd.to_datetime(current_pos["buy_date"]), key="edit_date")
        buy_date_str = buy_date.strftime("%Y-%m-%d")
    
    # 保存/取消按钮
    col3, col4 = st.columns(2)
    with col3:
        if st.button("✅ 保存持仓信息", key="save_position"):
            if hold_amount >=0 and cost_price >=0:
                success, msg = update_position(fund_code, hold_amount, cost_price, buy_date_str)
                st.success(msg)
                del st.session_state.edit_fund
                st.rerun()
            else:
                st.error("持仓金额和成本价不能为负数！")
    with col4:
        if st.button("❌ 取消编辑", key="cancel_edit"):
            del st.session_state.edit_fund
            st.rerun()

# ===================== 功能3：基金管理（搜索/添加/自选编辑）=====================
st.divider()
st.header("📝 基金管理（搜索/添加/自选编辑）")
tab1, tab2, tab3 = st.tabs(["🔍 一键搜索添加", "📥 手动添加基金", "✏️ 自选基金编辑"])

# 子板块1：一键搜索添加（带默认持仓）
with tab1:
    st.subheader("输入基金代码/名称搜索")
    fund_keyword = st.text_input("如161725或招商白酒", placeholder="基金代码/名称", key="fund_keyword")
    if st.button("🔍 开始搜索", key="search_fund"):
        if fund_keyword:
            with st.spinner("正在搜索..."):
                fund_data = search_fund(fund_keyword)
                if fund_data:
                    st.session_state.temp_fund = fund_data
                    st.success(f"找到基金：{fund_data['code']} - {fund_data['name']}")
                    if fund_data["holdings"]:
                        st.subheader("📋 自动获取前5大重仓股")
                        holdings_df = pd.DataFrame([{
                            "股票代码": k, "股票名称": v["name"], "持仓权重": f"{v['weight']:.3f}"
                        } for k, v in fund_data["holdings"].items()])
                        st.dataframe(holdings_df, index=False, use_container_width=True)
    # 添加到基金库+自选
    if "temp_fund" in st.session_state:
        if st.button("✅ 添加到基金库+自选", key="add_search_fund"):
            fund_data = st.session_state.temp_fund
            if fund_data["code"] not in st.session_state.fund_db:
                st.session_state.fund_db[fund_data["code"]] = fund_data
            if fund_data["code"] not in st.session_state.favorites:
                st.session_state.favorites.append(fund_data["code"])
            st.success(f"✅ {fund_data['code']}已添加！可在自选页修改持仓金额")
            del st.session_state.temp_fund
            st.rerun()

# 子板块2：手动添加基金（带持仓信息）
with tab2:
    st.subheader("手动填写基金信息")
    new_fund_code = st.text_input("基金代码（纯数字）", placeholder="如001632", key="new_fund_code")
    new_fund_name = st.text_input("基金名称", placeholder="如天弘中证医药100A", key="new_fund_name")
    st.subheader("添加重仓股（最少1只）")
    stock_datas = []
    for i in range(5):
        col1, col2, col3 = st.columns(3)
        with col1:
            s_code = st.text_input(f"股票代码{i+1}", placeholder="600519", key=f"s_code_{i}")
        with col2:
            s_name = st.text_input(f"股票名称{i+1}", placeholder="贵州茅台", key=f"s_name_{i}")
        with col3:
            s_weight = st.number_input(f"权重{i+1}", 0.001, 1.0, 0.1, step=0.001, key=f"s_weight_{i}")
        if s_code and s_name:
            stock_datas.append({"code": s_code, "name": s_name, "weight": s_weight})
    # 初始持仓信息
    st.subheader("初始持仓信息（可后续修改）")
    init_amount = st.number_input("初始持仓本金（元）", min_value=0.0, step=10.0, value=0.0, key="init_amount")
    init_cost = st.number_input("初始成本价", min_value=0.0, step=0.0001, value=0.0, key="init_cost")
    
    if st.button("✅ 确认添加+加入自选", key="add_fund"):
        if not new_fund_code or not new_fund_name or not stock_datas:
            st.error("基金代码、名称、重仓股（至少1只）不能为空！")
        elif new_fund_code in st.session_state.fund_db:
            st.error(f"基金{new_fund_code}已存在！")
        else:
            fund_holdings = {s["code"]: {"name": s["name"], "weight": s["weight"]} for s in stock_datas}
            st.session_state.fund_db[new_fund_code] = {
                "name": new_fund_name, "holdings": fund_holdings,
                "position": {"amount": round(init_amount,2), "cost_price": round(init_cost,4),
                             "buy_date": datetime.now().strftime("%Y-%m-%d")}
            }
            if new_fund_code not in st.session_state.favorites:
                st.session_state.favorites.append(new_fund_code)
            st.success(f"✅ {new_fund_code}添加成功！可直接修改持仓金额")
            st.rerun()

# 子板块3：自选基金编辑
with tab3:
    st.subheader("📌 自选基金管理（勾选=同屏展示）")
    all_fund_codes = list(st.session_state.fund_db.keys())
    selected_funds = st.multiselect(
        "选择要展示的自选基金（可多选）",
        options=all_fund_codes,
        default=st.session_state.favorites,
        format_func=lambda x: f"{x} - {st.session_state.fund_db[x]['name']}"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 保存自选设置", key="save_favorites"):
            st.session_state.favorites = selected_funds
            st.success(f"✅ 自选基金已保存，共{len(selected_funds)}只！")
    with col2:
        if st.button("🗑️ 清空所有自选", key="clear_favorites"):
            st.session_state.favorites = []
            st.success("✅ 自选基金已清空！")
    # 删除基金库中的基金
    st.subheader("🗑️ 删除基金库中的基金")
    del_fund_code = st.selectbox(
        "选择要删除的基金",
        options=all_fund_codes,
        format_func=lambda x: f"{x} - {st.session_state.fund_db[x]['name']}",
        key="del_fund_select"
    )
    if st.button("❌ 确认删除基金", key="del_fund"):
        del st.session_state.fund_db[del_fund_code]
        if del_fund_code in st.session_state.favorites:
            st.session_state.favorites.remove(del_fund_code)
        if del_fund_code == st.session_state.current_fund_code:
            st.session_state.current_fund_code = all_fund_codes[0] if all_fund_codes else None
        st.success(f"✅ 基金{del_fund_code}已删除！")
        st.rerun()

# ===================== 功能4：盈亏历史记录（新增，可筛选/导出）=====================
st.divider()
st.header("📜 盈亏历史记录（永久保存）")
if st.session_state.profit_history:
    # 转换为DataFrame并去重（保留最新记录）
    profit_df = pd.DataFrame(st.session_state.profit_history)
    # 按基金+日期去重，保留当日最新记录
    profit_df = profit_df.drop_duplicates(subset=["基金代码", "日期"], keep="last")
    # 按日期倒序排列
    profit_df = profit_df.sort_values(["日期", "时间"], ascending=False).reset_index(drop=True)
    
    # 基金筛选（手机端适配）
    fund_filter = st.selectbox("筛选基金（全部/单只）", options=["全部"] + all_fund_codes, key="profit_filter")
    if fund_filter != "全部":
        profit_df = profit_df[profit_df["基金代码"] == fund_filter]
    
    # 展示盈亏历史
    show_cols = ["日期", "基金代码", "基金名称", "估算净值", "持仓金额(元)", "当前市值(元)",
                 "当日盈亏(元)", "当日盈亏(%)", "累计盈亏(元)", "累计盈亏(%)"]
    st.dataframe(profit_df[show_cols], index=False, use_container_width=True)
    
    # 导出盈亏历史
    csv_profit = profit_df[show_cols].to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 导出盈亏历史到Excel",
        data=csv_profit,
        file_name=f"基金盈亏历史_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="download_profit"
    )
    
    # 清空盈亏历史
    if st.button("🗑️ 清空盈亏历史记录", key="clear_profit"):
        st.session_state.profit_history = []
        st.session_state.valuation_history = []
        st.success("✅ 盈亏+估值历史已全部清空！")
        st.rerun()
else:
    st.info("ℹ️ 暂无盈亏历史记录，添加持仓并计算估值后自动生成！")

# ===================== 功能5：辅助设置（预警/单只估值）=====================
st.divider()
st.header("⚡ 辅助功能设置")
# 单只基金精准估值
all_fund_codes = list(st.session_state.fund_db.keys())
if all_fund_codes:
    st.subheader("📊 单只基金精准估值")
    fund_code_select = st.selectbox(
        "选择基金", options=all_fund_codes,
        format_func=lambda x: f"{x} - {st.session_state.fund_db[x]['name']}",
        index=all_fund_codes.index(st.session_state.current_fund_code) if st.session_state.current_fund_code in all_fund_codes else 0,
        key="fund_select"
    )
    if st.button("📈 计算单只基金详细估值+盈亏", key="single_calc"):
        calculate_fund_val(fund_code_select, show_detail=True)

# 涨跌预警设置
st.subheader("🚨 涨跌预警阈值设置")
col1, col2 = st.columns(2)
with col1:
    new_warn_up = st.number_input("上涨预警阈值(%)", min_value=0.0, step=0.1, value=st.session_state.warn_up, key="new_warn_up")
with col2:
    new_warn_down = st.number_input("下跌预警阈值(%)", max_value=0.0, step=0.1, value=st.session_state.warn_down, key="new_warn_down")
if st.button("✅ 保存预警阈值", key="save_warn"):
    st.session_state.warn_up = new_warn_up
    st.session_state.warn_down = new_warn_down
    st.success(f"✅ 预警阈值保存成功！上涨≥{new_warn_up}% | 下跌≤{new_warn_down}%")

# 底部说明
st.divider()
st.markdown("""
<center>
© 2025 基金实时估值-持仓盈亏版 | 数据来源：新浪财经、天天基金网<br>
⚠️ 估值为盘中参考，实际盈亏以基金公司公布净值为准 | 持仓数据本地持久化，刷新不丢失<br>
💡 当日盈亏=持仓本金×当日涨跌幅；累计盈亏=当前市值-持仓本金；累计盈亏率=累计盈亏/持仓本金×100%
</center>
""", unsafe_allow_html=True)
