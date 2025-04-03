import streamlit as st
import json
import os
from datetime import datetime
from openai import OpenAI

# 初始化配置
CLIENT = OpenAI(
    api_key="sk-ea71d9c3658143119e7c6442b040c4df",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
MODEL = "qwq-32b"

# 数据存储路径
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONVERSATIONS_FILE = os.path.join(DATA_DIR, "conversations.json")

# 初始化数据存储
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def init_json_file(file_path):
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump([], f)

init_json_file(USERS_FILE)
init_json_file(CONVERSATIONS_FILE)

# 完整问卷结构
QUESTIONNAIRE = [
    {
        "id": "q1",
        "text": "过去7天中，您有几天进行了剧烈身体活动？",
        "type": "days",
        "jump": {"condition": 0, "target": "q3"}
    },
    {
        "id": "q2",
        "text": "在其中一天，您通常花费多长时间进行此类剧烈活动？",
        "type": "time"
    },
    {
        "id": "q3",
        "text": "过去7天中，您有几天进行了中等强度身体活动？",
        "type": "days",
        "jump": {"condition": 0, "target": "q5"}
    },
    {
        "id": "q4",
        "text": "在其中一天，您通常花费多长时间进行此类中等强度活动？",
        "type": "time"
    },
    {
        "id": "q5",
        "text": "过去7天中，您有几天进行了步行活动？",
        "type": "days",
        "jump": {"condition": 0, "target": "q7"}
    },
    {
        "id": "q6",
        "text": "在其中一天，您通常花费多长时间步行？",
        "type": "time"
    },
    {
        "id": "q7",
        "text": "过去7天中，您每天平均花费多长时间久坐？",
        "type": "sitting_time"
    }
]

QUESTION_MAP = {q["id"]: i for i, q in enumerate(QUESTIONNAIRE)}

def save_conversation(username, conversation):
    data = []
    if os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE, "r") as f:
            data = json.load(f)
    data.append({
        "username": username,
        "timestamp": str(datetime.now()),
        "conversation": conversation
    })
    with open(CONVERSATIONS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_plan(answers):
    prompt = f"""基于以下问卷结果生成个性化运动方案：
    
    **剧烈运动**：{answers.get('q1', {}).get('days', 0)}天/周，每次{answers.get('q2', {}).get('hours', 0)}小时{answers.get('q2', {}).get('minutes', 0)}分钟
    
    **中等强度运动**：{answers.get('q3', {}).get('days', 0)}天/周，每次{answers.get('q4', {}).get('hours', 0)}小时{answers.get('q4', {}).get('minutes', 0)}分钟
    
    **步行**：{answers.get('q5', {}).get('days', 0)}天/周，每次{answers.get('q6', {}).get('hours', 0)}小时{answers.get('q6', {}).get('minutes', 0)}分钟
    
    **久坐时间**：每天{answers.get('q7', {}).get('hours', 0)}小时{answers.get('q7', {}).get('minutes', 0)}分钟
    
    请按照以下要求生成方案：
    1. 分不同强度给出运动建议
    2. 包含久坐提醒和改善建议
    3. 给出具体实施计划（频率、时长、强度）
    4. 使用中文口语化表达"""
    
    try:
        response = CLIENT.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"方案生成失败：{str(e)}"

def login_page():
    st.title("用户登录")
    username = st.text_input("请输入您的姓名", key="username_input")
    if st.button("开始"):
        if username.strip():
            st.session_state.logged_in = True
            st.session_state.username = username.strip()
            st.session_state.current_q_index = 0
            st.session_state.answers = {}
            st.rerun()
        else:
            st.error("请输入有效姓名")

def handle_question_form():
    q = QUESTIONNAIRE[st.session_state.current_q_index]
    st.subheader(q["text"])
    
    answer = {}
    with st.form(f"form_{q['id']}"):
        # 处理不同题型
        if q["type"] == "days":
            days = st.number_input("天数/周", min_value=0, max_value=7, key=f"{q['id']}_days")
            no_activity = st.checkbox("未进行该强度活动", key=f"{q['id']}_check")
            answer = {"days": days, "no_activity": no_activity}
            
        elif q["type"] == "time":
            col1, col2 = st.columns(2)
            with col1:
                hours = st.number_input("小时/天", min_value=0, key=f"{q['id']}_hours")
            with col2:
                minutes = st.number_input("分钟/天", min_value=0, max_value=59, key=f"{q['id']}_minutes")
            unsure = st.checkbox("不知道/不确定", key=f"{q['id']}_unsure")
            answer = {"hours": hours, "minutes": minutes, "unsure": unsure}
            
        elif q["type"] == "sitting_time":
            col1, col2 = st.columns(2)
            with col1:
                hours = st.number_input("小时/天", min_value=0, key=f"{q['id']}_hours")
            with col2:
                minutes = st.number_input("分钟/天", min_value=0, max_value=59, key=f"{q['id']}_minutes")
            unsure = st.checkbox("不知道/不确定", key=f"{q['id']}_unsure")
            answer = {"hours": hours, "minutes": minutes, "unsure": unsure}
        
        submitted = st.form_submit_button("下一步")
        
        if submitted:
            st.session_state.answers[q["id"]] = answer
            handle_form_submission(q, answer)

def handle_form_submission(q, answer):
    # 处理跳转逻辑
    if q.get("jump"):
        if answer.get("no_activity") and answer["days"] == q["jump"]["condition"]:
            target_index = QUESTION_MAP[q["jump"]["target"]]
            st.session_state.current_q_index = target_index
            return
    
    # 正常流程
    if st.session_state.current_q_index < len(QUESTIONNAIRE) - 1:
        st.session_state.current_q_index += 1
    else:
        st.session_state.questionnaire_completed = True
    
    st.rerun()

def admin_page():
    st.title("后台管理系统")
    
    if os.path.exists(CONVERSATIONS_FILE):
        with open(CONVERSATIONS_FILE, "r") as f:
            conversations = json.load(f)
        
        users = list(set([c["username"] for c in conversations]))
        selected_user = st.selectbox("选择用户", users)
        
        st.divider()
        st.subheader(f"{selected_user}的对话记录")
        
        for conv in reversed([c for c in conversations if c["username"] == selected_user]):
            with st.expander(f"记录时间：{conv['timestamp']}"):
                st.json(conv["conversation"], expanded=False)
    else:
        st.warning("暂无对话记录")

def main_app():
    if "logged_in" not in st.session_state:
        login_page()
        return
    
    if not st.session_state.get("questionnaire_completed"):
        st.progress((st.session_state.current_q_index + 1) / len(QUESTIONNAIRE))
        handle_question_form()
    else:
        show_result_page()

def show_result_page():
    st.title("个性化运动方案")
    
    with st.spinner("正在生成您的运动方案..."):
        plan = generate_plan(st.session_state.answers)
    
    st.success("方案生成完成！")
    st.markdown(f"## 您的专属运动建议\n{plan}")
    
    # 保存对话记录
    save_conversation(st.session_state.username, {
        "answers": st.session_state.answers,
        "plan": plan
    })
    
    if st.button("重新填写问卷"):
        st.session_state.current_q_index = 0
        st.session_state.answers = {}
        del st.session_state.questionnaire_completed
        st.rerun()

def main():
    st.set_page_config(page_title="健康助手", layout="wide")
    
    # 管理员入口
    if st.secrets.get("ADMIN_PWD"):
        if st.sidebar.text_input("管理员密码", type="password"):
            if st.session_state.get("admin_auth"):
                admin_page()
            else:
                st.sidebar.error("管理员密码错误")
    
    # 主应用
    if not st.session_state.get("admin_auth"):
        main_app()

if __name__ == "__main__":
    main()